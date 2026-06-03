from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

current_trade = {}
sop_status = {"step": 0}

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
    return (f"⏳ <b>XAU/USD 15分整理中</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"關鍵位｜{t['entry']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 等待突破訊號，尚未進場\n"
            f"🔍 持續觀察區間形成")

def msg_breakout(t):
    direction = "向下突破" if t["direction"] == "short" else "向上突破"
    return (f"⚡ <b>XAU/USD 突破訊號！</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{direction} {t['entry']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📌 等待回測確認，準備進場")

def msg_retest(t):
    return (f"🔄 <b>XAU/USD 回測確認！</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"回測 {t['entry']} 守住\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚡ 等待第三根K棒確認進場")

def msg_entry_confirmed(t):
    direction = "多單 LONG ▲" if t["direction"] == "long" else "空單 SHORT ▼"
    return (f"🎯 <b>XAU/USD 第三根進場！</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"方向｜{direction}\n"
            f"進場價｜{t['entry']}\n"
            f"停損｜{t['sl']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎯 TP1｜{t['tp1']}\n"
            f"🎯 TP2｜{t['tp2']}")

HTML = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XAU/USD 交易管理</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Noto+Sans+TC:wght@400;500;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f1117;font-family:'Noto Sans TC',sans-serif;color:#d1d9f0;min-height:100vh;padding:32px 16px;display:flex;flex-direction:column;align-items:center}
.container{width:100%;max-width:480px}
h1{font-size:20px;font-weight:700;color:#f0f4ff;margin-bottom:4px}
.subtitle{font-size:12px;color:#6b7a99;font-family:'IBM Plex Mono',monospace;margin-bottom:28px}
.card{background:#161b27;border:1px solid #232b3e;border-radius:12px;padding:18px 20px;margin-bottom:16px}
.card-title{font-size:11px;font-weight:600;color:#4b5a7a;letter-spacing:1px;text-transform:uppercase;margin-bottom:14px}
.status-empty{font-size:13px;color:#4b5a7a;font-family:'IBM Plex Mono',monospace;text-align:center;padding:8px 0}
.trade-row{display:flex;justify-content:space-between;align-items:center;font-size:13px;margin-bottom:8px}
.trade-label{color:#6b7a99}
.trade-val{font-family:'IBM Plex Mono',monospace;font-weight:600;color:#f0f4ff}
.trade-val.green{color:#34d399}.trade-val.red{color:#f87171}.trade-val.purple{color:#a78bfa}
.dir-group{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:16px}
.dir-btn{padding:10px;border-radius:8px;border:1px solid #232b3e;background:#1e2637;color:#6b7a99;font-size:13px;font-weight:600;cursor:pointer;text-align:center;transition:all 0.2s}
.dir-btn.active-long{background:rgba(52,211,153,0.15);border-color:rgba(52,211,153,0.4);color:#34d399}
.dir-btn.active-short{background:rgba(248,113,113,0.15);border-color:rgba(248,113,113,0.4);color:#f87171}
.input-group{margin-bottom:14px}
label{display:block;font-size:11px;color:#6b7a99;margin-bottom:6px;font-family:'IBM Plex Mono',monospace}
input{width:100%;background:#1e2637;border:1px solid #2a3550;border-radius:8px;padding:10px 14px;font-size:14px;font-family:'IBM Plex Mono',monospace;color:#f0f4ff;outline:none;transition:border-color 0.2s}
input:focus{border-color:#6366f1}
.auto-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.auto-tag{font-size:10px;color:#34d399;font-family:'IBM Plex Mono',monospace;margin-top:4px}
.submit-btn{width:100%;padding:13px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border:none;border-radius:10px;color:#fff;font-size:14px;font-weight:700;cursor:pointer;margin-top:4px;transition:opacity 0.2s}
.submit-btn:hover{opacity:0.85}
.autofill-banner{background:rgba(52,211,153,0.1);border:1px solid rgba(52,211,153,0.3);border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:12px;color:#34d399;font-family:'IBM Plex Mono',monospace;display:none}
.quick-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.quick-btn{padding:10px 8px;border-radius:8px;border:none;font-size:12px;font-weight:600;cursor:pointer;transition:opacity 0.2s;font-family:'Noto Sans TC',sans-serif}
.quick-btn:hover{opacity:0.8}
.btn-tp1{background:rgba(52,211,153,0.15);border:1px solid rgba(52,211,153,0.3);color:#34d399}
.btn-profit{background:rgba(251,191,36,0.15);border:1px solid rgba(251,191,36,0.3);color:#fbbf24}
.btn-sl{background:rgba(248,113,113,0.15);border:1px solid rgba(248,113,113,0.3);color:#f87171}
.btn-close{background:rgba(107,122,153,0.15);border:1px solid rgba(107,122,153,0.3);color:#6b7a99}
.clear-btn{width:100%;padding:9px;background:transparent;border:1px solid #2a3550;border-radius:8px;color:#4b5a7a;font-size:12px;cursor:pointer;margin-top:8px;font-family:'Noto Sans TC',sans-serif}
.clear-btn:hover{border-color:#f87171;color:#f87171}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1e2637;border:1px solid #34d399;color:#34d399;padding:10px 24px;border-radius:8px;font-size:13px;font-family:'IBM Plex Mono',monospace;opacity:0;transition:opacity 0.3s;pointer-events:none;z-index:999;white-space:nowrap}
.toast.show{opacity:1}.toast.error{border-color:#f87171;color:#f87171}
.consolidate-btn{width:100%;padding:10px;background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);border-radius:8px;color:#818cf8;font-size:12px;font-weight:600;cursor:pointer;margin-bottom:12px;font-family:'Noto Sans TC',sans-serif}
.consolidate-btn:hover{opacity:0.8}
.sop-steps{display:flex;flex-direction:column;gap:8px;margin-bottom:14px}
.sop-step{display:flex;align-items:center;gap:12px;padding:10px 14px;border-radius:8px;background:#1e2637;border:1px solid #2a3550}
.sop-step.active{background:rgba(251,191,36,0.1);border-color:rgba(251,191,36,0.3)}
.sop-step.done{background:rgba(52,211,153,0.1);border-color:rgba(52,211,153,0.3)}
.sop-dot{width:10px;height:10px;border-radius:50%;background:#2a3550;flex-shrink:0}
.sop-step.active .sop-dot{background:#fbbf24;box-shadow:0 0 6px #fbbf24}
.sop-step.done .sop-dot{background:#34d399}
.sop-label{font-size:13px;color:#6b7a99;flex:1}
.sop-step.active .sop-label{color:#fbbf24;font-weight:600}
.sop-step.done .sop-label{color:#34d399}
.sop-btn{padding:5px 12px;border-radius:6px;border:none;font-size:11px;font-weight:600;cursor:pointer;font-family:'Noto Sans TC',sans-serif;display:none}
.sop-step.active .sop-btn{display:block;background:rgba(251,191,36,0.2);color:#fbbf24;border:1px solid rgba(251,191,36,0.4)}
</style>
</head>
<body>
<div class="container">
<h1>XAU/USD 交易管理</h1>
<p class="subtitle">輸入單子參數 → 自動推送 Telegram</p>
<div class="autofill-banner" id="autofillBanner">⚡ 助教已自動帶入參數，確認後按送出即可！</div>

<div class="card">
  <div class="card-title">🚦 SOP 進場燈號</div>
  <div class="sop-steps">
    <div class="sop-step" id="step0"><div class="sop-dot"></div><span class="sop-label">等待突破關鍵位</span><button class="sop-btn" onclick="advanceSOP(1)">已突破 ✓</button></div>
    <div class="sop-step" id="step1"><div class="sop-dot"></div><span class="sop-label">第一根 K 棒突破</span><button class="sop-btn" onclick="advanceSOP(2)">已回測 ✓</button></div>
    <div class="sop-step" id="step2"><div class="sop-dot"></div><span class="sop-label">第二根回測確認</span><button class="sop-btn" onclick="advanceSOP(3)">已進場 ✓</button></div>
    <div class="sop-step" id="step3"><div class="sop-dot"></div><span class="sop-label">第三根進場執行</span></div>
  </div>
  <button class="consolidate-btn" onclick="sendConsolidating()">⏳ 15分區間整理中 → 推送到 TG</button>
</div>

<div class="card">
  <div class="card-title">📋 當前單子</div>
  <div id="statusContent"><div class="status-empty">尚未設定單子</div></div>
</div>

<div class="card">
  <div class="card-title">➕ 設定新單子</div>
  <div class="dir-group">
    <div class="dir-btn active-long" id="btnLong" onclick="setDirection('long')">▲ 多單 LONG</div>
    <div class="dir-btn" id="btnShort" onclick="setDirection('short')">▼ 空單 SHORT</div>
  </div>
  <div class="input-group"><label>進場價</label><input type="number" id="entry" placeholder="例：4498.74" step="0.01" oninput="calcTP()"></div>
  <div class="input-group"><label>停損價</label><input type="number" id="sl" placeholder="例：4462.8" step="0.01"></div>
  <div class="input-group"><label>M15 區間距離（自動計算 TP）</label><input type="number" id="range" placeholder="例：32.26" step="0.01" oninput="calcTP()"><div class="auto-tag" id="autoTag"></div></div>
  <div class="auto-row">
    <div class="input-group"><label>TP1（自動）</label><input type="number" id="tp1" placeholder="自動帶入" step="0.01"></div>
    <div class="input-group"><label>TP2（自動）</label><input type="number" id="tp2" placeholder="自動帶入" step="0.01"></div>
  </div>
  <button class="submit-btn" onclick="submitTrade()">📤 確認並推送進場提醒到 TG</button>
</div>

<div class="card">
  <div class="card-title">⚡ 快速推送提醒</div>
  <div class="quick-grid">
    <button class="quick-btn btn-tp1" onclick="sendAlert('tp1')">✅ TP1 達到</button>
    <button class="quick-btn btn-profit" onclick="sendAlert('profit')">💰 讓利提醒</button>
    <button class="quick-btn btn-sl" onclick="sendAlert('sl_warning')">🚨 停損警告</button>
    <button class="quick-btn btn-close" onclick="sendAlert('close')">🏁 本波收手</button>
  </div>
  <button class="clear-btn" onclick="clearTrade()">🗑 清除當前單子</button>
</div>
</div>
<div class="toast" id="toast"></div>
<script>
let direction='long';

window.onload=function(){
  const params=new URLSearchParams(window.location.search);
  if(params.get('entry')){
    const d=params.get('direction')||'long';
    setDirection(d);
    document.getElementById('entry').value=params.get('entry')||'';
    document.getElementById('sl').value=params.get('sl')||'';
    document.getElementById('range').value=params.get('range')||'';
    document.getElementById('tp1').value=params.get('tp1')||'';
    document.getElementById('tp2').value=params.get('tp2')||'';
    if(params.get('range'))document.getElementById('autoTag').textContent='✓ TP1 '+params.get('tp1')+'  TP2 '+params.get('tp2');
    document.getElementById('autofillBanner').style.display='block';
    window.history.replaceState({},'','/');
  }
  loadStatus();
  loadSOP();
}

async function sendConsolidating(){const res=await fetch('/webhook',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'consolidating'})});const data=await res.json();if(data.ok)showToast('✅ 整理中訊號已推送到 TG！');else showToast('❌ 先設定單子再推送',true)}

function updateSOPUI(step){
  for(let i=0;i<4;i++){
    const el=document.getElementById('step'+i);
    el.className='sop-step';
    if(i<step) el.classList.add('done');
    else if(i===step) el.classList.add('active');
  }
}

async function loadSOP(){
  try{
    const res=await fetch('/sop');
    const data=await res.json();
    updateSOPUI(data.step);
  }catch(e){}
}

async function advanceSOP(step){
  const typeMap={1:'breakout',2:'retest',3:'entry_confirmed'};
  await fetch('/webhook',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:typeMap[step]})});
  updateSOPUI(step);
  const labels={1:'突破訊號已推送到 TG！',2:'回測確認已推送到 TG！',3:'進場確認已推送到 TG！'};
  showToast('✅ '+labels[step]);
}

function setDirection(d){direction=d;document.getElementById('btnLong').className='dir-btn'+(d==='long'?' active-long':'');document.getElementById('btnShort').className='dir-btn'+(d==='short'?' active-short':'');calcTP()}
function calcTP(){const entry=parseFloat(document.getElementById('entry').value);const range=parseFloat(document.getElementById('range').value);if(!entry||!range)return;const tp1=direction==='long'?(entry+range).toFixed(2):(entry-range).toFixed(2);const tp2=direction==='long'?(entry+range*2).toFixed(2):(entry-range*2).toFixed(2);document.getElementById('tp1').value=tp1;document.getElementById('tp2').value=tp2;document.getElementById('autoTag').textContent='✓ TP1 '+tp1+'  TP2 '+tp2}
async function submitTrade(){const entry=document.getElementById('entry').value;const sl=document.getElementById('sl').value;const tp1=document.getElementById('tp1').value;const tp2=document.getElementById('tp2').value;const range=document.getElementById('range').value;if(!entry||!sl||!tp1||!tp2){showToast('請填入所有欄位',true);return}const res=await fetch('/set_trade',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({direction,entry,sl,tp1,tp2,range})});const data=await res.json();if(data.ok){showToast('✅ 已儲存並推送進場提醒！');document.getElementById('autofillBanner').style.display='none';loadStatus()}else showToast('❌ 發送失敗',true)}
async function sendAlert(type){const res=await fetch('/webhook',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type,price:'—'})});const data=await res.json();if(data.ok){showToast('✅ 提醒已推送到 TG！');if(type==='close'){loadStatus();loadSOP();}}else showToast(data.error||'❌ 先設定單子再推送',true)}
async function clearTrade(){await fetch('/clear_trade',{method:'POST'});showToast('🗑 單子已清除');loadStatus();updateSOPUI(0)}
async function loadStatus(){const res=await fetch('/trade');const t=await res.json();const el=document.getElementById('statusContent');if(!t.entry){el.innerHTML='<div class="status-empty">尚未設定單子</div>';return}const dirColor=t.direction==='long'?'green':'red';const dirText=t.direction==='long'?'▲ 多單 LONG':'▼ 空單 SHORT';el.innerHTML='<div class="trade-row"><span class="trade-label">方向</span><span class="trade-val '+dirColor+'">'+dirText+'</span></div><div class="trade-row"><span class="trade-label">進場價</span><span class="trade-val">'+t.entry+'</span></div><div class="trade-row"><span class="trade-label">停損</span><span class="trade-val red">'+t.sl+'</span></div><div class="trade-row"><span class="trade-label">TP1</span><span class="trade-val green">'+t.tp1+'</span></div><div class="trade-row"><span class="trade-label">TP2</span><span class="trade-val purple">'+t.tp2+'</span></div>'}
function showToast(msg,isError=false){const t=document.getElementById('toast');t.textContent=msg;t.className='toast show'+(isError?' error':'');setTimeout(()=>{t.className='toast'},3000)}
</script>
</body>
</html>"""

@app.route("/", methods=["GET"])
def index():
    return HTML

@app.route("/set_trade", methods=["POST"])
def set_trade():
    global current_trade, sop_status
    data = request.json
    current_trade = {
        "direction": data.get("direction", "long"),
        "entry": data.get("entry", ""),
        "sl": data.get("sl", ""),
        "tp1": data.get("tp1", ""),
        "tp2": data.get("tp2", ""),
        "range": data.get("range", ""),
    }
    sop_status = {"step": 0}
    send_telegram(msg_entry(current_trade))
    return jsonify({"ok": True, "trade": current_trade})

@app.route("/trade", methods=["GET"])
def get_trade():
    return jsonify(current_trade)

@app.route("/sop", methods=["GET"])
def get_sop():
    return jsonify(sop_status)

@app.route("/clear_trade", methods=["POST"])
def clear_trade():
    global current_trade, sop_status
    current_trade = {}
    sop_status = {"step": 0}
    return jsonify({"ok": True})

@app.route("/webhook", methods=["POST"])
def webhook():
    global current_trade, sop_status
    data = request.json
    alert_type = data.get("type", "")
    price = data.get("price", "N/A")

    if alert_type == "consolidating":
        if current_trade:
            message = msg_consolidating(current_trade)
        else:
            message = ("⏳ <b>XAU/USD 15分區間整理中</b>\n"
                      f"━━━━━━━━━━━━━━━\n"
                      f"📌 等待突破訊號，尚未進場\n"
                      f"🔍 持續觀察區間形成")
        send_telegram(message)
        return jsonify({"ok": True})

    if alert_type == "breakout":
        sop_status["step"] = 1
        if current_trade:
            message = msg_breakout(current_trade)
        else:
            message = ("⚡ <b>XAU/USD 突破訊號！</b>\n"
                      f"━━━━━━━━━━━━━━━\n"
                      f"📌 等待回測確認，準備進場")
        send_telegram(message)
        return jsonify({"ok": True})

    if alert_type == "retest":
        sop_status["step"] = 2
        if current_trade:
            message = msg_retest(current_trade)
        else:
            message = ("🔄 <b>XAU/USD 回測確認！</b>\n"
                      f"━━━━━━━━━━━━━━━\n"
                      f"⚡ 等待第三根K棒確認進場")
        send_telegram(message)
        return jsonify({"ok": True})

    if alert_type == "entry_confirmed":
        sop_status["step"] = 3
        if current_trade:
            message = msg_entry_confirmed(current_trade)
        else:
            message = ("🎯 <b>XAU/USD 第三根進場！</b>\n"
                      f"━━━━━━━━━━━━━━━\n"
                      f"⚡ 進場執行中")
        send_telegram(message)
        return jsonify({"ok": True})

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
        current_trade = {}
        sop_status = {"step": 0}
    else:
        message = f"📊 XAU/USD 警報：{data.get('message', alert_type)}"

    success = send_telegram(message)
    return jsonify({"ok": success})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running", "has_trade": bool(current_trade), "sop_step": sop_status.get("step", 0)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
