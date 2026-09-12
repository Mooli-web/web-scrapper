#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""داشبورد بازبینی پیش‌بینی مدل — آمار کلی + صف غیرمطمئن‌ها + اصلاح/حذف.

مدل را روی همه‌ی آگهی‌ها اجرا می‌کند و آمار کلی را نشان می‌دهد، ولی **صف
بازبینی فقط کالاهای غیرمطمئن است** (اطمینان دسته < آستانه و حذف خودکارنشده) —
همان‌هایی که auto_purify خودش تصمیم نمی‌گیرد. کنار هر کالا دسته‌ی پیشنهادی
با درصد اطمینان می‌آید؛ یا دسته‌ی درست را می‌نشانی یا حذفش می‌کنی.

اجرا:
    python predict_ui.py                     # آستانه‌ی ۰.۹۰
    python predict_ui.py --threshold 0.95    # صف بزرگ‌تر (اطمینان‌های بالاتر هم بیایند)
    python predict_ui.py --source db         # از market.db
"""
from __future__ import annotations
import argparse, json, sys
from collections import Counter
from pathlib import Path

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import review_queue as rq
import ml_predict as P

CATEGORIES = rq.CATEGORIES
REASONS = [c for c in rq.REASON_CODES if c != "MODEL_REJECT"]   # دلایل انسانی
STATE = {"all": [], "queue": [], "pos": 0, "dsl": None, "session": "",
         "decided": set(), "threshold": 0.9}


def _ensure_models():
    if not (HUB / "exports/ml/model_category.pkl").exists() or \
       not (HUB / "exports/ml/model_quality.pkl").exists():
        print("⚙️  مدل‌ها یافت نشد؛ در حال آموزش (چند دقیقه)…")
        import ml_train_final
        ml_train_final.main()


def load_items(source: str):
    rows = []
    if source == "db":
        from database.db_manager import LocalDatabaseManager
        db = LocalDatabaseManager()
        with db.get_connection() as c:
            for r in c.execute("SELECT id, title_fa, price_toman FROM store_listings"):
                rows.append({"id": r[0], "title": r[1] or "", "price": r[2] or 0})
    else:
        for l in (HUB / "exports/training_bundle/listings.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            rows.append({"id": r["id"], "title": r.get("title_fa") or "",
                         "price": r.get("price_toman") or 0})
    return [{**r, **P.predict(r["title"], r["price"])} for r in rows]


def _build_queue():
    """فقط غیرمطمئن‌ها: نامطلوب نباشد، حذف خودکارنشده، و اطمینان دسته زیر آستانه."""
    t, td = STATE["threshold"], 0.95
    q = [it for it in STATE["all"]
         if it["wanted"] and it["delete_prob"] < td and it["category_conf"] < t]
    q.sort(key=lambda x: x["category_conf"])
    STATE["queue"] = q


def _next_item():
    while STATE["pos"] < len(STATE["queue"]) and STATE["queue"][STATE["pos"]]["id"] in STATE["decided"]:
        STATE["pos"] += 1
    if STATE["pos"] >= len(STATE["queue"]):
        return None
    return STATE["queue"][STATE["pos"]]


def _append_dsl(line):
    with STATE["dsl"].open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        import os
        os.fsync(fh.fileno())


app = FastAPI(title="داشبورد پالایش")


class Decide(BaseModel):
    id: int
    verdict: str            # keep | junk
    category: str = ""
    reason_code: str = ""


@app.get("/api/next")
def api_next():
    it = _next_item()
    if it is None:
        return {"done": True, "decided": len(STATE["decided"]), "total": len(STATE["queue"])}
    return {"done": False, "item": {**it, "position": STATE["pos"] + 1,
                                    "total": len(STATE["queue"]), "done": len(STATE["decided"])}}


@app.post("/api/decide")
def api_decide(body: Decide):
    if body.verdict == "keep":
        if body.category not in CATEGORIES:
            raise HTTPException(400, f"دسته‌ی نامعتبر: {body.category}")
        dsl = f"{body.id} s {body.category}"
    elif body.verdict == "junk":
        if body.reason_code not in REASONS:
            raise HTTPException(400, f"کد دلیل نامعتبر: {body.reason_code}")
        dsl = f"{body.id} j {body.reason_code}"
    else:
        raise HTTPException(400, "verdict نامعتبر")
    try:
        parsed = rq.parse_dsl(dsl + "\n")
        assert len(parsed) == 1 and parsed[0].get("id") == body.id
    except Exception as e:
        raise HTTPException(400, f"پارسر رد کرد: {e}")
    _append_dsl(dsl)
    STATE["decided"].add(body.id)
    STATE["pos"] += 1
    return {"ok": True, "done": len(STATE["decided"]), "total": len(STATE["queue"])}


@app.post("/api/skip")
def api_skip():
    STATE["pos"] += 1
    return {"ok": True}


@app.post("/api/undo")
def api_undo():
    """آخرین تصمیم را از فایل برمی‌دارد — اشتباه زدن کلید اجتناب‌ناپذیر است."""
    if not STATE["decided"]:
        return {"ok": False, "msg": "چیزی برای برگرداندن نیست"}
    p = STATE["dsl"]
    lines = p.read_text(encoding="utf-8").splitlines()
    last = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() and not lines[i].startswith("//"):
            last = i
            break
    if last is None:
        return {"ok": False, "msg": "چیزی برای برگرداندن نیست"}
    removed = lines.pop(last)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        STATE["decided"].discard(int(removed.split()[0]))
    except (ValueError, IndexError):
        pass
    STATE["pos"] = max(0, STATE["pos"] - 1)
    return {"ok": True, "removed": removed, "done": len(STATE["decided"])}


@app.get("/api/stats")
def api_stats():
    a = STATE["all"]
    cats = Counter(it["category"] for it in a)
    return {
        "total": len(a),
        "queue": len(STATE["queue"]),
        "decided": len(STATE["decided"]),
        "keep": sum(1 for it in a if it["keep"]),
        "delete": sum(1 for it in a if not it["keep"]),
        "high": sum(1 for it in a if it["category_conf"] >= 0.9),
        "mid": sum(1 for it in a if 0.5 <= it["category_conf"] < 0.9),
        "low": sum(1 for it in a if it["category_conf"] < 0.5),
        "cats": dict(cats.most_common()),
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE.replace("__SESSION__", STATE["session"])


PAGE = r"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>داشبورد پالایش — __SESSION__</title>
<style>
:root{--bg:#0a0d12;--card:#141922;--card2:#1b2230;--line:#26303f;--fg:#eef2f8;--mut:#8b96a8;
--dim:#616d80;--ok:#25c46f;--bad:#f4574d;--amber:#e8b64c;--blue:#4c8dff;--rad:16px}
*{box-sizing:border-box}html{color-scheme:dark}
body{margin:0;background:radial-gradient(1000px 500px at 80% -10%,#121c2e 0%,var(--bg) 55%);
color:var(--fg);font:15px/1.7 Vazirmatn,Tahoma,system-ui,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:24px 18px 50px}
.head{display:flex;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap}
.head h1{font-size:20px;margin:0;font-weight:800}
.pill{background:var(--card2);border:1px solid var(--line);border-radius:20px;padding:4px 14px;font-size:12px;color:var(--mut)}
.pill b{color:var(--fg)}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px}
@media(max-width:640px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--card);border:1px solid var(--line);border-radius:var(--rad);padding:15px 18px}
.stat .n{font-size:27px;font-weight:800;line-height:1.2}
.stat .l{font-size:12px;color:var(--mut);margin-top:2px}
.stat.ok .n{color:var(--ok)}.stat.bad .n{color:var(--bad)}.stat.amber .n{color:var(--amber)}
.stat.blue .n{color:var(--blue)}.stat.q{border-color:rgba(232,182,76,.5);background:rgba(232,182,76,.06)}
.stat.q .n{color:var(--amber)}
.panel{background:var(--card);border:1px solid var(--line);border-radius:var(--rad);padding:16px 18px;margin-bottom:14px}
.panel h3{margin:0 0 12px;font-size:13px;color:var(--mut);font-weight:700}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:7px;font-size:12.5px}
.bar-row .name{width:96px;text-align:right}
.bar-row .track{flex:1;height:9px;background:#0f141d;border-radius:5px;overflow:hidden}
.bar-row .fill{height:100%;background:linear-gradient(90deg,var(--blue),#7fb0ff);border-radius:5px}
.bar-row .cnt{width:48px;color:var(--mut);text-align:left}
.review{background:var(--card);border:1px solid var(--line);border-radius:var(--rad);padding:22px}
.meta{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.tag{background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:3px 11px;font-size:12px;color:var(--mut)}.tag b{color:var(--fg)}
.title{font-size:21px;font-weight:700;margin:0 0 14px;line-height:1.6;word-break:break-word}
.pred{display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:13px 18px;margin-bottom:18px}
.pred .cat{font-size:18px;font-weight:800}
.conf{font-size:29px;font-weight:800}.conf.hi{color:var(--ok)}.conf.mid{color:var(--amber)}.conf.lo{color:var(--bad)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:760px){.cols{grid-template-columns:1fr}}
.box{border:1px solid var(--line);border-radius:12px;padding:14px;background:var(--card2)}
.box.ok{background:rgba(37,196,111,.06);border-color:rgba(37,196,111,.3)}
.box.bad{background:rgba(244,87,77,.05);border-color:rgba(244,87,77,.3)}
.box h4{margin:0 0 10px;font-size:13px;display:flex;gap:7px;align-items:center}
.box.ok h4{color:var(--ok)}.box.bad h4{color:var(--bad)}
.box h4 .sub{color:var(--dim);font-weight:400;font-size:11px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{background:#1c2431;border:1px solid var(--line);color:var(--mut);border-radius:9px;padding:7px 12px;cursor:pointer;font-size:12.5px;transition:.12s}
.chip:hover{color:var(--fg);transform:translateY(-1px)}
.chip.star{box-shadow:inset 0 0 0 1px rgba(37,196,111,.5)}
.chip.on{background:var(--ok);color:#04150c;font-weight:700;border-color:var(--ok)}
.chip.onr{background:var(--bad);color:#fff;font-weight:700;border-color:var(--bad)}
.acts{display:flex;gap:10px;margin-top:18px}
.btn{flex:1;border:0;border-radius:12px;padding:13px;font-size:15px;font-weight:700;cursor:pointer;color:#fff}
.btn.v{background:linear-gradient(180deg,#2fd67c,#1cab5f)}
.btn.j{background:linear-gradient(180deg,#ff6a5f,#e04238)}
.btn.ghost{flex:0 0 auto;background:var(--card2);border:1px solid var(--line);color:var(--mut)}
.keys{text-align:center;color:var(--dim);font-size:12px;margin-top:16px}
kbd{background:var(--card2);border:1px solid var(--line);border-radius:5px;padding:1px 7px;color:var(--mut)}
.done{text-align:center;padding:50px 20px}
</style></head><body><div class="wrap">
<div class="head"><h1>🧹 داشبورد پالایش</h1><span class="pill">نشست __SESSION__</span>
<span class="pill">صف بررسی: <b id="qsize">—</b></span><span class="pill" id="prog">—</span></div>
<div class="stats" id="stats"></div>
<div class="panel"><h3>توزیع دسته‌های پیش‌بینی‌شده (کل داده)</h3><div id="cats"></div></div>
<div id="root"></div>
<div class="keys"><kbd>V</kbd> تأیید دسته · <kbd>J</kbd> حذف با دلیل انتخابی · <kbd>1</kbd>…<kbd>0</kbd><kbd>Q</kbd>… دسته · <kbd>A</kbd><kbd>B</kbd>… دلیل · <kbd>N</kbd> رد · <kbd>Z</kbd> برگرداندن آخری</div>
</div>
<script>
const CATS=__CATS__, REASONS=__REASONS__;
const KEYS="1234567890QWERTYUIOP".split(""), RKEYS="ABCDFGHKLMSX".split("");
let cur=null,cat="",reason=REASONS[0];
const fa=n=>Number(n).toLocaleString('fa-IR');
function confCls(c){return c>=0.8?'hi':c>=0.5?'mid':'lo'}
async function loadStats(){const s=await fetch('/api/stats').then(r=>r.json());
 const cards=[['کل آگهی‌ها',s.total,'blue'],['صف غیرمطمئن‌ها',s.queue,'q'],['نگه‌داشتنی',s.keep,'ok'],
  ['حذف‌شدنی',s.delete,'bad'],['اطمینان بالا',s.high,'ok'],['اطمینان متوسط',s.mid,'amber']];
 document.getElementById('stats').innerHTML=cards.map(c=>
  `<div class="stat ${c[2]}"><div class="n">${fa(c[1])}</div><div class="l">${c[0]}</div></div>`).join('');
 const e=Object.entries(s.cats);const mx=Math.max(...e.map(x=>x[1]),1);
 document.getElementById('cats').innerHTML=e.map(([k,v])=>
  `<div class="bar-row"><span class="name">${k}</span><span class="track"><span class="fill" style="width:${v/mx*100}%"></span></span><span class="cnt">${fa(v)}</span></div>`).join('');
 document.getElementById('qsize').textContent=fa(s.queue);
 document.getElementById('prog').textContent=`${fa(s.decided)} / ${fa(s.queue)} بررسی‌شده`;}
async function next(){await loadStats();const r=await fetch('/api/next').then(r=>r.json());
 if(r.done){document.getElementById('root').innerHTML=`<div class="review done"><h1>✅ صف تمام شد</h1><p>${fa(r.decided)} تصمیم ثبت شد.</p><p style="color:var(--mut)">بنشان:<br><code>python review_queue.py apply --session __SESSION__</code></p></div>`;return}
 cur=r.item;cat=cur.category;reason=REASONS[0];render()}
function render(){const c=cur;const pct=Math.round(c.category_conf*100);
 document.getElementById('root').innerHTML=`<div class="review">
 <div class="meta"><span class="tag">ID <b>${c.id}</b></span><span class="tag"><b>${fa(c.price||0)}</b> تومان</span>
  <span class="tag">حذف خودکار؟ <b>${c.delete_prob>=0.95?'بله':'نه'} (${Math.round(c.delete_prob*100)}٪)</b></span></div>
 <div class="title">${esc(c.title)||'(بدون عنوان)'}</div>
 <div class="pred"><span style="color:var(--mut)">پیش‌بینی مدل:</span><span class="cat">${c.category}</span>
  <span class="conf ${confCls(c.category_conf)}">${pct}٪</span>
  <span style="color:var(--dim);font-size:12px">گزینه‌ی دوم: ${c.second}</span></div>
 <div class="cols">
  <section class="box ok"><h4>✅ نگه‌داشتن <span class="sub">دسته‌ی درست</span></h4>
   <div class="chips">${CATS.map((k,i)=>`<button class="chip ${k===cat?'on':''} ${k===c.category?'star':''}" data-c="${k}">${k} <kbd style="opacity:.5">${KEYS[i]||''}</kbd></button>`).join('')}</div></section>
  <section class="box bad"><h4>🗑 حذف <span class="sub">دلیل</span></h4>
   <div class="chips">${REASONS.map(k=>`<button class="chip ${k===reason?'onr':''}" data-r="${k}">${k} <kbd style="opacity:.5">${RKEYS[REASONS.indexOf(k)]||''}</kbd></button>`).join('')}</div></section>
 </div>
 <div class="acts"><button class="btn v" id="bv">تأیید → ${cat}</button>
  <button class="btn j" id="bj">حذف ← ${reason}</button>
  <button class="btn ghost" id="bn">رد (N)</button>
  <button class="btn ghost" id="bu">↶ برگردان (Z)</button></div></div>`;
 document.querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>{cat=b.dataset.c;render()});
 document.querySelectorAll('[data-r]').forEach(b=>b.onclick=()=>{reason=b.dataset.r;render()});
 document.getElementById('bv').onclick=()=>send('keep');document.getElementById('bj').onclick=()=>send('junk');
 document.getElementById('bn').onclick=skip;document.getElementById('bu').onclick=undo}
const esc=s=>String(s||'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
async function send(v){const body=v==='keep'?{id:cur.id,verdict:'keep',category:cat}:{id:cur.id,verdict:'junk',reason_code:reason};
 const r=await fetch('/api/decide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!r.ok){alert((await r.json()).detail);return}next()}
async function skip(){await fetch('/api/skip',{method:'POST'});next()}
async function undo(){const r=await fetch('/api/undo',{method:'POST'}).then(r=>r.json());if(!r.ok)return;next()}
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;const k=e.key.toUpperCase();
 if(k==='V')send('keep');else if(k==='J')send('junk');else if(k==='N')skip();else if(k==='Z')undo();
 else{const i=KEYS.indexOf(k);if(i>=0&&i<CATS.length){cat=CATS[i];render();}
  else{const r=RKEYS.indexOf(k);if(r>=0&&r<REASONS.length){reason=REASONS[r];render();}}}});
next();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default="PREDICT")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8078)
    ap.add_argument("--source", choices=["bundle", "db"], default="bundle")
    ap.add_argument("--threshold", type=float, default=0.9,
                    help="اطمینان دسته زیر این → صف بازبینی (پیش‌فرض ۰.۹۰)")
    args = ap.parse_args()

    _ensure_models()
    STATE["all"] = load_items(args.source)
    STATE["threshold"] = args.threshold
    _build_queue()
    STATE["session"] = args.session
    STATE["dsl"] = rq.REVIEW / f"decisions_ui_{args.session}.dsl"
    STATE["dsl"].parent.mkdir(parents=True, exist_ok=True)
    if not STATE["dsl"].exists():
        STATE["dsl"].write_text(f"// بازبینی پیش‌بینی مدل — {args.session}\n", encoding="utf-8")
    else:
        # از قبل تصمیم‌گرفته‌ها را بار کن تا بعد از بستن/بازکردن دوباره نشان ندهد
        for line in STATE["dsl"].read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                STATE["decided"].add(int(line.split()[0]))
            except (ValueError, IndexError):
                pass
        print(f"   ↻ {len(STATE['decided']):,} تصمیم قبلی از فایل بار شد (دوباره نشان داده نمی‌شوند)")

    globals()["PAGE"] = PAGE.replace("__CATS__", json.dumps(CATEGORIES)) \
                            .replace("__REASONS__", json.dumps(REASONS))
    print(f"🧹 داشبورد پالایش — {len(STATE['all']):,} آگهی، صف غیرمطمئن‌ها: {len(STATE['queue']):,}")
    print(f"   آستانه‌ی اطمینان: {args.threshold} (زیر آن → صف بازبینی)")
    print(f"   ➜  http://{args.host}:{args.port}")
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
