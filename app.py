from flask import Flask, request, jsonify, render_template
import requests
import os
import json

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# 儲存當前單子（簡單用記憶體，Railway 重啟會清空）
current_trade = {}

# ─────────────────────────────────────────
# Telegram 發送
# ─────────────────────────────────────────
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    response = requests.post(url, json=payload)
    return response.ok

# ─────────────────────────────────────────
# 訊息格式
# ─────────────────────────────────────────
def msg_entry(t):
    direction = "多單 LONG ▲" if t["direction"] == "long" else "空單 SHORT ▼"
    emoji = "🟢" if t["direction"] == "long" else "🔴"
    return (
        f"{emoji} <b>XAU/USD 進場提醒</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"方向｜{direction}\n"
        f"進場價｜{t['entry']}\n"
        f"停損｜{t['sl']} 以下\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 TP1｜{t['tp1']}\n"
        f"🎯 TP2｜{t['tp2']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"M15 區間距離｜{t['range']}\n"
        f"風控｜帳戶 1~3%"
    )

def msg_tp1(t):
    return (
        f"✅ <b>XAU/USD TP1 達到！</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"當前價｜{t['tp1']}\n"
        f"進場價｜{t['entry']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚡ 動作：執行讓利出場\n"
        f"🔒 若續抱：停損移至 {t['entry']} 保本\n"
        f"🎯 下一目標｜{t['tp2']}"
    )

def msg_profit(t, price):
    return (
        f"💰 <b>XAU/USD 讓利提醒</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"當前價｜{price}\n"
        f"建議出場｜一半倉位先走\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔒 剩餘倉位停損移至 {t['entry']} 保本\n"
        f"🎯 續抱目標｜{t['tp2']}"
    )

def msg_sl_warning(t, price):
    return (
        f"🚨 <b>XAU/USD 停損警告！</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"當前價｜{price}\n"
        f"停損位｜{t['sl']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚠️ 價格接近停損！請確認部位\n"
        f"❌ 若觸及停損：立即出場勿凹單"
    )

def msg_close(t):
    return (
        f"🏁 <b>XAU/USD 本波結束</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"M15 走完兩層，生命週期結束\n"
        f"TP1｜{t['tp1']} ✅\n"
        f"TP2｜{t['tp2']} ✅\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📌 等新區間形成再規劃下一波\n"
        f"🔄 停手觀察，勿追行情"
    )

# ─────────────────────────────────────────
# 路由
# ─────────────────────────────────────────

# 首頁：輸入表單
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", trade=current_trade)

# 儲存單子 + 推送進場提醒
@app.route("/set_trade", methods=["POST"])
def set_trade():
    global current_trade
    data = request.json
    current_trade = {
        "direction": data.get("direction", "long"),
        "entry":     data.get("entry", ""),
        "sl":        data.get("sl", ""),
        "tp1":       data.get("tp1", ""),
        "tp2":       data.get("tp2", ""),
        "range":     data.get("range", ""),
    }
    send_telegram(msg_entry(current_trade))
    return jsonify({"ok": True, "trade": current_trade})

# 查詢當前單子
@app.route("/trade", methods=["GET"])
def get_trade():
    return jsonify(current_trade)

# 清除單子
@app.route("/clear_trade", methods=["POST"])
def clear_trade():
    global current_trade
    current_trade = {}
    return jsonify({"ok": True})

# TradingView Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    global current_trade
    data = request.json
    alert_type = data.get("type", "")
    price = data.get("price", "N/A")

    if not current_trade:
        return jsonify({"ok": False, "error": "尚未設定當前單子"})

    if alert_type == "tp1":
        message = msg_tp1(current_trade)
    elif alert_type == "profit":
        message = msg_profit(current_trade, price)
    elif alert_type == "sl_warning":
        message = msg_sl_warning(current_trade, price)
    elif alert_type == "close":
        message = msg_close(current_trade)
        current_trade = {}  # 本波結束，清除單子
    else:
        message = f"📊 XAU/USD 警報：{data.get('message', alert_type)}"

    success = send_telegram(message)
    return jsonify({"ok": success})

# 健康檢查
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running", "has_trade": bool(current_trade)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
