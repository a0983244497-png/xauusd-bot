from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from datetime import datetime, timezone, timedelta

app = Flask(__name__)
CORS(app)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

TZ_TAIPEI = timezone(timedelta(hours=8))

current_trade = {}
sop_status = {"step": -1, "triggered": []}
daily_stats = {"wins": 0, "losses": 0, "date": ""}

def get_today():
    return datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")

def reset_if_new_day():
    today = get_today()
    if daily_stats["date"] != today:
        daily_stats["wins"] = 0
        daily_stats["losses"] = 0
        daily_stats["date"] = today

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    response = requests.post(url, json=payload)
    return response.ok

def msg_entry(t):
    direction = "多單 LONG ▲" if t["direction"] == "long" else "空單 SHORT ▼"
    emoji = "🟢" if t["direction"] == "long" else "🔴"
    return (f"{emoji} <b>XAU/USD 進場提醒</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"方向｜{direction}\n"
            f"進場價｜{t['entry']}\n"
            f"停損｜{t['sl']} 以下\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎯 TP1｜{t['tp1']}\n"
            f"🎯 TP2｜{t['tp2']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"M15 區間距離｜{t['range']}\n"
            f"風控｜帳戶 1~3%")

def msg_tp1(t):
    return (f"✅ <b>XAU/USD TP1 達到！</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"當前價｜{t['tp1']}\n"
            f"進場價｜{t['entry']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚡ 動作：執行讓利出場\n"
            f"🔒 若續抱：停損移至 {t['entry']} 保本\n"
            f"🎯 下一目標｜{t['tp2']}")

def msg_profit(t, price):
    return (f"💰 <b>XAU/USD 讓利提醒</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"當前價｜{price}\n"
            f"建議出場｜一半倉位先走\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔒 剩餘倉位停損移至 {t['entry']} 保本\n"
            f"🎯 續抱目標｜{t['tp2']}")

def msg_sl_warning(t, price):
    return (f"🚨 <b>XAU/USD 停損警告！</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"當前價｜{price}\n"
            f"停損位｜{t['sl']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚠️ 價格接近停損！請確認部位\n"
            f"❌ 若觸及停損：立即出場勿凹單")

def msg_close(t):
    return (f"🏁 <b>XAU/USD 本波結束</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"M15 走完兩層，生命週期結束\n"
            f"TP1｜{t['tp1']} ✅\n"
            f"TP2｜{t['tp2']} ✅\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 等新區間形成再規劃下一波\n"
            f"🔄 停手觀察，勿追行情")

def msg_consolidating(t):
    if t:
        return (f"⏳ <b>XAU/USD 15分整理中</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"關鍵位｜{t['entry']}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📌 等待突破訊號，尚未進場\n"
                f"🔍 持續觀察區間形成")
    return (f"⏳ <b>XAU/USD 15分區間整理中</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 等待突破訊號，尚未進場\n"
            f"🔍 持續觀察區間形成")

def msg_breakout(t):
    if t:
        direction = "向下突破" if t["direction"] == "short" else "向上突破"
        return (f"⚡ <b>XAU/USD 突破訊號！</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{direction} {t['entry']}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📌 等待回測確認，準備進場")
    return (f"⚡ <b>XAU/USD 突破訊號！</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 等待回測確認，準備進場")

def msg_retest(t):
    if t:
        return (f"🔄 <b>XAU/USD 回測確認！</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"回測 {t['entry']} 守住\n"
                f"━━━━━━━━━━━━━━━\n"
                f"⚡ 等待第三根K棒確認進場")
    return (f"🔄 <b>XAU/USD 回測確認！</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚡ 等待第三根K棒確認進場")

def msg_entry_confirmed(t):
    if t:
        direction = "多單 LONG ▲" if t["direction"] == "long" else "空單 SHORT ▼"
        return (f"🎯 <b>XAU/USD 第三根進場！</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"方向｜{direction}\n"
                f"進場價｜{t['entry']}\n"
                f"停損｜{t['sl']}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🎯 TP1｜{t['tp1']}\n"
                f"🎯 TP2｜{t['tp2']}")
    return (f"🎯 <b>XAU/USD 第三根進場！</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚡ 進場執行中")

def msg_retest_fail(t):
    if t:
        return (f"❌ <b>XAU/USD 回測失敗</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"回測 {t['entry']} 未守住\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🚫 訊號取消，等待重新整理\n"
                f"📌 保持觀察，勿追入")
    return (f"❌ <b>XAU/USD 回測失敗</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🚫 訊號取消，等待重新整理")

def msg_wait_breakout(t):
    return (f"🔁 <b>XAU/USD 重新等待突破</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"行情假突破，訊號失效\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔍 回到觀察模式\n"
            f"📌 等待新區間突破再規劃")

def msg_result(data):
    result = data.get("result", "win").lower()
    entry  = float(data.get("entry", 0))
    exit_  = float(data.get("exit", 0))
    pnl    = abs(float(data.get("pnl", 0)))
    lot    = data.get("lot")
    note   = data.get("note", "").strip()

    is_win   = result == "win"
    emoji    = "✅" if is_win else "❌"
    label    = "獲利" if is_win else "停損"
    pnl_sign = "+" if is_win else "-"

    reset_if_new_day()
    if is_win:
        daily_stats["wins"] += 1
    else:
        daily_stats["losses"] += 1

    now_str = datetime.now(TZ_TAIPEI).strftime("%H:%M")

    lines = [
        f"📋 <b>交易結果｜XAUUSD</b>",
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


HTML = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XAU/USD 交易管理</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+TC:wght@400;500;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f1117;font-family:'Noto Sans TC',sans-serif;color:#d1d9f0;min-height:100vh;padding:20px}
.container{max-width:480px;margin:0 auto}
h1{font-size:18px;font-weight:700;color:#f0c040;margin-bottom:4px;letter-spacing:1px}
.subtitle{font-size:12px;color:#6b7280;margin-bottom:20px}
.hint-bar{background:#1a2035;border:1px solid #2a3a5c;border-radius:8px;padding:10px 14px;font-size:12px;color:#60a0ff;margin-bottom:16px;display:none}
.hint-bar.show{display:block}
.section-title{font-size:11px;color:#6b7280;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px}

/* SOP */
.sop-steps{display:flex;flex-direction:column;gap:6px;margin-bottom:8px}
.sop-step{display:flex;align-items:center;gap:10px;padding:10px 14px;background:#1a1f2e;border:1px solid #2a3a5c;border-radius:8px;transition:all .2s}
.sop-step.active{border-color:#f0c040;background:#1e2235}
.sop-step.done{border-color:#22c55e;background:#0f2318}
.sop-step.fail{border-color:#ef4444;background:#2a0a0a}
.sop-dot{width:8px;height:8px;border-radius:50%;background:#374151;flex-shrink:0}
.sop-step.active .sop-dot{background:#f0c040}
.sop-step.done .sop-dot{background:#22c55e}
.sop-step.fail .sop-dot{background:#ef4444}
.sop-label{flex:1;font-size:13px}
.sop-btn{font-size:11px;padding:4px 10px;background:#1e3a5c;border:1px solid #2a5080;color:#60a0ff;border-radius:6px;cursor:pointer;white-space:nowrap}
.sop-btn:active{transform:scale(.97)}
.sop-btn.red{background:#2a0a0a;border-color:#5c1a1a;color:#ef4444}
.sop-btn.gray{background:#1a1f2e;border-color:#374151;color:#9ca3af}
.sop-extra{display:flex;gap:6px;margin-bottom:16px}
.sop-extra button{flex:1;padding:8px;font-size:12px;border-radius:8px;cursor:pointer;transition:all .15s}
.btn-retest-fail{background:#2a0a0a;border:1px solid #ef444466;color:#ef4444}
.btn-wait-breakout{background:#1a1f2e;border:1px solid #37415166;color:#9ca3af}

/* Trade card */
.trade-card{background:#1a1f2e;border:1px solid #2a3a5c;border-radius:10px;padding:16px;margin-bottom:16px}
.trade-card.long{border-color:#22c55e}
.trade-card.short{border-color:#ef4444}
.trade-header{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.direction-badge{font-size:12px;font-weight:700;padding:3px 10px;border-radius:20px}
.direction-badge.long{background:#0f2318;color:#22c55e}
.direction-badge.short{background:#2a0a0a;color:#ef4444}
.trade-row{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px}
.trade-label{color:#6b7280}
.trade-val{font-family:'IBM Plex Mono',monospace;color:#d1d9f0}
.trade-val.tp{color:#60a0ff}
.no-trade{color:#4b5563;font-size:13px;text-align:center;padding:10px 0}

/* Form */
.form-section{background:#1a1f2e;border:1px solid #2a3a5c;border-radius:10px;padding:16px;margin-bottom:16px}
.form-section summary{font-size:13px;font-weight:500;cursor:pointer;color:#9ca3af;list-style:none}
.form-section summary::-webkit-details-marker{display:none}
.form-section[open] summary{color:#f0c040;margin-bottom:14px}
.dir-toggle{display:flex;gap:8px;margin-bottom:12px}
.dir-btn{flex:1;padding:9px;font-size:13px;font-weight:600;border-radius:8px;border:1px solid #374151;background:#111827;color:#6b7280;cursor:pointer;transition:all .15s}
.dir-btn.long.active{background:#0f2318;border-color:#22c55e;color:#22c55e}
.dir-btn.short.active{background:#2a0a0a;border-color:#ef4444;color:#ef4444}
.field{margin-bottom:10px}
.field label{display:block;font-size:11px;color:#6b7280;margin-bottom:4px}
.field input{width:100%;background:#111827;border:1px solid #374151;border-radius:6px;padding:8px 10px;font-size:14px;color:#d1d9f0;font-family:'IBM Plex Mono',monospace}
.field input:focus{outline:none;border-color:#60a0ff}
.field input[readonly]{color:#60a0ff}
.send-btn{width:100%;padding:12px;background:#1e3a5c;border:1px solid #2a5080;color:#60c0ff;font-size:14px;font-weight:600;border-radius:8px;cursor:pointer;margin-top:4px;transition:all .15s}
.send-btn:active{transform:scale(.98)}

/* Quick buttons */
.quick-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px}
.quick-btn{padding:10px;font-size:12px;background:#1a1f2e;border:1px solid #2a3a5c;color:#9ca3af;border-radius:8px;cursor:pointer;transition:all .15s}
.quick-btn:active{transform:scale(.97)}
.quick-btn.tp1{border-color:#22c55e;color:#22c55e}
.quick-btn.profit{border-color:#60a0ff;color:#60a0ff}
.quick-btn.sl{border-color:#ef4444;color:#ef4444}
.quick-btn.close{border-color:#f0c040;color:#f0c040}
.clear-btn{width:100%;padding:8px;font-size:12px;background:transparent;border:1px solid #374151;color:#4b5563;border-radius:8px;cursor:pointer;margin-bottom:20px}

/* 結果回報 */
.result-section{background:#1a1f2e;border:1px solid #2a3a5c;border-radius:10px;padding:16px;margin-bottom:16px}
.result-section summary{font-size:13px;font-weight:500;cursor:pointer;color:#9ca3af;list-style:none}
.result-section summary::-webkit-details-marker{display:none}
.result-section[open] summary{color:#f0c040;margin-bottom:14px}
.result-toggle{display:flex;gap:8px;margin-bottom:12px}
.result-btn{flex:1;padding:9px;font-size:13px;font-weight:600;border-radius:8px;border:1px solid #374151;background:#111827;color:#6b7280;cursor:pointer;transition:all .15s}
.result-btn.win.active{background:#0f2318;border-color:#22c55e;color:#22c55e}
.result-btn.loss.active{background:#2a0a0a;border-color:#ef4444;color:#ef4444}
.result-send-btn{width:100%;padding:12px;background:#1e3a2a;border:1px solid #22c55e44;color:#22c55e;font-size:14px;font-weight:600;border-radius:8px;cursor:pointer;margin-top:4px}
.result-send-btn:active{transform:scale(.98)}

/* Toast */
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:#1e3a5c;border:1px solid #2a5080;color:#60c0ff;padding:10px 20px;border-radius:20px;font-size:13px;opacity:0;transition:all .3s;pointer-events:none;z-index:999}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style>
</head>
<body>
<div class="container">
  <h1>XAU/USD 交易管理</h1>
  <p class="subtitle">輸入單子參數 → 自動推送 Telegram</p>
  <div class="hint-bar" id="hintBar">⚡ 助教已自動帶入參數，確認後按送出即可！</div>

  <!-- SOP -->
  <p class="section-title">🚦 SOP 進場燈號</p>
  <div class="sop-steps">
    <div class="sop-step active" id="step0">
      <div class="sop-dot"></div>
      <span class="sop-label">⏳ 15分區間整理中</span>
      <button class="sop-btn" onclick="triggerSOP('consolidating',0)">推送 TG</button>
    </div>
    <div class="sop-step" id="step1">
      <div class="sop-dot"></div>
      <span class="sop-label">⚡ 第一根 K 棒突破</span>
      <button class="sop-btn" onclick="triggerSOP('breakout',1)">推送 TG</button>
    </div>
    <div class="sop-step" id="step2">
      <div class="sop-dot"></div>
      <span class="sop-label">🔄 第二根回測確認</span>
      <button class="sop-btn" onclick="triggerSOP('retest',2)">推送 TG</button>
    </div>
    <div class="sop-step" id="step3">
      <div class="sop-dot"></div>
      <span class="sop-label">🎯 第三根進場執行</span>
      <button class="sop-btn" onclick="triggerSOP('entry_confirmed',3)">推送 TG</button>
    </div>
  </div>
  <div class="sop-extra">
    <button class="btn-retest-fail" onclick="triggerSOP('retest_fail', -1)">❌ 回測失敗</button>
    <button class="btn-wait-breakout" onclick="triggerSOP('wait_breakout', -2)">🔁 重新等待突破</button>
  </div>

  <!-- 當前單子 -->
  <p class="section-title">📋 當前單子</p>
  <div id="tradeCard" class="trade-card">
    <p class="no-trade">尚未設定單子</p>
  </div>

  <!-- 設定新單子 -->
  <details class="form-section" id="formDetails">
    <summary>➕ 設定新單子</summary>
    <div class="dir-toggle">
      <button class="dir-btn long active" id="btnLong" onclick="setDir('long')">▲ 多單 LONG</button>
      <button class="dir-btn short" id="btnShort" onclick="setDir('short')">▼ 空單 SHORT</button>
    </div>
    <div class="field"><label>進場價</label><input type="number" id="entry" placeholder="3250.00" step="0.01" oninput="calcTP()"></div>
    <div class="field"><label>停損價</label><input type="number" id="sl" placeholder="3240.00" step="0.01"></div>
    <div class="field"><label>M15 區間距離（自動計算 TP）</label><input type="number" id="range" placeholder="25.00" step="0.01" oninput="calcTP()"></div>
    <div class="field"><label>TP1（自動）</label><input type="number" id="tp1" readonly></div>
    <div class="field"><label>TP2（自動）</label><input type="number" id="tp2" readonly></div>
    <button class="send-btn" onclick="submitTrade()">📤 確認並推送進場提醒到 TG</button>
  </details>

  <!-- 快速推送 -->
  <p class="section-title">⚡ 快速推送提醒</p>
  <div class="quick-grid">
    <button class="quick-btn tp1" onclick="quickPush('tp1')">✅ TP1 達到</button>
    <button class="quick-btn profit" onclick="quickPush('profit')">💰 讓利提醒</button>
    <button class="quick-btn sl" onclick="quickPush('sl_warning')">🚨 停損警告</button>
    <button class="quick-btn close" onclick="quickPush('close')">🏁 本波收手</button>
  </div>
  <button class="clear-btn" onclick="clearTrade()">🗑 清除當前單子</button>

  <!-- 結果回報 -->
  <details class="result-section" id="resultDetails">
    <summary>📋 交易結果回報</summary>
    <div class="result-toggle">
      <button class="result-btn win active" id="rBtnWin" onclick="setResult('win')">✅ 獲利</button>
      <button class="result-btn loss" id="rBtnLoss" onclick="setResult('loss')">❌ 停損</button>
    </div>
    <div class="field"><label>進場價</label><input type="number" id="rEntry" placeholder="3320.00" step="0.01"></div>
    <div class="field"><label>出場價</label><input type="number" id="rExit" placeholder="3335.00" step="0.01"></div>
    <div class="field"><label>損益金額（$）</label><input type="number" id="rPnl" placeholder="150" step="0.01"></div>
    <div class="field"><label>手數（選填）</label><input type="number" id="rLot" placeholder="0.10" step="0.01"></div>
    <div class="field"><label>備註（選填）</label><input type="text" id="rNote" placeholder="M15撐壓回測進場"></div>
    <button class="result-send-btn" onclick="submitResult()">📤 推送結果到 TG</button>
  </details>
</div>

<div class="toast" id="toast"></div>

<script>
let direction = 'long';
let resultType = 'win';

const p = new URLSearchParams(location.search);
if(p.get('direction')||p.get('entry')){
  const d = p.get('direction')||'long';
  setDir(d);
  if(p.get('entry')) document.getElementById('entry').value = p.get('entry');
  if(p.get('sl'))    document.getElementById('sl').value    = p.get('sl');
  if(p.get('range')) document.getElementById('range').value = p.get('range');
  if(p.get('tp1'))   document.getElementById('tp1').value   = p.get('tp1');
  if(p.get('tp2'))   document.getElementById('tp2').value   = p.get('tp2');
  document.getElementById('formDetails').open = true;
  document.getElementById('hintBar').classList.add('show');
}

function setDir(d){
  direction = d;
  document.getElementById('btnLong').classList.toggle('active', d==='long');
  document.getElementById('btnShort').classList.toggle('active', d==='short');
  calcTP();
}

function setResult(r){
  resultType = r;
  document.getElementById('rBtnWin').classList.toggle('active', r==='win');
  document.getElementById('rBtnLoss').classList.toggle('active', r==='loss');
}

function calcTP(){
  const entry = parseFloat(document.getElementById('entry').value);
  const range = parseFloat(document.getElementById('range').value);
  if(!entry||!range) return;
  const mult = direction==='long' ? 1 : -1;
  document.getElementById('tp1').value = (entry + mult*range).toFixed(2);
  document.getElementById('tp2').value = (entry + mult*range*2).toFixed(2);
}

function triggerSOP(type, step){
  // 回測失敗：清除step1,2,3
  if(type === 'retest_fail'){
    document.getElementById('step1').className='sop-step fail';
    document.getElementById('step2').className='sop-step';
    document.getElementById('step3').className='sop-step';
  }
  // 重新等待突破：清除全部
  else if(type === 'wait_breakout'){
    for(let i=0;i<4;i++) document.getElementById('step'+i).className='sop-step'+(i===0?' active':'');
  }
  // 正常SOP步驟
  else {
    document.getElementById('step'+step).classList.add('done');
  }
  fetch('/sop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:type})})
    .then(()=>showToast('✅ 已推送到 TG！'));
}

async function submitTrade(){
  const t = {
    direction,
    entry: document.getElementById('entry').value,
    sl:    document.getElementById('sl').value,
    range: document.getElementById('range').value,
    tp1:   document.getElementById('tp1').value,
    tp2:   document.getElementById('tp2').value
  };
  if(!t.entry||!t.sl||!t.range){showToast('⚠️ 請填寫必要欄位');return;}
  const res = await fetch('/trade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(t)});
  if(res.ok){
    updateTradeCard(t);
    document.getElementById('formDetails').open=false;
    showToast('✅ 進場提醒已推送！');
  }
}

async function quickPush(type){
  await fetch(`/quick`,{method:`POST`,headers:{`Content-Type`:`application/json`},body:JSON.stringify({type:type})});
  showToast(`✅ 提醒已推送！`);
}

async function submitResult(){
  const data = {
    result: resultType,
    entry:  document.getElementById('rEntry').value,
    exit:   document.getElementById('rExit').value,
    pnl:    document.getElementById('rPnl').value,
    lot:    document.getElementById('rLot').value,
    note:   document.getElementById('rNote').value
  };
  if(!data.entry||!data.exit||!data.pnl){showToast('⚠️ 請填寫進出場與損益');return;}
  const res = await fetch('/result',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  if(res.ok){
    showToast('✅ 交易結果已推送！');
    ['rEntry','rExit','rPnl','rLot','rNote'].forEach(id=>document.getElementById(id).value='');
    document.getElementById('resultDetails').open=false;
  }
}

function clearTrade(){
  fetch('/clear',{method:'POST'}).then(()=>{
    document.getElementById('tradeCard').innerHTML='<p class="no-trade">尚未設定單子</p>';
    document.getElementById('tradeCard').className='trade-card';
    showToast('🗑 已清除當前單子');
  });
}

function updateTradeCard(t){
  const isLong = t.direction==='long';
  const card = document.getElementById('tradeCard');
  card.className = 'trade-card '+(isLong?'long':'short');
  card.innerHTML = `
    <div class="trade-header">
      <span class="direction-badge ${isLong?'long':'short'}">${isLong?'▲ 多單 LONG':'▼ 空單 SHORT'}</span>
    </div>
    <div class="trade-row"><span class="trade-label">進場價</span><span class="trade-val">${t.entry}</span></div>
    <div class="trade-row"><span class="trade-label">停損</span><span class="trade-val">${t.sl}</span></div>
    <div class="trade-row"><span class="trade-label">TP1</span><span class="trade-val tp">${t.tp1}</span></div>
    <div class="trade-row"><span class="trade-label">TP2</span><span class="trade-val tp">${t.tp2}</span></div>
  `;
}

function showToast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 2500);
}

fetch('/current').then(r=>r.json()).then(t=>{if(t&&t.entry) updateTradeCard(t);});
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML

@app.route("/trade", methods=["POST"])
def trade():
    global current_trade
    data = request.get_json(force=True)
    current_trade = data
    send_telegram(msg_entry(data))
    return jsonify({"ok": True})

@app.route("/sop", methods=["POST"])
def sop():
    data = request.get_json(force=True)
    t = current_trade
    type_ = data.get("type")
    if type_ == "consolidating":   msg = msg_consolidating(t)
    elif type_ == "breakout":      msg = msg_breakout(t)
    elif type_ == "retest":        msg = msg_retest(t)
    elif type_ == "entry_confirmed": msg = msg_entry_confirmed(t)
    elif type_ == "retest_fail":   msg = msg_retest_fail(t)
    elif type_ == "wait_breakout": msg = msg_wait_breakout(t)
    else: return jsonify({"ok": False}), 400
    send_telegram(msg)
    return jsonify({"ok": True})

@app.route("/quick", methods=["POST"])
def quick():
    data = request.get_json(force=True)
    type_ = data.get("type")
    price = data.get("price", "—")
    t = current_trade if current_trade else {}

    if type_ == "tp1":
        if t:
            msg = msg_tp1(t)
        else:
            msg = "✅ <b>XAU/USD TP1 達到！</b>\n━━━━━━━━━━━━━━━\n⚡ 動作：執行讓利出場"
    elif type_ == "profit":
        if t:
            msg = msg_profit(t, price)
        else:
            msg = "💰 <b>XAU/USD 讓利提醒</b>\n━━━━━━━━━━━━━━━\n建議出場｜一半倉位先走"
    elif type_ == "sl_warning":
        if t:
            msg = msg_sl_warning(t, price)
        else:
            msg = "🚨 <b>XAU/USD 停損警告！</b>\n━━━━━━━━━━━━━━━\n⚠️ 價格接近停損！請確認部位\n❌ 若觸及停損：立即出場勿凹單"
    elif type_ == "close":
        if t:
            msg = msg_close(t)
        else:
            msg = "🏁 <b>XAU/USD 本波結束</b>\n━━━━━━━━━━━━━━━\n📌 等新區間形成再規劃下一波\n🔄 停手觀察，勿追行情"
    else:
        return jsonify({"ok": False}), 400
    send_telegram(msg)
    return jsonify({"ok": True})

@app.route("/result", methods=["POST"])
def result():
    data = request.get_json(force=True)
    msg = msg_result(data)
    ok = send_telegram(msg)
    return jsonify({"ok": ok}), 200 if ok else 500

@app.route("/current", methods=["GET"])
def current():
    return jsonify(current_trade)

@app.route("/clear", methods=["POST"])
def clear():
    global current_trade
    current_trade = {}
    return jsonify({"ok": True})

@app.route("/stats", methods=["GET"])
def stats():
    reset_if_new_day()
    return jsonify(daily_stats)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
