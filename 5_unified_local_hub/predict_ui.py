#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI بازبینی پیش‌بینی‌های مدل — دسته + درصد اطمینان + اصلاح دستی.

مدل را روی آگهی‌ها اجرا می‌کند، دسته و **درصد اطمینان** را کنار هر کدام
نشان می‌دهد، و از کم‌اطمینان‌ترین شروع می‌کند (جایی که احتمال خطای مدل
بیشتر است). با یک کلید دسته‌ی درست را می‌نشانی؛ اصلاحات در DSL نوشته و با
`apply --session` در دفترکل می‌نشیند (هم داده را درست می‌کند هم خوراک
آموزش مجدد می‌شود).

اجرا:
    python predict_ui.py                 # پورت ۸۰۷۸
    python predict_ui.py --source db     # از market.db (زنده) به‌عنوان منبع
اگر مدل‌ها نباشند، اول ml_train_final.py اجرا و ساخته می‌شوند.
"""
from __future__ import annotations
import argparse, json, sys
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
    """آگهی‌ها را از bundle یا market.db می‌خواند و پیش‌بینی مدل را رویشان می‌گذارد."""
    rows = []
    if source == "db":
        from database.db_manager import LocalDatabaseManager
        db = LocalDatabaseManager()
        with db.get_connection() as c:
            cur = c.execute("SELECT id, title_fa, price_toman FROM store_listings")
            for r in cur.fetchall():
                rows.append({"id": r[0], "title": r[1] or "", "price": r[2] or 0})
    else:
        for l in (HUB / "exports/training_bundle/listings.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            rows.append({"id": r["id"], "title": r.get("title_fa") or "",
                         "price": r.get("price_toman") or 0})
    items = []
    for r in rows:
        pr = P.predict(r["title"], r["price"])
        items.append({**r, **pr})
    items.sort(key=lambda x: x["category_conf"])   # کم‌اطمینان اول
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


app = FastAPI(title="بازبینی پیش‌بینی مدل")


class Decide(BaseModel):
    id: int
    category: str


@app.get("/api/next")
def api_next():
    it = _next_item()
    if it is None:
        return {"done": True, "decided": len(STATE["decided"]), "total": len(STATE["items"])}
    return {"done": False, "item": {**it, "position": STATE["pos"] + 1,
                                    "total": len(STATE["items"]),
                                    "done": len(STATE["decided"])}}


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


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE.replace("__SESSION__", STATE["session"])


PAGE = r"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>بازبینی پیش‌بینی — __SESSION__</title>
<style>
:root{--bg:#0b0e13;--card:#151a22;--card2:#1b212c;--line:#28303e;--fg:#eef2f8;--mut:#939db0;
--ok:#25c46f;--bad:#f4574d;--amber:#e8b64c;--rad:14px}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.7 Vazirmatn,Tahoma,system-ui,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:22px 16px}
.bar{display:flex;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);
border-radius:var(--rad);padding:10px 16px;margin-bottom:16px;font-size:13px;position:sticky;top:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--rad);padding:24px}
h1{font-size:22px;margin:0 0 14px;line-height:1.6;word-break:break-word}
.pred{display:flex;align-items:center;gap:12px;flex-wrap:wrap;background:var(--card2);
border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin-bottom:16px}
.conf{font-size:26px;font-weight:800}
.conf.hi{color:var(--ok)}.conf.mid{color:var(--amber)}.conf.lo{color:var(--bad)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.chip{background:#1e2531;border:1px solid var(--line);color:var(--mut);border-radius:8px;
padding:7px 12px;cursor:pointer;font-size:13px}
.chip:hover{color:var(--fg)}.chip.star{box-shadow:inset 0 0 0 1px var(--ok)}
.chip.on{background:var(--ok);color:#04150c;font-weight:700;border-color:var(--ok)}
.tag{background:var(--card2);border:1px solid var(--line);border-radius:7px;padding:3px 10px;
font-size:12px;color:var(--mut)}.tag b{color:var(--fg)}
.btn{border:0;border-radius:10px;padding:12px 18px;font-size:15px;font-weight:700;cursor:pointer;
color:#fff;background:linear-gradient(180deg,#2fd67c,#1cab5f);margin-top:18px}
.ghost{background:var(--card2);border:1px solid var(--line);color:var(--mut)}
.keys{text-align:center;color:var(--mut);font-size:12px;margin-top:14px}
kbd{background:var(--card2);border:1px solid var(--line);border-radius:4px;padding:0 6px}
</style></head><body><div class="wrap">
<div class="bar"><b>بازبینی پیش‌بینی — __SESSION__</b>
<span style="flex:1"></span><span id="cnt">۰/۰</span></div>
<div id="root"></div>
<div class="keys"><kbd>V</kbd> تأیید دسته‌ی پیشنهادی مدل · <kbd>1</kbd>…<kbd>0</kbd><kbd>Q</kbd>… انتخاب دسته ·
<kbd>N</kbd> رد کردن</div></div>
<script>
const CATS=__CATS__;const KEYS="1234567890QWERTYUIOP".split("");
let cur=null,cat="";
function confCls(c){return c>=0.8?'hi':c>=0.5?'mid':'lo'}
async function next(){const r=await fetch('/api/next').then(r=>r.json());
 if(r.done){document.getElementById('root').innerHTML='<div class="card"><h1>✅ تمام شد</h1><p>'+r.decided+' اصلاح ثبت شد. حالا بنشان:</p><code>python review_queue.py apply --session __SESSION__ --file decisions_ui___SESSION__.dsl</code></div>';return}
 cur=r.item;cat=cur.category;
 document.getElementById('cnt').textContent=r.item.done+'/'+r.item.total;render()}
function render(){const c=cur;const pct=Math.round(c.category_conf*100);
 document.getElementById('root').innerHTML=`<div class="card">
 <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
  <span class="tag">ID <b>${c.id}</b></span>
  <span class="tag"><b>${(c.price||0).toLocaleString('fa-IR')}</b> تومان</span>
  <span class="tag">حذف؟ <b>${c.keep?'نه':'بله ('+Math.round(c.delete_prob*100)+'٪)'}</b></span></div>
 <h1>${esc(c.title)||'(بدون عنوان)'}</h1>
 <div class="pred"><span>پیش‌بینی مدل:</span><b style="font-size:18px">${c.category}</b>
  <span class="conf ${confCls(c.category_conf)}">${pct}٪</span>
  <span style="color:var(--mut);font-size:12px">گزینه‌ی دوم: ${c.second}</span></div>
 <div class="chips">${CATS.map((k,i)=>`<button class="chip ${k===cat?'on':''} ${k===c.category?'star':''}" data-c="${k}">${k} <kbd style="opacity:.5">${KEYS[i]||''}</kbd></button>`).join('')}</div>
 <button class="btn" id="ok">تأیید → ${cat}</button>
 <button class="btn ghost" id="sk">رد کردن (N)</button></div>`;
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
    ap.add_argument("--source", choices=["bundle", "db"], default="bundle",
                    help="bundle: از training_bundle (قابل‌حمل)؛ db: از market.db (زنده)")
    args = ap.parse_args()

    _ensure_models()
    STATE["items"] = load_items(args.source)
    STATE["session"] = args.session
    STATE["dsl"] = rq.REVIEW / f"decisions_ui_{args.session}.dsl"
    STATE["dsl"].parent.mkdir(parents=True, exist_ok=True)
    if not STATE["dsl"].exists():
        STATE["dsl"].write_text(f"// بازبینی پیش‌بینی مدل — {args.session}\n", encoding="utf-8")

    globals()["PAGE"] = PAGE.replace("__CATS__", json.dumps(CATEGORIES))
    print(f"🤖 بازبینی پیش‌بینی — {len(STATE['items']):,} آگهی، از کم‌اطمینان‌ترین")
    print(f"   فایل اصلاحات: {STATE['dsl']}")
    print(f"   بعد از پایان: python review_queue.py apply --session {args.session} --file {STATE['dsl'].name}")
    print(f"   ➜  http://{args.host}:{args.port}")
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
