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
    ⭕ استثنا (تصمیم نهایی صاحب داده): اگر کالا برند مستقلِ خودش را دارد و
    هیچ ادعایی روی برند/طرح دیگری ندارد (مثلاً «ساعت ویرفیت مدل HK10 PRO MAX»
    یا «Haino Teko G8») → می‌ماند و verify است. ملاک «ادعای برند دیگر» است،
    نه شباهت ظاهری. آنچه junk می‌شود: «طرح اپل واچ»، «آیفون فول کپی»،
    «مک بوک های‌کپی»، «ساعت طرح سیکو»، «آیفون فیک».
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


def prior_tag(x):
    """برچسب قبلی = فقط شاهد، نه رأی."""
    t = x.get("tier")
    st = (x.get("status") or "?")
    if t == "L0_human":
        return "انسان:" + st[:14]
    if t == "L1_inherit":
        return "ارث:" + st[:12]
    if t == "L2_ai_cache":
        cat = x.get("ai_category")
        return "AI:" + ("دستگاه" if x.get("ai_is_device") else "غیردستگاه") + (f"/{cat}" if cat else "")
    return "بدون‌شاهد"


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

    # ── خوشه‌ها روی «همه‌ی» آگهی‌ها؛ هیچ لایه‌ای معاف نیست
    decided = set()
    for d in _load("decisions.jsonl"):
        ids = d.get("affected_ids")
        if ids:
            decided.update(ids)

    clusters = defaultdict(list)
    for it in queue:
        clusters[it.get("canonical_key") or norm_title(it["title"])].append(it)

    # شناسه‌ی پایدار: کلیدهای قدیمی همان cid قبلی را نگه می‌دارند.
    # اگر نسخه‌ی تابع خوشه‌سازی عوض شده باشد، cid های قدیمی معنا ندارند.
    vk = REVIEW / "cluster_key.version"
    cur_ver = "canonical-v1"
    old_ids = {}
    if vk.exists() and vk.read_text(encoding="utf-8").strip() == cur_ver:
        old_ids = {c["key"]: c["cluster_id"] for c in _load("clusters.jsonl")}
    vk.write_text(cur_ver, encoding="utf-8")
    used = {int(v[1:]) for v in old_ids.values() if re.fullmatch(r"C\d{4,}", v)}
    used = used if old_ids else set()
    nxt = max(used, default=0)

    def cid_for(k):
        nonlocal nxt
        if k in old_ids:
            return old_ids[k]
        nxt += 1
        old_ids[k] = f"C{nxt:04d}"
        return f"C{nxt:04d}"

    crows = []
    for k, items in sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        prices = sorted(x["price"] for x in items if x["price"] > 0)
        crows.append({
            "cluster_id": cid_for(k), "key": k,
            "n_titles": len({x["title"] for x in items}), "n_listings": len(items),
            "n_pending": sum(1 for x in items if x["id"] not in decided),
            "priors": dict(Counter(x["tier"] for x in items)),
            "stores": dict(Counter(x["store"] for x in items)),
            "median_price": prices[len(prices) // 2] if prices else 0,
            "signal_hit": items[0].get("signal_hit"),
            "samples": [{"id": x["id"], "title": x["title"], "price": x["price"],
                         "store": x["store"], "category": x.get("category"),
                         "condition": x.get("condition"), "tier": x["tier"]}
                        for x in sorted(items, key=lambda z: -z["price"])[:args.samples]],
            "member_ids": [x["id"] for x in items],
        })
    # cid ها را بعد از تخصیص کامل، به‌ترتیب بزرگی بازنویسی نکن — فقط فایل را بنویس
    with open(REVIEW / "clusters.jsonl", "w", encoding="utf-8") as f:
        for c in crows:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    pend_clusters = [c for c in crows if c["n_pending"] > 0]
    print("=" * 62)
    print("🧭 صف ساخته شد — همه‌ی آگهی‌ها در حوزه‌ی بازبینی‌اند")
    print("=" * 62)
    for t in ("L0_human", "L1_inherit", "L2_ai_cache", "L3_queue"):
        n = sum(1 for x in queue if x["tier"] == t)
        d = sum(1 for x in queue if x["tier"] == t and x["id"] in decided)
        print(f"   {t:<13} {n:>7,} آگهی   (تصمیم‌گرفته {d:,} · باقی {n - d:,})")
    print(f"\n   کل: {len(queue):,} آگهی · تصمیم‌گرفته {len(decided):,} "
          f"· باقی {len(queue) - len(decided):,}  ({len(decided) / len(queue) * 100:.1f}٪)")
    print(f"\n   خوشه‌ها: {len(crows):,} — با کار باقی‌مانده: {len(pend_clusters):,}")
    print(f"   عنوان‌های یکتا: {len({x['title'] for x in queue}):,}")
    for n in (50, 100, 200, 400):
        cov = sum(c["n_pending"] for c in pend_clusters[:n])
        tot = sum(c["n_pending"] for c in pend_clusters) or 1
        print(f"     {n:>4} خوشه‌ی بزرگ → {cov:,} آگهی باقی‌مانده ({cov / tot * 100:.0f}٪)")
    print(f"\n   📁 {REVIEW}")


# ----------------------------------------------------------------------------
def _load(name):
    p = REVIEW / name
    if not p.exists():
        return []
    return [json.loads(x) for x in open(p, encoding="utf-8")]


def _decided_ids():
    """id های آگهی‌هایی که قبلاً تصمیم گرفته‌اند.

    برای تصمیم‌های خوشه‌ای از `affected_ids` (عکس لحظه‌ی ثبت) استفاده می‌شود،
    نه عضویت فعلی خوشه — وگرنه وقتی خوشه بعداً بزرگ‌تر شود، رأی قدیمی بی‌آنکه
    اعضایش خوانده شده باشند گسترش پیدا می‌کند.
    """
    clusters = {c["cluster_id"]: c for c in _load("clusters.jsonl")}
    out = {}
    for d in _load("decisions.jsonl"):
        if d.get("scope") == "cluster":
            ids = d.get("affected_ids") or clusters.get(d["ref"], {}).get("member_ids", [])
        elif d.get("scope") in ("title", "id"):
            ids = [d["ref"]]
        else:
            continue
        for i in ids:
            out[i] = d
    return out


def cmd_status(args):
    queue = _load("queue.jsonl")
    if not queue:
        print("❌ اول build را اجرا کن")
        return
    clusters = _load("clusters.jsonl")
    dec = _load("decisions.jsonl")
    decided = _decided_ids()
    done = [x for x in queue if x["id"] in decided]

    print("=" * 62)
    print("📊 وضعیت بازبینی — همه‌ی آگهی‌ها در حوزه")
    print("=" * 62)
    print(f"   کل آگهی‌ها:            {len(queue):>7,}")
    for t in ("L0_human", "L1_inherit", "L2_ai_cache", "L3_queue"):
        rows = [x for x in queue if x["tier"] == t]
        d = sum(1 for x in rows if x["id"] in decided)
        print(f"     {t:<13} {len(rows):>7,}   تصمیم {d:>6,}   باقی {len(rows) - d:>6,}")
    print(f"\n   تصمیم‌گرفته‌شده:        {len(done):>7,}  ({len(done) / len(queue) * 100:.1f}٪)")
    print(f"   باقی‌مانده:            {len(queue) - len(done):>7,}")
    print(f"\n   خوشه‌ها: {len(clusters):,} کل · "
          f"{sum(1 for c in clusters if c['n_pending'] > 0):,} با کار باقی‌مانده")
    print(f"   کل رکوردهای دفترکل: {len(dec):,}")
    if dec:
        print("\n   تفکیک تصمیم‌ها:")
        for (dd, sc), n in Counter((d["decision"], d.get("scope")) for d in dec).most_common():
            print(f"     {dd:<13} ({sc}) {n:>6,}")
    audits = [d for d in dec if d.get("scope") == "audit"]
    if audits:
        ok = sum(1 for a in audits if a.get("agree"))
        print(f"\n   ممیزی کور: {ok}/{len(audits)} توافق = {ok / len(audits) * 100:.1f}٪")


# ----------------------------------------------------------------------------
def cmd_flat(args):
    """بسته‌ی تخت: آگهی‌ها یکی‌یکی، بدون خوشه — همان چیزی که صاحب داده خواست.

    ترتیب پایدار (سایت، بعد دسته‌ی حدسی، بعد قیمت نزولی) تا سیاست‌ها در طول
    بسته یکدست بماند و نشست بعدی دقیقاً از همان‌جا ادامه پیدا کند.
    """
    queue = _load("queue.jsonl")
    if not queue:
        print("❌ اول build را اجرا کن")
        return
    decided = _decided_ids()
    todo = [x for x in queue if x["id"] not in decided]
    todo.sort(key=lambda x: (x["store"] or "", x.get("tier", ""), -x["price"], x["id"]))
    if not todo:
        print("✅ هیچ آگهی باقی‌مانده‌ای نیست")
        return
    start = (args.packet - 1) * args.rows
    chunk = todo[start:start + args.rows]
    if not chunk:
        print(f"✅ بسته‌ی {args.packet} وجود ندارد — "
              f"{(len(todo) + args.rows - 1) // args.rows} بسته کار باقی است")
        return
    npk = (len(todo) + args.rows - 1) // args.rows
    print(f"# PACKET {args.packet:04d} — {len(chunk)} آگهی از {len(todo):,} باقی‌مانده "
          f"({npk} بسته در کل)")
    print("# قالب پاسخ:  <id> v|j|s|u [category] [# دلیل]")
    print(f"# سایت: {chunk[0]['store']}")
    for x in chunk:
        print(f'{x["id"]} | {x["title"][:70]} | {x["price"]:,} | {x.get("condition") or "-"} '
              f'| {prior_tag(x)}')


def cmd_next(args):
    """بسته‌ی بعدی کار: خوشه‌هایی که هنوز عضو تصمیم‌نگرفته دارند.

    هیچ خوشه‌ای به‌خاطر برچسب انسانی/AI رد نمی‌شود؛ برچسب فقط کنار هر آگهی
    به‌عنوان شاهد چاپ می‌شود و رأی نهایی را بازبین می‌دهد.
    """
    clusters = _load("clusters.jsonl")
    if not clusters:
        print("❌ اول build را اجرا کن")
        return
    queue_by_id = {x["id"]: x for x in _load("queue.jsonl")}
    decided = _decided_ids()
    todo = sorted((c for c in clusters if c["n_pending"] > 0), key=lambda c: -c["n_pending"])
    if not todo:
        print("✅ هیچ کار باقی‌مانده‌ای نیست")
        return

    packets, cur, cur_rows = [], [], 0
    for c in todo:
        cur.append(c)
        cur_rows += c["n_pending"]
        if len(cur) >= args.clusters or cur_rows >= args.max_rows:
            packets.append(cur)
            cur, cur_rows = [], 0
    if cur:
        packets.append(cur)

    if args.packet > len(packets):
        print(f"✅ بسته‌ی {args.packet} وجود ندارد — {len(packets)} بسته کار باقی است")
        return

    pkt = packets[args.packet - 1]
    rows = sum(c["n_pending"] for c in pkt)
    print(f"# PACKET {args.packet:04d} — {len(pkt)} خوشه / {rows:,} آگهی "
          f"(بسته‌های باقی‌مانده: {len(packets):,})")
    print("")
    print("تصمیم برای هر خوشه (دقیقاً یکی) — اگر اعضا یکدست نبود، تصمیم آگهی‌به‌آگهی بده:")
    print("  verify       → کالای اصلی واقعی (+ category درست)")
    print("  junk         → حذف (+ reason فارسی)   ·   set-category → فقط اصلاح دسته")
    print("  uncertain    → قابل قضاوت نیست، از دیتاست بیرون می‌رود (+ reason)")
    print('  برای آگهی خاص: {"id": 12345, "decision": "junk", "reason": "..."}')
    print("")
    for c in pkt:
        sig = f"  ⚑ «{c['signal_hit']}»" if c.get("signal_hit") else ""
        print(f'[{c["cluster_id"]}] {c["n_titles"]} عنوان / {c["n_listings"]} آگهی · '
              f'باقی {c["n_pending"]} · میانه {c["median_price"]:,} · {c["priors"]}{sig}')
        pend = [queue_by_id[i] for i in c["member_ids"] if i in queue_by_id and i not in decided]
        if len(pend) > args.max_per_cluster:
            pr = sorted(x["price"] for x in pend if x["price"] > 0)
            cond = Counter(x.get("condition") or "-" for x in pend)
            pr2 = Counter(x.get("tier") for x in pend)
            print(f"    ▸ {len(pend)} عضو | قیمت min/میانه/max = "
                  f"{pr[0]:,}/{pr[len(pr) // 2]:,}/{pr[-1]:,}" if pr else f"    ▸ {len(pend)} عضو | بدون قیمت")
            print(f"    ▸ وضعیت: {dict(cond.most_common(4))} | شاهد: {dict(pr2)}")
        shown = pend[:args.max_per_cluster]
        for x in sorted(shown, key=lambda z: -z["price"]):
            print(f'    · {x["id"]} | {x["title"][:64]} | {x["price"]:,} | {x["store"]} | '
                  f'{x.get("condition") or "-"} | {prior_tag(x)}')
        if len(pend) > len(shown):
            print(f"    … {len(pend) - len(shown)} آگهی دیگر (اگر خوشه یکدست است "
                  f'خوشه‌ای رأی بده، وگرنه "split")')
        print("")
    print('قالب پاسخ: {"decisions":[{"cluster":"C0123","decision":"verify","category":"watch"}, ...]}')


# ----------------------------------------------------------------------------
def cmd_report(args):
    """خلاصه‌ی نهایی: چند آگهی هست و چند تا بررسی/دسته‌بندی/حذف شده."""
    queue = _load("queue.jsonl")
    if not queue:
        print("❌ اول build را اجرا کن")
        return
    decided = _decided_ids()
    dec = [d for d in _load("decisions.jsonl") if d.get("scope") != "audit"]
    q = [x for x in queue if x["tier"] == "L3_queue"]

    def bucket(x):
        d = decided.get(x["id"])
        if d:
            return {"verify": "clean", "set-category": "clean",
                    "junk": "junk", "uncertain": "excluded"}[d["decision"]]
        return "pending"   # برچسب قبلی رأی نیست — تا بازبین تصمیم ندهد، بررسی‌نشده است

    tot = Counter(bucket(x) for x in queue)
    mine = Counter()
    for x in queue:
        d = decided.get(x["id"])
        if d:
            mine[{"verify": "clean", "set-category": "clean",
                  "junk": "junk", "uncertain": "excluded"}[d["decision"]]] += 1

    print("=" * 62)
    print("📋 خلاصه‌ی بازبینی داده — همه‌ی آگهی‌ها در حوزه")
    print("=" * 62)
    print(f"  کل آگهی‌ها:                 {len(queue):>8,}")
    print(f"    ├─ تمیز (clean):         {tot['clean']:>8,}")
    print(f"    ├─ حذف‌شده (junk):        {tot['junk']:>8,}")
    print(f"    ├─ کنارگذاشته (uncertain):{tot['excluded']:>8,}")
    print(f"    └─ هنوز بررسی‌نشده:       {tot['pending']:>8,}")
    print(f"\n  پوشش بازبینی: {(len(queue) - tot['pending']) / len(queue) * 100:.1f}٪ "
          f"({len(queue) - tot['pending']:,} از {len(queue):,})")
    print("\n  باقی‌مانده به تفکیک برچسب قبلی (فقط شاهد است، پذیرفته نشده):")
    for t in ("L0_human", "L1_inherit", "L2_ai_cache", "L3_queue"):
        rows = [x for x in queue if x["tier"] == t and x["id"] not in decided]
        v = sum(1 for x in rows if x["status"] == "VERIFIED")
        print(f"    {t:<13} {len(rows):>7,}   (برچسب قبلی‌شان: {v:,} تأیید · {len(rows) - v:,} رد)")
    print(f"\n  تصمیم‌های این ایجنت: {sum(mine.values()):,} آگهی "
          f"(clean {mine['clean']:,} · junk {mine['junk']:,} · excluded {mine['excluded']:,})")
    dec = [d for d in _load("decisions.jsonl") if d.get("scope") != "audit"]
    print(f"  رکوردهای دفترکل: {len(dec):,}")
    modes = Counter(d.get("review_mode") or ("cluster" if d.get("scope") == "cluster" else "per_listing")
                    for d in dec)
    print(f"  حالت بازبینی: {dict(modes)}")
    clusters = _load("clusters.jsonl")
    print(f"  خوشه‌های با کار باقی‌مانده: "
          f"{sum(1 for c in clusters if c['n_pending'] > 0):,} از {len(clusters):,}")
    audits = [d for d in _load("decisions.jsonl") if d.get("scope") == "audit"]
    if audits:
        ok = sum(1 for a in audits if a.get("agree"))
        print(f"  ممیزی کور: {ok}/{len(audits)} = {ok / len(audits) * 100:.0f}٪")


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


DSL_DOC = """قالب فشرده (هر خط یک تصمیم):
   <ref> <d> [category] [# دلیل/یادداشت]      ·  ref = id عددی یا Cxxxx
   d: v=verify · j=junk · s=set-category · u=uncertain
   مثال:  1234 v laptop   |   1235 j # لوازم جانبی   |   C0001 v watch
"""


def parse_dsl(text):
    """تبدیل قالب فشرده به همان ساختار JSON تصمیم‌ها."""
    out = []
    for ln, line in enumerate(text.splitlines(), 1):
        line = line.split("//")[0].strip()
        if not line or line.startswith("#") and " " not in line.strip("# "):
            continue
        note = ""
        if "#" in line:
            line, note = line.split("#", 1)
            line, note = line.strip(), note.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            raise ValueError(f"خط {ln}: «{line}» — قالب: <ref> <d> [category] [# دلیل]")
        ref, d = parts[0], parts[1].lower()
        cat = parts[2] if len(parts) > 2 else None
        m = {"v": "verify", "j": "junk", "s": "set-category", "u": "uncertain"}
        if d not in m:
            raise ValueError(f"خط {ln}: کد نامعتبر «{d}» (v/j/s/u)")
        ref = int(ref) if ref.isdigit() else ref
        row = {"cluster" if isinstance(ref, str) else "id": ref,
               "decision": m[d], "category": cat}
        if note:
            row["reason" if m[d] in ("junk", "uncertain") else "note"] = note
        out.append(row)
    return out


def cmd_apply(args):
    path = Path(args.file)
    if not path.exists():
        print(f"❌ {path} پیدا نشد")
        sys.exit(1)
    raw = path.read_text(encoding="utf-8")
    if path.suffix in (".txt", ".dsl") or not raw.lstrip().startswith(("{", "[")):
        rows = parse_dsl(raw)
    else:
        data = json.loads(raw)
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
        missing = [x for x in ids if x not in queue_by_id]
        if missing:
            errs.append((i, f"{ref}: {len(missing)} آگهی در صف نیست (نمونه {missing[:3]})"))
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
    b.add_argument("--samples", type=int, default=6)
    b.set_defaults(fn=cmd_build)
    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)
    n = sub.add_parser("next")
    n.add_argument("--packet", type=int, default=1)
    n.add_argument("--clusters", type=int, default=25)
    n.add_argument("--max-titles", type=int, default=250)
    n.add_argument("--max-rows", type=int, default=140, help="حداکثر آگهی در هر بسته")
    n.add_argument("--max-per-cluster", type=int, default=25,
                   help="حداکثر آگهی که از هر خوشه چاپ می‌شود")
    n.set_defaults(fn=cmd_next)
    f = sub.add_parser("flat")
    f.add_argument("--packet", type=int, default=1)
    f.add_argument("--rows", type=int, default=250)
    f.set_defaults(fn=cmd_flat)
    r = sub.add_parser("report")
    r.set_defaults(fn=cmd_report)
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
