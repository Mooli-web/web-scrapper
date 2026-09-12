#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""داشبورد بازبینی پیش‌بینی مدل — آمار کلی + دسته + اطمینان + اصلاح.

مدل را روی آگهی‌ها اجرا می‌کند، آمار کلی را نشان می‌دهد، و از
کم‌اطمینان‌ترین شروع می‌کند. اصلاحات در DSL نوشته و با `apply --session`
در دفترکل می‌نشیند.

اجرا:
    python predict_ui.py                 # پورت ۸۰۷۸، از باندل
    python predict_ui.py --source db     # از market.db (زنده)
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
STATE = {"items": [], "pos": 0, "dsl": None, "session": "", "decided": set()}


def _ensure_models():
    mp = HUB / "exports" / "ml" / "model_category.pkl"
    mq = HUB / "exports" / "ml" / "model_quality.pkl"
    if not (mp.exists() and mq.exists()):
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
    items = [{**r, **P.predict(r["title"], r["price"])} for r in rows]
    items.sort(key=lambda x: x["category_conf"])
    return items


def _next_item():
    while STATE["pos"] < len(STATE["items"]) and STATE["items"][STATE["pos"]]["id"] in STATE["decided"]:
        STATE["pos"] += 1
    if STATE["pos"] >= len(STATE["items"]):
        return None
    return STATE["items"][STATE["pos"]]


def _append_dsl(line):
    with STATE["dsl"].open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        import os
        os.fsync(fh.fileno())


app = FastAPI(title="داشبورد پالایش")


class Decide(BaseModel):
    id: int
    category: str


@app.get("/api/next")
def api_next():
    it = _next_item()
    if it is None:
        return {"done": True, "decided": len(STATE["decided"]), "total": len(STATE["items"])}
    return {"done": False, "item": {**it, "position": STATE["pos"] + 1,
                                    "total": len(STATE["items"]), "done": len(STATE["decided"])}}


@app.post("/api/decide")
def api_decide(body: Decide):
    if body.category not in CATEGORIES:
        raise HTTPException(400, f"دسته‌ی نامعتبر: {body.category}")
    dsl = f"{body.id} s {body.category}"
    try:
        parsed = rq.parse_dsl(dsl + "\n")
        assert len(parsed) == 1 and parsed[0].get("id") == body.id
    except Exception as e:
        raise HTTPException(400, f"پارسر رد کرد: {e}")
    _append_dsl(dsl)
    STATE["decided"].add(body.id)
    STATE["pos"] += 1
    return {"ok": True, "done": len(STATE["decided"]), "total": len(STATE["items"])}


@app.post("/api/skip")
def api_skip():
    STATE["pos"] += 1
    return {"ok": True}


@app.get("/api/stats")
def api_stats():
    items = STATE["items"]
    cats = Counter(it["category"] for it in items)
    return {
        "total": len(items),
        "decided": len(STATE["decided"]),
        "keep": sum(1 for it in items if it["keep"]),
        "delete": sum(1 for it in items if not it["keep"]),
        "high": sum(1 for it in items if it["category_conf"] >= 0.9),
        "mid": sum(1 for it in items if 0.5 <= it["category_conf"] < 0.9),
        "low": sum(1 for it in items if it["category_conf"] < 0.5),
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
/* سربرگ */
.head{display:flex;align-items:center;gap:14px;margin-bottom:20px}
.head h1{font-size:20px;margin:0;font-weight:800}
.pill{background:var(--card2);border:1px solid var(--line);border-radius:20px;padding:4px 14px;
font-size:12px;color:var(--mut)}
/* کارت‌های آمار */
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px}
@media(max-width:640px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat{background:var(--card);border:1px solid var(--line);border-radius:var(--rad);padding:16px 18px}
.stat .n{font-size:28px;font-weight:800;line-height:1.2}
.stat .l{font-size:12px;color:var(--mut);margin-top:2px}
.stat.ok .n{color:var(--ok)}.stat.bad .n{color:var(--bad)}.stat.amber .n{color:var(--amber)}
.stat.blue .n{color:var(--blue)}
/* توزیع دسته‌ها */
.panel{background:var(--card);border:1px solid var(--line);border-radius:var(--rad);
padding:16px 18px;margin-bottom:14px}
.panel h3{margin:0 0 12px;font-size:13px;color:var(--mut);font-weight:700}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:7px;font-size:12.5px}
.bar-row .name{width:90px;color:var(--fg);text-align:right}
.bar-row .track{flex:1;height:9px;background:#0f141d;border-radius:5px;overflow:hidden}
.bar-row .fill{height:100%;background:linear-gradient(90deg,var(--blue),#7fb0ff);border-radius:5px}
.bar-row .cnt{width:46px;color:var(--mut);text-align:left}
/* کارت بازبینی */
.review{background:var(--card);border:1px solid var(--line);border-radius:var(--rad);padding:22px}
.meta{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.tag{background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:3px 11px;
font-size:12px;color:var(--mut)}.tag b{color:var(--fg)}
.title{font-size:21px;font-weight:700;margin:0 0 14px;line-height:1.6;word-break:break-word}
.pred{display:flex;align-items:center;gap:14px;flex-wrap:wrap;background:var(--card2);
border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-bottom:16px}
.pred .cat{font-size:18px;font-weight:800}
.conf{font-size:30px;font-weight:800}
.conf.hi{color:var(--ok)}.conf.mid{color:var(--amber)}.conf.lo{color:var(--bad)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{background:#1c2431;border:1px solid var(--line);color:var(--mut);border-radius:9px;
padding:8px 13px;cursor:pointer;font-size:13px;transition:.12s}
.chip:hover{color:var(--fg);transform:translateY(-1px)}
.chip.star{box-shadow:inset 0 0 0 1px rgba(37,196,111,.5)}
.chip.on{background:var(--ok);color:#04150c;font-weight:700;border-color:var(--ok)}
.acts{display:flex;gap:10px;margin-top:18px}
.btn{flex:1;border:0;border-radius:12px;padding:13px;font-size:15px;font-weight:700;cursor:pointer;
color:#fff;background:linear-gradient(180deg,#2fd67c,#1cab5f)}
.btn.ghost{flex:0 0 auto;background:var(--card2);border:1px solid var(--line);color:var(--mut)}
.keys{text-align:center;color:var(--dim);font-size:12px;margin-top:16px}
kbd{background:var(--card2);border:1px solid var(--line);border-radius:5px;padding:1px 7px;color:var(--mut)}
.done{text-align:center;padding:50px 20px}
</style></head><body><div class="wrap">
<div class="head"><h1>🧹 داشبورد پالایش</h1><span class="pill">نشست __SESSION__</span>
<span class="pill" id="prog">—</span></div>
<div class="stats" id="stats"></div>
<div class="panel"><h3>توزیع دسته‌های پیش‌بینی‌شده</h3><div id="cats"></div></div>
<div id="root"></div>
<div class="keys"><kbd>V</kbd> تأیید دسته‌ی پیشنهادی · <kbd>1</kbd>…<kbd>0</kbd><kbd>Q</kbd>… انتخاب دسته · <kbd>N</kbd> رد کردن</div>
</div>
<script>
const CATS=__CATS__;const KEYS="1234567890QWERTYUIOP".split("");
let cur=null,cat="";
const fa=n=>Number(n).toLocaleString('fa-IR');
function confCls(c){return c>=0.8?'hi':c>=0.5?'mid':'lo'}
async function loadStats(){const s=await fetch('/api/stats').then(r=>r.json());
 const cards=[['کل آگهی‌ها',s.total,'blue'],['نگه‌داشتنی',s.keep,'ok'],['حذف‌شدنی',s.delete,'bad'],
  ['اطمینان بالا',s.high,'ok'],['اطمینان متوسط',s.mid,'amber'],['نیاز به بازبینی',s.low,'bad']];
 document.getElementById('stats').innerHTML=cards.map(c=>
  `<div class="stat ${c[2]}"><div class="n">${fa(c[1])}</div><div class="l">${c[0]}</div></div>`).join('');
 const entries=Object.entries(s.cats);const max=Math.max(...entries.map(e=>e[1]),1);
 document.getElementById('cats').innerHTML=entries.map(([k,v])=>
  `<div class="bar-row"><span class="name">${k}</span><span class="track"><span class="fill" style="width:${v/max*100}%"></span></span><span class="cnt">${fa(v)}</span></div>`).join('');
 document.getElementById('prog').textContent=`${fa(s.decided)} / ${fa(s.total)} بررسی‌شده`;}
async function next(){await loadStats();const r=await fetch('/api/next').then(r=>r.json());
 if(r.done){document.getElementById('root').innerHTML=`<div class="review done"><h1>✅ تمام شد</h1><p>${fa(r.decided)} اصلاح ثبت شد.</p><p style="color:var(--mut)">بنشان:<br><code>python review_queue.py apply --session __SESSION__</code></p></div>`;return}
 cur=r.item;cat=cur.category;render()}
function render(){const c=cur;const pct=Math.round(c.category_conf*100);
 document.getElementById('root').innerHTML=`<div class="review">
 <div class="meta"><span class="tag">ID <b>${c.id}</b></span>
  <span class="tag"><b>${fa(c.price||0)}</b> تومان</span>
  <span class="tag">حذف؟ <b>${c.keep?'نه':'بله ('+Math.round(c.delete_prob*100)+'٪)'}</b></span></div>
 <div class="title">${esc(c.title)||'(بدون عنوان)'}</div>
 <div class="pred"><span style="color:var(--mut)">پیش‌بینی:</span><span class="cat">${c.category}</span>
  <span class="conf ${confCls(c.category_conf)}">${pct}٪</span>
  <span style="color:var(--dim);font-size:12px">گزینه‌ی دوم: ${c.second}</span></div>
 <div class="chips">${CATS.map((k,i)=>`<button class="chip ${k===cat?'on':''} ${k===c.category?'star':''}" data-c="${k}">${k} <kbd>${KEYS[i]||''}</kbd></button>`).join('')}</div>
 <div class="acts"><button class="btn" id="ok">تأیید → ${cat}</button>
  <button class="btn ghost" id="sk">رد کردن (N)</button></div></div>`;
 document.querySelectorAll('[data-c]').forEach(b=>b.onclick=()=>{cat=b.dataset.c;render()});
 document.getElementById('ok').onclick=send;document.getElementById('sk').onclick=skip}
const esc=s=>String(s||'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
async function send(){const r=await fetch('/api/decide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:cur.id,category:cat})});if(!r.ok){alert((await r.json()).detail);return}next()}
async function skip(){await fetch('/api/skip',{method:'POST'});next()}
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT')return;const k=e.key.toUpperCase();
 if(k==='V')send();else if(k==='N')skip();else{const i=KEYS.indexOf(k);if(i>=0&&i<CATS.length){cat=CATS[i];render()}}});
next();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", default="PREDICT")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8078)
    ap.add_argument("--source", choices=["bundle", "db"], default="bundle")
    args = ap.parse_args()

    _ensure_models()
    STATE["items"] = load_items(args.source)
    STATE["session"] = args.session
    STATE["dsl"] = rq.REVIEW / f"decisions_ui_{args.session}.dsl"
    STATE["dsl"].parent.mkdir(parents=True, exist_ok=True)
    if not STATE["dsl"].exists():
        STATE["dsl"].write_text(f"// بازبینی پیش‌بینی مدل — {args.session}\n", encoding="utf-8")

    globals()["PAGE"] = PAGE.replace("__CATS__", json.dumps(CATEGORIES))
    print(f"🧹 داشبورد پالایش — {len(STATE['items']):,} آگهی، از کم‌اطمینان‌ترین")
    print(f"   ➜  http://{args.host}:{args.port}")
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
