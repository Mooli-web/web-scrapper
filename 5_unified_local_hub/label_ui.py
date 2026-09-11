#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""رابط برچسب‌زنی انسانی — همان دفترکل، با سرعت صفحه‌کلید.

چرا این فایل وجود دارد
-----------------------
بازبینی آگهی‌به‌آگهی در چت ۳۰۰ سطر در هر نشست جلو می‌رفت؛ برای ۹٬۸۳۲ آگهی
باقی یعنی ~۳۳ نشست دیگر. یک انسان با صفحه‌کلید ۶۰۰ تا ۹۰۰ سطر در ساعت
برچسب می‌زند، یعنی ۱۱ تا ۱۶ ساعت. این ابزار همان کار را به انسان می‌دهد.

این ابزار **مسیر حسابرسی را دور نمی‌زند**. هر کلید که بزنی یک سطر DSL به
`exports/review/decisions_ui_<برچسب>.dsl` اضافه و fsync می‌شود. یعنی:
  - قطع برق/بستن مرورگر هیچ چیز را از بین نمی‌برد؛
  - بازکردن دوباره از همان‌جا ادامه می‌دهد؛
  - نشاندن رأی‌ها با همان `apply --session …` انجام می‌شود، پس دفترکل
    (decisions.jsonl) تنها منبع حقیقت می‌ماند و ممیزی کور هم کار می‌کند.

اجرا:
    python label_ui.py --session S33            # پیش‌فرض پورت ۸۰۷۷
    python label_ui.py --session S33 --port 9000 --order risk
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import review_queue as rq  # noqa: E402

try:
    from core.taxonomy import category_label, normalize_category
except ImportError:  # pragma: no cover
    from taxonomy import category_label, normalize_category

CATEGORIES = rq.CATEGORIES
REASON_CODES = rq.REASON_CODES

STATE = {
    "queue": [],       # ردیف‌های بازبینی‌نشده، به ترتیبِ پیمایش
    "labeled": {},     # id -> سطر DSL
    "order": [],       # id ها به ترتیب پیمایش
    "pos": 0,
    "dsl_path": None,
    "session": "",
}


# ---------------------------------------------------------------------------
# داده
# ---------------------------------------------------------------------------
def load(order: str, session: str, dsl_path: Path) -> None:
    """صف را می‌سازد، رأی‌های قبلی را برمی‌دارد، و فایل DSL را ادامه می‌دهد."""
    if not (HUB / "exports" / "review" / "queue.jsonl").exists():
        raise SystemExit("❌ اول `python review_queue.py build` را اجرا کن")

    queue = rq._load("queue.jsonl")
    decided = rq._decided_ids()
    todo = [x for x in queue if x["id"] not in decided]

    # رأی‌هایی که در نشست‌های قبلیِ همین ابزار زده شده‌اند ولی هنوز apply نشده‌اند
    labeled: dict[int, str] = {}
    if dsl_path.exists():
        for line in dsl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                labeled[int(line.split()[0])] = line
            except (ValueError, IndexError):
                continue

    if order == "risk":
        # وقت انسان جایی خرج شود که شک بیشتر است: برچسب قبلیِ «رد» اول.
        def key(x):
            rejected = 0 if "reject" in (x.get("status") or "").lower() else 1
            return (rejected, x.get("store") or "", -(x.get("price") or 0))
        todo.sort(key=key)

    STATE["queue"] = {x["id"]: x for x in todo}
    STATE["labeled"] = labeled
    STATE["order"] = [x["id"] for x in todo]
    STATE["pos"] = 0
    STATE["dsl_path"] = dsl_path
    STATE["session"] = session
    dsl_path.parent.mkdir(parents=True, exist_ok=True)
    if not dsl_path.exists():
        dsl_path.write_text(
            f"// برچسب‌زنی انسانی — نشست {session}\n"
            f"// هر سطر با label_ui.py نوشته شده؛ با apply --session {session} بنشان.\n",
            encoding="utf-8")


def _next_row():
    """اولین ردیفی که هنوز در این نشست برچسب نخورده."""
    order, labeled = STATE["order"], STATE["labeled"]
    while STATE["pos"] < len(order) and order[STATE["pos"]] in labeled:
        STATE["pos"] += 1
    if STATE["pos"] >= len(order):
        return None
    return STATE["queue"][order[STATE["pos"]]]


def _shape(row) -> dict:
    title = row.get("title") or ""
    clean = rq.strip_invisible(title)
    suggest = normalize_category(None, clean)
    return {
        "id": row["id"],
        "title": clean,
        "price": row.get("price") or 0,
        "store": row.get("store") or "",
        "tier": row.get("tier") or "",
        "status": row.get("status") or "",
        "suggest": suggest,
        "suggest_label": category_label(suggest),
        "oos_hint": (rq.oos_match(clean) or [None])[0],
        "position": STATE["pos"] + 1,
        "total": len(STATE["order"]),
        "done": len(STATE["labeled"]),
    }


def _append_dsl(line: str) -> None:
    """یک سطر را می‌نویسد و روی دیسک محکم می‌کند — قطع برق چیزی را نمی‌برد."""
    p = STATE["dsl_path"]
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
        import os
        os.fsync(fh.fileno())


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
app = FastAPI(title="برچسب‌زنی انسانی")


class Label(BaseModel):
    id: int
    verdict: str            # verify | junk
    category: str = ""
    reason_code: str = ""
    note: str = ""


@app.get("/api/item")
def api_item():
    row = _next_row()
    if row is None:
        return {"done": True, "labeled": len(STATE["labeled"]),
                "total": len(STATE["order"])}
    return {"done": False, "item": _shape(row)}


@app.post("/api/label")
def api_label(body: Label):
    row = STATE["queue"].get(body.id)
    if row is None:
        raise HTTPException(404, "این آگهی در صف بازبینی‌نشده نیست")
    if body.id in STATE["labeled"]:
        raise HTTPException(409, "قبلاً در این نشست برچسب خورده")

    note = (body.note or "").replace("#", "").replace("\n", " ").strip()
    if body.verdict == "verify":
        if body.category not in CATEGORIES:
            raise HTTPException(400, f"دسته‌ی نامعتبر: {body.category}")
        dsl = f"{body.id} s {body.category}"
        if note:
            dsl += f" # {note}"
    elif body.verdict == "junk":
        if body.reason_code not in REASON_CODES:
            raise HTTPException(400, f"کد دلیل نامعتبر: {body.reason_code}")
        dsl = f"{body.id} j {body.reason_code}"
        dsl += f" # {note}" if note else " # برچسب‌زنی انسانی"
    else:
        raise HTTPException(400, f"verdict نامعتبر: {body.verdict}")

    # قبل از نوشتن، پارسر خودِ review_queue را روی سطر امتحان کن تا سطر کج
    # هرگز روی دیسک ننشیند.
    try:
        parsed = rq.parse_dsl(dsl + "\n")
        assert len(parsed) == 1 and parsed[0].get("id") == body.id, parsed
    except Exception as exc:
        raise HTTPException(400, f"پارسر DSL رد کرد: {exc}")

    _append_dsl(dsl)
    STATE["labeled"][body.id] = dsl
    STATE["pos"] += 1
    return {"ok": True, "dsl": dsl, "done": len(STATE["labeled"]),
            "total": len(STATE["order"])}


@app.post("/api/undo")
def api_undo():
    """آخرین سطر را از فایل برمی‌دارد — چون اشتباه زدن کلید اجتناب‌ناپذیر است."""
    if not STATE["labeled"]:
        return {"ok": False, "msg": "چیزی برای برگرداندن نیست"}
    p = STATE["dsl_path"]
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
        STATE["labeled"].pop(int(removed.split()[0]), None)
    except (ValueError, IndexError):
        pass
    STATE["pos"] = max(0, STATE["pos"] - 1)
    return {"ok": True, "removed": removed, "done": len(STATE["labeled"])}


@app.get("/api/stats")
def api_stats():
    return {
        "session": STATE["session"],
        "dsl": str(STATE["dsl_path"]),
        "labeled": len(STATE["labeled"]),
        "total": len(STATE["order"]),
        "verify": sum(1 for v in STATE["labeled"].values() if " s " in v),
        "junk": sum(1 for v in STATE["labeled"].values() if " j " in v),
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE.replace("__SESSION__", STATE["session"]) \
               .replace("__DSL__", str(STATE["dsl_path"]))


PAGE = r"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>برچسب‌زنی — نشست __SESSION__</title>
<style>
:root{--bg:#0f1115;--card:#181c24;--line:#2a3040;--fg:#e8ecf4;--mut:#8b95a8;
--ok:#2ecc71;--bad:#ff5d5d;--acc:#4c8dff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.7 Vazirmatn,Tahoma,system-ui,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:20px}
.bar{display:flex;gap:14px;align-items:center;flex-wrap:wrap;
padding:10px 14px;background:var(--card);border:1px solid var(--line);
border-radius:10px;margin-bottom:16px;font-size:13px;color:var(--mut)}
.bar b{color:var(--fg)}
.prog{flex:1;min-width:140px;height:6px;background:#232936;border-radius:3px;overflow:hidden}
.prog i{display:block;height:100%;background:var(--acc);width:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}
h1{font-size:22px;margin:0 0 10px;line-height:1.5;word-break:break-word}
.meta{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}
.tag{background:#232936;border:1px solid var(--line);border-radius:8px;
padding:4px 10px;font-size:13px;color:var(--mut)}
.tag b{color:var(--fg)}
.hint{background:#2a2416;border:1px solid #5a4a1e;color:#e8c86a;
border-radius:8px;padding:8px 12px;font-size:13px;margin-bottom:14px}
.lbl{font-size:12px;color:var(--mut);margin:14px 0 6px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{background:#232936;border:1px solid var(--line);color:var(--mut);
border-radius:8px;padding:6px 11px;cursor:pointer;font-size:13px;font-family:inherit}
.chip:hover{border-color:var(--acc);color:var(--fg)}
.chip.on{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
.chip kbd{opacity:.55;font-size:10px;margin-inline-start:5px}
.acts{display:flex;gap:12px;margin-top:22px}
.btn{flex:1;border:0;border-radius:12px;padding:16px;font-size:17px;font-weight:700;
cursor:pointer;font-family:inherit;color:#fff}
.btn small{display:block;font-size:11px;font-weight:400;opacity:.75;margin-top:2px}
.v{background:var(--ok)}.j{background:var(--bad)}
.v:hover{filter:brightness(1.1)}.j:hover{filter:brightness(1.1)}
.ghost{background:#232936;border:1px solid var(--line);color:var(--mut);flex:0 0 auto}
input[type=text]{width:100%;background:#0f1319;border:1px solid var(--line);
color:var(--fg);border-radius:8px;padding:9px 12px;font-family:inherit;font-size:14px}
.done{text-align:center;padding:60px 20px}
.keys{margin-top:16px;font-size:12px;color:var(--mut);line-height:2}
.keys kbd{background:#232936;border:1px solid var(--line);border-radius:4px;
padding:1px 6px;margin:0 2px}
</style></head><body><div class="wrap">
<div class="bar">
  <span>نشست <b>__SESSION__</b></span>
  <span>برچسب‌خورده <b id="done">0</b> / <b id="total">0</b></span>
  <span style="color:var(--ok)">تأیید <b id="nV">0</b></span>
  <span style="color:var(--bad)">حذف <b id="nJ">0</b></span>
  <div class="prog"><i id="prog"></i></div>
</div>
<div id="root"></div>
<div class="keys">
  <kbd>V</kbd> تأیید با دسته‌ی انتخابی &nbsp; <kbd>J</kbd> حذف با دلیل انتخابی
  &nbsp; <kbd>1</kbd>…<kbd>9</kbd><kbd>0</kbd><kbd>Q</kbd>… انتخاب دسته
  &nbsp; <kbd>N</kbd> رد کردن &nbsp; <kbd>Z</kbd> برگرداندن آخری
</div>
</div>
<script>
const CATS=__CATS__, REASONS=__REASONS__;
let cur=null, cat="", reason=REASONS[0], note="", busy=false;
const KEYS="1234567890QWERTYUIOP".split("");
const $=id=>document.getElementById(id);

async function stats(){const r=await fetch('/api/stats').then(r=>r.json());
  $('done').textContent=r.labeled; $('total').textContent=r.total;
  $('nV').textContent=r.verify; $('nJ').textContent=r.junk;
  $('prog').style.width=(r.total? r.labeled/r.total*100:0)+'%';}

async function next(){
  const r=await fetch('/api/item').then(r=>r.json());
  if(r.done){$('root').innerHTML=`<div class="card done"><h1>✅ تمام شد</h1>
    <p>${r.labeled} برچسب در این نشست نوشته شد.</p>
    <p style="color:var(--mut)">حالا بنشان:<br><code>python review_queue.py apply --session __SESSION__</code></p></div>`;
    stats(); return;}
  cur=r.item; cat=cur.suggest; reason=REASONS[0]; note="";
  render(); stats();
}

function render(){
  const c=cur;
  $('root').innerHTML=`<div class="card">
    <div class="meta">
      <span class="tag">id <b>${c.id}</b></span>
      <span class="tag">قیمت <b>${(c.price||0).toLocaleString('fa-IR')}</b> تومان</span>
      <span class="tag">فروشگاه <b>${c.store||'—'}</b></span>
      <span class="tag">لایه <b>${c.tier||'—'}</b></span>
      <span class="tag">پیشنهاد تاکسونومی <b>${c.suggest_label}</b></span>
    </div>
    <h1>${esc(c.title)||'<i style="color:var(--mut)">(بدون عنوان)</i>'}</h1>
    ${c.oos_hint?`<div class="hint">⚠️ پیش‌فیلتر این را ${c.oos_hint} می‌داند — اگر موافقی <kbd>J</kbd> با دلیل OUT_OF_SCOPE.</div>`:''}
    <div class="lbl">دسته (برای تأیید)</div>
    <div class="chips">${CATS.map((k,i)=>
      `<button class="chip ${k===cat?'on':''}" data-cat="${k}">${k}<kbd>${KEYS[i]||''}</kbd></button>`).join('')}</div>
    <div class="lbl">دلیل (برای حذف)</div>
    <div class="chips">${REASONS.map(k=>
      `<button class="chip ${k===reason?'on':''}" data-rsn="${k}">${k}</button>`).join('')}</div>
    <div class="lbl">یادداشت اختیاری (داده‌ی آموزشی)</div>
    <input type="text" id="note" placeholder="چرا؟ یک جمله که بعداً برای آموزش مدل به درد بخورد" value="${esc(note)}">
    <div class="acts">
      <button class="btn v" id="bv">تأیید → ${cat}<small>V</small></button>
      <button class="btn j" id="bj">حذف ← ${reason}<small>J</small></button>
      <button class="btn ghost" id="bn">رد کردن<small>N</small></button>
      <button class="btn ghost" id="bz">↶<small>Z</small></button>
    </div></div>`;
  document.querySelectorAll('[data-cat]').forEach(b=>b.onclick=()=>{cat=b.dataset.cat;render();});
  document.querySelectorAll('[data-rsn]').forEach(b=>b.onclick=()=>{reason=b.dataset.rsn;render();});
  $('bv').onclick=()=>send('verify'); $('bj').onclick=()=>send('junk');
  $('bn').onclick=()=>skip(); $('bz').onclick=undo;
  $('note').oninput=e=>{note=e.target.value;};
}

const esc=s=>String(s||'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));

async function send(verdict){
  if(busy||!cur) return; busy=true;
  const body={id:cur.id,verdict,category:cat,reason_code:reason,note};
  const r=await fetch('/api/label',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)});
  busy=false;
  if(!r.ok){alert((await r.json()).detail); return;}
  next();
}
async function skip(){ if(!cur) return; cur=null;
  const r=await fetch('/api/item').then(r=>r.json());
  if(r.done) return next(); cur=r.item; cat=cur.suggest; render(); }
async function undo(){ await fetch('/api/undo',{method:'POST'}); next(); }

document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'){ if(e.key==='Escape') e.target.blur(); return; }
  const k=e.key.toUpperCase();
  if(k==='V') send('verify'); else if(k==='J') send('junk');
  else if(k==='N') skip(); else if(k==='Z') undo();
  else{ const i=KEYS.indexOf(k); if(i>=0&&i<CATS.length){cat=CATS[i];render();} }
});
next();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", required=True, help="برچسب نشست، مثلاً S33")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--order", choices=["queue", "risk"], default="queue",
                    help="risk: آن‌هایی که برچسب قبلی‌شان «رد» بوده اول")
    ap.add_argument("--dsl", default=None,
                    help="مسیر فایل DSL (پیش‌فرض exports/review/decisions_ui_<برچسب>.dsl)")
    args = ap.parse_args()

    dsl = Path(args.dsl) if args.dsl else (
        rq.REVIEW / f"decisions_ui_{args.session}.dsl")
    load(args.order, args.session, dsl)

    import json as _json
    globals()["PAGE"] = PAGE.replace("__CATS__", _json.dumps(CATEGORIES)) \
                            .replace("__REASONS__", _json.dumps(REASON_CODES))

    todo = len(STATE["order"]) - len(STATE["labeled"])
    print(f"🏷️  برچسب‌زنی انسانی — نشست {args.session}")
    print(f"   صف بازبینی‌نشده: {len(STATE['order']):,} | "
          f"از قبل برچسب‌خورده: {len(STATE['labeled']):,} | باقی: {todo:,}")
    print(f"   فایل DSL: {dsl}")
    print(f"   بعد از پایان:  python review_queue.py apply --session {args.session} "
          f"--file {dsl.name}")
    print(f"   ➜  http://{args.host}:{args.port}")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
