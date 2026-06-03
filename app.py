from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

# 環境變數（在 Railway 設定）
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_CHAT_ID   = os.environ.get("TG_CHAT_ID")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")  # 可選：防止未授權請求

# 台灣時區
TZ_TAIPEI = timezone(timedelta(hours=8))

# 每日戰績（重啟後歸零；如需持久化請接 Redis 或資料庫）
daily_stats = {"wins": 0, "losses": 0, "date": ""}


def get_today() -> str:
    return datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")


def reset_if_new_day():
    today = get_today()
    if daily_stats["date"] != today:
        daily_stats["wins"] = 0
        daily_stats["losses"] = 0
        daily_stats["date"] = today


def send_telegram(text: str) -> bool:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("[ERROR] TG_BOT_TOKEN 或 TG_CHAT_ID 未設定")
        return False

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=10)
    if not resp.ok:
        print(f"[TG ERROR] {resp.status_code} {resp.text}")
    return resp.ok


def build_message(data: dict) -> str:
    """
    TradingView alert payload 格式（JSON）:
    {
      "result":  "win" | "loss",
      "entry":   3320.50,
      "exit":    3335.00,
      "pnl":     150.00,        // 絕對值，正數即可
      "lot":     0.10,          // 選填
      "note":    "M15撐壓回測"  // 選填
    }
    """
    result = data.get("result", "win").lower()
    entry  = float(data.get("entry", 0))
    exit_  = float(data.get("exit",  0))
    pnl    = abs(float(data.get("pnl", 0)))
    lot    = data.get("lot")
    note   = data.get("note", "").strip()

    is_win   = result == "win"
    emoji    = "✅" if is_win else "❌"
    label    = "獲利" if is_win else "停損"
    pnl_sign = "+" if is_win else "-"

    # 更新戰績
    reset_if_new_day()
    if is_win:
        daily_stats["wins"] += 1
    else:
        daily_stats["losses"] += 1

    now_str = datetime.now(TZ_TAIPEI).strftime("%H:%M")

    lines = [
        f"📋 交易結果｜XAUUSD",
        f"━━━━━━━━━━━━━━",
        f"結果：{emoji} {label}",
        f"進場：${entry:,.2f}",
        f"出場：${exit_:,.2f}",
        f"損益：{pnl_sign}${pnl:,.2f}",
    ]

    if lot:
        lines.append(f"手數：{float(lot):.2f} lot")

    if note:
        lines.append(f"備註：{note}")

    lines += [
        f"━━━━━━━━━━━━━━",
        f"今日戰績：{daily_stats['wins']}勝 {daily_stats['losses']}負",
        f"<i>{now_str} TST</i>",
    ]

    return "\n".join(lines)


@app.route("/webhook", methods=["POST"])
def webhook():
    # 選填：驗證 secret
    if WEBHOOK_SECRET:
        incoming = request.headers.get("X-Webhook-Secret", "")
        if incoming != WEBHOOK_SECRET:
            return jsonify({"error": "unauthorized"}), 401

    # 解析 JSON
    try:
        data = request.get_json(force=True)
        if not data:
            raise ValueError("empty body")
    except Exception as e:
        return jsonify({"error": f"invalid JSON: {e}"}), 400

    message = build_message(data)
    ok = send_telegram(message)

    return jsonify({"ok": ok, "message": message}), 200 if ok else 500


@app.route("/stats", methods=["GET"])
def stats():
    """查看今日戰績"""
    reset_if_new_day()
    return jsonify(daily_stats)


@app.route("/reset", methods=["POST"])
def reset():
    """手動重置戰績"""
    daily_stats["wins"] = 0
    daily_stats["losses"] = 0
    daily_stats["date"] = get_today()
    return jsonify({"ok": True, "stats": daily_stats})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
