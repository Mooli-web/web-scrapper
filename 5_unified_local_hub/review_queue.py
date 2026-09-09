# -*- coding: utf-8 -*-
"""
🧭 صف بازبینی خوشه‌محور — review_queue.py
==========================================
مشکل: ۲۰,۳۴۵ آگهی را نمی‌شود در یک نشست قضاوت کرد. تلاش‌های قبلی به بسته‌های
۸۰۰تایی تقسیم شدند و نیمه‌کاره ماندند چون «کجا بودیم» هیچ‌جا ثبت نمی‌شد.

راه‌حل این اسکریپت — سه اصل:
  ۱) واحد کار «خوشه‌ی عنوان» است، نه آگهی. یک تصمیم روی یک خوشه می‌تواند
     ۱۰۰ آگهی را حل کند.
  ۲) وضعیت در مخزن ثبت می‌شود (decisions.jsonl append-only) نه در چت؛ پس هر
     نشست قابل ازسرگیری است و شکست یک نشست چیزی را از بین نمی‌برد.
  ۳) هر تصمیم با نمونه‌ی شاهد و امکان واگردانی ثبت می‌شود و دقت با ممیزی
     کور اندازه‌گیری می‌شود.

سیاست برچسب‌گذاری (تصمیم‌شده توسط صاحب داده، ۱۴۰۴/۰۶/۱۸):
  • کالای «طرح / کپی / های‌کپی / فیک / replica» = junk و حذف می‌شود، حتی اگر
    سخت‌افزار واقعی باشد — چون مقایسه‌ی قیمت و آموزش مدل را آلوده می‌کند.
  • هر آگهی جدا قضاوت می‌شود: «شرایط» (condition) و قیمت هر آگهی می‌تواند با
    هم‌خوشه‌هایش فرق کند. تصمیم خوشه‌ای فقط وقتی مجاز است که ۱۰۰٪ اعضا خوانده
    شده باشند و یکدست باشند؛ در دفترکل با review_mode ثبت می‌شود.
  • uncertain = از دیتاست آموزش کنار گذاشته می‌شود (نه clean، نه junk). این
    تنها راهی است که نمونه‌ی مبهم مدل را «سردرگم» نکند.

لایه‌ها (هر لایه صف را کوچک‌تر می‌کند):
  L0  برچسب انسانی        → تصمیم قطعی، دست نمی‌خورد
  L1  ارث از canonical_key → همان محصول، انسان قبلاً تصمیم گرفته
  L2  کش AI                → عنوان قبلاً قضاوت شده
  L3  خوشه‌های بزرگ        → قضاوت در سطح الگو (بیشترین اهرم)
  L4  دم بلند              → قضاوت تک‌تک عنوان‌ها

زیردستورها:
    python review_queue.py build            # ساخت صف و خوشه‌ها از داده‌ی push‌شده
    python review_queue.py status           # داشبورد پیشرفت
    python review_queue.py next --clusters 40   # بسته‌ی کار بعدی (چسبان در چت)
    python review_queue.py apply --file decisions_0007.json
    python review_queue.py audit --n 30     # نمونه‌ی کور برای سنجش دقت
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent
BUNDLE = HUB / "exports" / "training_bundle"
REVIEW = HUB / "exports" / "review"

CATEGORIES = ["mobile", "laptop", "tablet", "console", "gpu", "cpu", "ram", "storage",
              "motherboard", "desktop-pc", "monitor", "watch", "headphone", "other"]
DECISIONS = ("verify", "junk", "set-category", "uncertain")


def thash(t):
    return hashlib.sha1((t or "").strip().encode("utf-8")).hexdigest()[:16]


def norm_title(t):
    t = (t or "").lower().strip()
    t = re.sub(r"[0-9]+", "#", t)
    return re.sub(r"\s+", " ", t)


def cluster_key(t):
    w = norm_title(t).split()
    return " ".join(w[:2]) if w else "(خالی)"


def src_of(l):
    """همان منطق export_training_data.py برای تعیین منبع برچسب."""
    r = l.get("rejection_reason") or ""
    if l.get("quality_status") == "CONFIRMED_JUNK":
        return "human"
    if "✋" in r or "Agent" in r:
        return "human"
    if r.startswith("🤖"):
        return "ai"
    return "rule"


def load_bundle():
    if not (BUNDLE / "listings.jsonl").exists():
        print(f"❌ {BUNDLE / 'listings.jsonl'} پیدا نشد — اول export_training_bundle.py را اجرا کن")
        sys.exit(1)
    listings = [json.loads(x) for x in open(BUNDLE / "listings.jsonl", encoding="utf-8")]
    cache_p = BUNDLE / "ai_review_cache.jsonl"
    cache = [json.loads(x) for x in open(cache_p, encoding="utf-8")] if cache_p.exists() else []
    sig_p = BUNDLE / "learned_junk_signals.jsonl"
    sig = [json.loads(x) for x in open(sig_p, encoding="utf-8")] if sig_p.exists() else []
    return listings, cache, sig


# ----------------------------------------------------------------------------
def cmd_build(args):
    REVIEW.mkdir(parents=True, exist_ok=True)
    listings, cache, sig = load_bundle()
    for l in listings:
        l["_src"] = src_of(l)

    human_keys = {l["canonical_key"] for l in listings if l["_src"] == "human"}
    cache_titles = {c["title"].strip(): c for c in cache}

    queue, tiers = [], Counter()
    for l in listings:
        item = {
            "id": l["id"], "title": (l.get("title_fa") or "").strip(),
            "price": l.get("price_toman") or 0, "store": l.get("store_key"),
            "canonical_key": l.get("canonical_key"), "category": None,
            "status": l.get("quality_status"), "reason": l.get("rejection_reason") or "",
            "condition": l.get("condition") or "",
        }
        if l["_src"] == "human":
            item["tier"] = "L0_human"
        elif l["_src"] == "ai":
            item["tier"] = "L2_ai_cache"
            c = cache_titles.get(item["title"])
            if c:
                item["ai_is_device"] = c.get("is_device")
                item["ai_category"] = c.get("category") or None
                item["ai_confidence"] = c.get("confidence")
        elif l["canonical_key"] in human_keys:
            item["tier"] = "L1_inherit"
        elif item["title"] in cache_titles:
            item["tier"] = "L2_ai_cache"
            c = cache_titles[item["title"]]
            item["ai_is_device"] = c.get("is_device")
            item["ai_category"] = c.get("category") or None
        else:
            item["tier"] = "L3_queue"
            item["signal_hit"] = next((s["signal"] for s in sig
                                       if s.get("signal") and s["signal"] in item["title"]), None)
        tiers[item["tier"]] += 1
        queue.append(item)

    with open(REVIEW / "queue.jsonl", "w", encoding="utf-8") as f:
        for it in queue:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    # خوشه‌ها فقط روی صف واقعی
    q = [it for it in queue if it["tier"] == "L3_queue"]
    clusters = defaultdict(list)
    for it in q:
        clusters[cluster_key(it["title"])].append(it)
    ordered = sorted(clusters.items(), key=lambda kv: -len(kv[1]))
    crows = []
    for i, (k, items) in enumerate(ordered, 1):
        cid = f"C{i:04d}"
        prices = sorted(x["price"] for x in items if x["price"] > 0)
        crows.append({
            "cluster_id": cid, "key": k, "n_titles": len({x["title"] for x in items}),
            "n_listings": len(items),
            "stores": dict(Counter(x["store"] for x in items)),
            "median_price": prices[len(prices) // 2] if prices else 0,
            "signal_hit": items[0].get("signal_hit"),
            "samples": [{"id": x["id"], "title": x["title"], "price": x["price"],
                         "store": x["store"], "category": x.get("category"),
                         "condition": x.get("condition")}
                        for x in sorted(items, key=lambda z: -z["price"])[:args.samples]],
            "member_ids": [x["id"] for x in items],
        })
    with open(REVIEW / "clusters.jsonl", "w", encoding="utf-8") as f:
        for c in crows:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print("=" * 62)
    print("🧭 صف ساخته شد")
    print("=" * 62)
    for t in ("L0_human", "L1_inherit", "L2_ai_cache", "L3_queue"):
        print(f"   {t:<13} {tiers[t]:>7,} آگهی")
    print(f"\n   خوشه‌ها: {len(crows):,} (روی {tiers['L3_queue']:,} آگهی صف)")
    tot = sum(c["n_titles"] for c in crows)
    for n in (50, 100, 200, 400):
        cov = sum(c["n_titles"] for c in crows[:n])
        print(f"     {n:>4} خوشه‌ی بزرگ → {cov:,} عنوان ({cov / tot * 100:.0f}٪)")
    print(f"\n   📁 {REVIEW}")


# ----------------------------------------------------------------------------
def _load(name):
    p = REVIEW / name
    if not p.exists():
        return []
    return [json.loads(x) for x in open(p, encoding="utf-8")]


def _decided_ids():
    """id های آگهی‌هایی که قبلاً تصمیم گرفته‌اند (مستقیم یا از راه خوشه)."""
    clusters = {c["cluster_id"]: c for c in _load("clusters.jsonl")}
    out = {}
    for d in _load("decisions.jsonl"):
        if d.get("scope") == "cluster":
            c = clusters.get(d["ref"])
            if c:
                for i in c["member_ids"]:
                    out[i] = d
        elif d.get("scope") == "title":
            out[d["ref"]] = d
        elif d.get("scope") == "id":
            out[d["ref"]] = d
    return out


def cmd_status(args):
    queue = _load("queue.jsonl")
    if not queue:
        print("❌ اول build را اجرا کن")
        return
    clusters = _load("clusters.jsonl")
    dec = _load("decisions.jsonl")
    decided = _decided_ids()
    q = [x for x in queue if x["tier"] == "L3_queue"]
    done = [x for x in q if x["id"] in decided]
    cdone = {d["ref"] for d in dec if d.get("scope") == "cluster"}
    tdone = {d["ref"] for d in dec if d.get("scope") == "title"}

    print("=" * 62)
    print("📊 وضعیت بازبینی")
    print("=" * 62)
    print(f"   کل آگهی‌ها:            {len(queue):>7,}")
    for t in ("L0_human", "L1_inherit", "L2_ai_cache", "L3_queue"):
        n = sum(1 for x in queue if x["tier"] == t)
        print(f"     {t:<13} {n:>7,}")
    print(f"\n   صف واقعی:             {len(q):>7,} آگهی")
    print(f"   تصمیم‌گرفته‌شده:        {len(done):>7,}  ({len(done) / max(1, len(q)) * 100:.1f}٪)")
    print(f"   باقی‌مانده:            {len(q) - len(done):>7,}")
    print(f"\n   خوشه‌ها: {len(cdone):,} از {len(clusters):,} تصمیم گرفته شده")
    print(f"   عنوان‌های منفرد: {len(tdone):,}")
    print(f"   کل رکوردهای دفترکل: {len(dec):,}")
    if dec:
        kinds = Counter((d["decision"], d.get("scope")) for d in dec)
        print("\n   تفکیک تصمیم‌ها:")
        for (dd, sc), n in kinds.most_common():
            print(f"     {dd:<13} ({sc}) {n:>6,}")
    audits = [d for d in dec if d.get("scope") == "audit"]
    if audits:
        ok = sum(1 for a in audits if a.get("agree"))
        print(f"\n   ممیزی کور: {ok}/{len(audits)} توافق = {ok / len(audits) * 100:.1f}٪")


# ----------------------------------------------------------------------------
def cmd_next(args):
    clusters = _load("clusters.jsonl")
    if not clusters:
        print("❌ اول build را اجرا کن")
        return
    decided = _decided_ids()
    dec_refs = {d["ref"] for d in _load("decisions.jsonl")}
    todo = [c for c in clusters if c["cluster_id"] not in dec_refs and c["n_listings"] > 1]
    singles = [c for c in clusters if c["n_listings"] == 1 and c["cluster_id"] not in dec_refs]

    packets, cur, cur_n = [], [], 0
    for c in todo:
        cur.append(c)
        cur_n += c["n_titles"]
        if len(cur) >= args.clusters or cur_n >= args.max_titles:
            packets.append(cur)
            cur, cur_n = [], 0
    if cur:
        packets.append(cur)

    n = args.packet
    if n > len(packets):
        # دم بلند: بسته‌های تک‌عنوانی
        start = (n - len(packets) - 1) * args.max_titles
        chunk = singles[start:start + args.max_titles]
        if not chunk:
            print("✅ هیچ کار باقی‌مانده‌ای نیست")
            return
        print(f"# PACKET {n:04d} — {len(chunk)} عنوان منفرد")
        print('خروجی: {"decisions":[{"cluster":"C0123","decision":"verify","category":"desktop-pc"},'
              '{"cluster":"C0124","decision":"junk","reason":"..."}]}')
        for c in chunk:
            s = c["samples"][0]
            print(f'[{c["cluster_id"]}] {s["title"]}  |  {s["price"]:,}  |  {s["store"]}  |  {s.get("condition") or "-"}')
        return

    pkt = packets[n - 1]
    print(f"# PACKET {n:04d} — {len(pkt)} خوشه، پوشش {sum(c['n_titles'] for c in pkt):,} عنوان "
          f"/ {sum(c['n_listings'] for c in pkt):,} آگهی")
    print("")
    print("تصمیم برای هر خوشه (دقیقاً یکی):")
    print('  verify       → کالای اصلی واقعی است (+ category درست اگر لازم است)')
    print('  junk         → چرت/جانبی/خارج از حوزه (+ reason فارسی)')
    print('  set-category → اصلی است ولی دسته‌اش غلط است (+ category)')
    print('  split        → خوشه یکدست نیست؛ باید خرد شود (من اعضا را جدا می‌فرستم)')
    print("")
    for c in pkt:
        sig = f"  ⚑ سیگنال: «{c['signal_hit']}»" if c.get("signal_hit") else ""
        print(f'[{c["cluster_id"]}] {c["n_titles"]} عنوان / {c["n_listings"]} آگهی  '
              f'میانه قیمت {c["median_price"]:,}  سایت‌ها {c["stores"]}{sig}')
        for s in c["samples"]:
            print(f'    - {s["title"][:100]}  |  {s["price"]:,}  |  {s["store"]}  |  {s.get("condition") or "-"}')
        print("")
    print('قالب پاسخ: {"decisions":[{"cluster":"C0001","decision":"verify","category":"desktop-pc"}, ...]}')


# ----------------------------------------------------------------------------
def cmd_members(args):
    """همه‌ی اعضای یک خوشه با id — برای قضاوت آگهی‌به‌آگهی."""
    clusters = {c["cluster_id"]: c for c in _load("clusters.jsonl")}
    q = {x["id"]: x for x in _load("queue.jsonl")}
    decided = _decided_ids()
    ids = []
    for ref in args.clusters.split(","):
        c = clusters.get(ref.strip())
        if not c:
            print(f"❌ خوشه‌ی {ref} پیدا نشد")
            sys.exit(1)
        ids += c["member_ids"]
    print(f"# PER-LISTING — {len(ids)} آگهی (هر ردیف یک تصمیم جدا با id)")
    print('قالب: {"decisions":[{"id":123,"decision":"verify","category":"gpu"}, ...]}')
    for i in ids:
        it = q[i]
        flag = "  [قبلاً تصمیم دارد]" if i in decided else ""
        print(f'  id={i}  {it["title"][:95]}  |  {it["price"]:,}  |  {it["store"]}  '
              f'|  {it.get("condition") or "-"}{flag}')


FAKE_PATTERNS = {
    # ⚠️ «فیک» باید مرز کلمه داشته باشد وگرنه داخل «گرافیک» تطابق می‌شود!
    "فیک (کلمه‌ی مستقل)": r"(?<![\u0600-\u06FF])فیک(?![\u0600-\u06FF])",
    "کپی / های‌کپی": r"(?<![\u0600-\u06FF])(?:های[  ]?کپی|هایکپی|کپی)(?![\u0600-\u06FF])",
    "طرحِ برند": r"طرح\s*(?:اپل|apple|آیفون|iphone|سامسونگ|samsung|ایرپاد|airpod|گالکسی|galaxy|اولترا|ultra|پلی\s*استیشن|ps\d|رولکس|rolex|امگا|omega|جوردن|jordan|نایک|nike|آدیداس|adidas|شیائومی|xiaomi)",
    "ساعت/هدفون طرح (بدون برند)": r"(?:ساعت|هدفون|ایرباد|هندزفری)\s+طرح(?:\s|$|[\u0600-\u06FF])",
    "replica / clone / 1:1": r"\b(?:replica|1:1)\b|\bclone\b(?!\s+\d+\s+of)",
    "مدل کپی معروف (ساعت)": r"(?<![A-Za-z])(?:KW\d{2,3}|HK\d{1,2}|TX\d{2}(?!\d)|T900|T800|T500)(?![A-Za-z0-9])",
}


def cmd_scan(args):
    """اسکن دقیق کالای طرح/فیک — با مرز کلمه، و گزارش نمونه برای چشم‌گذرانی."""
    import re
    pats = {k: re.compile(v, re.I) for k, v in FAKE_PATTERNS.items()}
    q = _load("queue.jsonl")
    if not q:
        print("❌ اول build را اجرا کن")
        return
    print("=" * 66)
    print("🔎 اسکن کالای طرح/فیک")
    print("=" * 66)
    tot = Counter()
    bysrc = defaultdict(Counter)
    ex = defaultdict(list)
    matched = {}
    for it in q:
        t = it["title"] or ""
        for name, rx in pats.items():
            m = rx.search(t)
            if m:
                tot[name] += 1
                bysrc[name][it["tier"]] += 1
                matched[it["id"]] = name
                if len(ex[name]) < 8:
                    lo, hi = max(0, m.start() - 25), min(len(t), m.end() + 25)
                    ex[name].append((it["id"], t[lo:hi], it["price"], it["store"], it["tier"]))
                break
    total = sum(tot.values())
    print(f"\n  جمع آگهی‌های طرح/فیک: {total:,} از {len(q):,}  ({total / len(q) * 100:.1f}٪)")
    for name, n in tot.most_common():
        print(f"\n  ▸ {name}: {n:,}")
        print("     " + "  ".join(f"{t}:{c:,}" for t, c in bysrc[name].most_common()))
        for i, ctx, pr, st, tier in ex[name]:
            print(f"        id={i}  …{ctx}…  |  {pr:,}  |  {st}")
    if args.dump:
        out = REVIEW / "fake_candidates.jsonl"
        REVIEW.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for it in q:
                if it["id"] in matched:
                    r = dict(it)
                    r["fake_pattern"] = matched[it["id"]]
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\n  📁 لیست کامل: {out}")


def cmd_apply(args):
    path = Path(args.file)
    if not path.exists():
        print(f"❌ {path} پیدا نشد")
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("decisions", data) if isinstance(data, dict) else data
    clusters = {c["cluster_id"]: c for c in _load("clusters.jsonl")}
    if not clusters:
        print("❌ اول build را اجرا کن")
        sys.exit(1)
    queue_by_id = {x["id"]: x for x in _load("queue.jsonl")}

    ok, errs = [], []
    for i, d in enumerate(rows):
        ref = d.get("cluster") or d.get("title") or d.get("id")
        dec = d.get("decision")
        if ref is None:
            errs.append((i, "بدون cluster/title/id"))
            continue
        if dec not in DECISIONS:
            errs.append((i, f"decision نامعتبر: {dec}"))
            continue
        if dec in ("junk", "uncertain") and not (d.get("reason") or "").strip():
            errs.append((i, f"{ref}: {dec} بدون reason"))
            continue
        cat = d.get("category")
        if dec in ("verify", "set-category") and cat is not None and cat not in CATEGORIES:
            errs.append((i, f"{ref}: دسته‌ی خارج از لیست: {cat}"))
            continue
        if dec == "set-category" and not cat:
            errs.append((i, f"{ref}: set-category بدون category"))
            continue
        scope = "cluster" if str(ref).startswith("C") and ref in clusters else (
            "id" if isinstance(ref, int) else "title")
        if scope == "cluster":
            ids = clusters[ref]["member_ids"]
        elif scope == "id":
            ids = [ref]
        else:
            ids = [x["id"] for x in queue_by_id.values() if x["title"] == ref]
        if not ids:
            errs.append((i, f"{ref}: هیچ آگهی‌ای مطابقت نکرد"))
            continue
        ok.append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "scope": scope, "ref": ref, "decision": dec,
            "category": cat, "reason": (d.get("reason") or "").strip()[:200],
            "review_mode": d.get("review_mode") or ("cluster" if scope == "cluster" else "per_listing"),
            "members_read": d.get("members_read"),
            "decided_by": d.get("by") or "agent-arena",
            "note": (d.get("note") or "")[:200],
            "n_affected": len(ids), "affected_ids": ids,
            "prev": [{"id": x, "status": queue_by_id[x]["status"],
                      "reason": queue_by_id[x]["reason"]} for x in ids[:50]],
        })

    if errs:
        print(f"❌ {len(errs)} رکورد نامعتبر (چیزی اعمال نشد):")
        for i, m in errs[:15]:
            print(f"   [{i}] {m}")
        sys.exit(1)

    REVIEW.mkdir(parents=True, exist_ok=True)
    with open(REVIEW / "decisions.jsonl", "a", encoding="utf-8") as f:
        for r in ok:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_aff = sum(r["n_affected"] for r in ok)
    print(f"✅ {len(ok)} تصمیم ثبت شد → {n_aff:,} آگهی تحت تأثیر")
    print(f"   دفترکل: {REVIEW / 'decisions.jsonl'}")
    cmd_status(args)


# ----------------------------------------------------------------------------
def cmd_audit(args):
    dec = [d for d in _load("decisions.jsonl") if d.get("scope") == "cluster"]
    queue_by_id = {x["id"]: x for x in _load("queue.jsonl")}
    if not dec:
        print("❌ هنوز تصمیم خوشه‌ای ثبت نشده")
        return
    import random
    random.seed(args.seed)
    picks = []
    for d in dec:
        for i in random.sample(d["affected_ids"], min(2, len(d["affected_ids"]))):
            picks.append((d, queue_by_id.get(i)))
    random.shuffle(picks)
    picks = picks[:args.n]
    print(f"# AUDIT — {len(picks)} نمونه‌ی کور (بدون دیدن تصمیم قبلی قضاوت کن)")
    print('پاسخ: {"audit":[{"id":123,"decision":"verify","category":"gpu"}, ...]}')
    for d, it in picks:
        if not it:
            continue
        print(f'  id={it["id"]}  {it["title"][:110]}  |  {it["price"]:,}  |  {it["store"]}')
    (REVIEW / "audit_pending.json").write_text(
        json.dumps([{"id": it["id"], "cluster": d["ref"], "prev_decision": d["decision"],
                     "prev_category": d.get("category")} for d, it in picks if it],
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n(کلید پاسخ در {REVIEW / 'audit_pending.json'} ذخیره شد)")


def cmd_audit_apply(args):
    pending = json.loads((REVIEW / "audit_pending.json").read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in pending}
    data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    rows = data.get("audit", data) if isinstance(data, dict) else data
    agree = 0
    with open(REVIEW / "decisions.jsonl", "a", encoding="utf-8") as f:
        for r in rows:
            p = by_id.get(r["id"])
            if not p:
                continue
            same = (r["decision"] == p["prev_decision"]) and (
                r.get("category") in (None, p.get("prev_category")))
            agree += 1 if same else 0
            f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"),
                                "scope": "audit", "ref": r["id"], "decision": r["decision"],
                                "category": r.get("category"), "agree": same,
                                "cluster": p["cluster"], "decided_by": "agent-arena-audit"},
                               ensure_ascii=False) + "\n")
    print(f"✅ ممیزی: {agree}/{len(rows)} توافق = {agree / max(1, len(rows)) * 100:.1f}٪")
    bad = [r["id"] for r in rows
           if by_id.get(r["id"]) and not (r["decision"] == by_id[r["id"]]["prev_decision"])]
    if bad:
        print(f"   ⚠️ ناهمخوانی در: {bad[:20]}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--samples", type=int, default=4)
    b.set_defaults(fn=cmd_build)
    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)
    n = sub.add_parser("next")
    n.add_argument("--packet", type=int, default=1)
    n.add_argument("--clusters", type=int, default=25)
    n.add_argument("--max-titles", type=int, default=250)
    n.set_defaults(fn=cmd_next)
    m = sub.add_parser("members")
    m.add_argument("--clusters", required=True)
    m.set_defaults(fn=cmd_members)
    sc = sub.add_parser("scan")
    sc.add_argument("--dump", action="store_true")
    sc.set_defaults(fn=cmd_scan)
    a = sub.add_parser("apply")
    a.add_argument("--file", required=True)
    a.set_defaults(fn=cmd_apply)
    au = sub.add_parser("audit")
    au.add_argument("--n", type=int, default=30)
    au.add_argument("--seed", type=int, default=42)
    au.set_defaults(fn=cmd_audit)
    aa = sub.add_parser("audit-apply")
    aa.add_argument("--file", required=True)
    aa.set_defaults(fn=cmd_audit_apply)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args.fn(args)


if __name__ == "__main__":
    main()
