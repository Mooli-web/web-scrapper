# -*- coding: utf-8 -*-
"""
🎓 ممیزی پیش‌آموزش — pre_training_audit.py
=============================================
گزارش کامل آمادگی داده‌ها قبل از رفتن به مرحله‌ی آموزش مدل. فقط خواندنی
(هیچ چیزی تغییر نمی‌دهد). بخش‌ها:

  A) برچسب‌های انسانی: تایید✋ / حذف🗑 / تغییر دسته🗂 + تفکیک فروشگاهی
  B) علت‌های حذف: تفکیک دلایل (آماده/دلخواه/عمومی قدیمی)
  C) دقت دسته‌بندی: توافق قاعده‌ای با اصلاحات انسانی + نمونه‌های مشکوک
  D) کالاهای باقی‌مانده: به تفکیک دسته + صف AI
  E) کارنامه‌ی آمادگی ML: پوشش طلایی هر دسته، توازن برچسب‌ها، پوشش توضیحات، تکراری‌ها

اجرا (پوشه 5_unified_local_hub):
    python pre_training_audit.py
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402
from core.taxonomy import normalize_category, STANDARD_CATEGORIES, ensure_category_columns  # noqa: E402

GENERIC_OLD_REASON = "✋ تأیید شما: کالای چرت/غیرمرتبط"


def hr(title):
    print("\n" + "—" * 22 + f" {title} " + "—" * 22)


def main():
    print("=" * 64)
    print("🎓 ممیزی پیش‌آموزش — آمار کامل برچسب‌ها و آمادگی ML")
    print("=" * 64)

    # FIX: category_std / category_source / category_history در schema.sql نیستند
    # و runtime توسط taxonomy ساخته می‌شوند — بدون این فراخوانی کوئری بعدی
    # روی دیتابیس نوساخته با «no such column: category_std» می‌شکست.
    ensure_category_columns()

    listings = {r["id"]: r for r in db.fetchall(
        "SELECT id, canonical_key, store_key, title_fa, description, price_toman, quality_status, rejection_reason FROM store_listings;")}
    products = {r["canonical_key"]: r for r in db.fetchall(
        "SELECT canonical_key, title_fa, category_key, category_std, category_source FROM canonical_products;")}

    def std_of(p):
        s = (p.get("category_std") or "").strip()
        return s if s in STANDARD_CATEGORIES else normalize_category(p["category_key"], p["title_fa"] or "")

    def is_human_verified(l):
        r = l["rejection_reason"] or ""
        return l["quality_status"] == "VERIFIED" and (r.startswith("✋") or "تایید شما" in r or "تأیید شما" in r or "تائید" in r[:12])

    # ---------------- A) برچسب‌های انسانی ----------------
    hr("A) برچسب‌های انسانی")
    hv = [l for l in listings.values() if is_human_verified(l)]
    junk_h = [l for l in listings.values() if l["quality_status"] == "CONFIRMED_JUNK"]
    print(f"تایید دستی ✋:        {len(hv):,} آگهی ({len({l['canonical_key'] for l in hv}):,} محصول)")
    print(f"حذف دستی 🗑:          {len(junk_h):,} آگهی ({len({l['canonical_key'] for l in junk_h}):,} محصول)")
    for name, group in (("تایید ✋", hv), ("حذف 🗑", junk_h)):
        by_store = Counter(l["store_key"] for l in group)
        print(f"تفکیک {name} بر اساس سایت: " + ", ".join(f"{s}({n:,})" for s, n in by_store.most_common()))

    # تغییر دسته‌ها
    hist = db.fetchall("SELECT canonical_key, old_category, new_category, note, is_uncertain, created_at FROM category_history ORDER BY id;")
    print(f"\nتغییر دسته 🗂:        {len(hist):,} مورد")
    if hist:
        store_of = {}
        for l in listings.values():
            store_of.setdefault(l["canonical_key"], Counter())[l["store_key"]] += 1
        ch_store = Counter()
        for h in hist:
            c = store_of.get(h["canonical_key"])
            if c:
                ch_store[c.most_common(1)[0][0]] += 1
        print("تفکیک تغییر دسته بر اساس سایت (غالب آگهی‌های محصول): " +
              ", ".join(f"{s}({n:,})" for s, n in ch_store.most_common()))
        trans = Counter((h["old_category"] or "(خالی)", h["new_category"]) for h in hist)
        print("پرتکرارترین مسیرها:")
        for (o, n), c in trans.most_common(8):
            print(f"   {c:4,}×  {o} → {n}")
        unc = sum(1 for h in hist if h["is_uncertain"])
        noted = sum(1 for h in hist if (h["note"] or "").strip())
        print(f"دارای یادداشت دلیل: {noted:,} | علامت «مطمئن نیستم»: {unc:,}")

    # ---------------- B) علت‌های حذف ----------------
    hr("B) علت‌های حذف (چرت‌های دستی)")
    reasons = Counter()
    generic = 0
    for l in junk_h:
        r = (l["rejection_reason"] or "").strip()
        if r.startswith("✋"):
            r = r[1:].strip()
        if not r or "چرت/غیرمرتبط" in r:
            generic += 1
            reasons["(عمومی قدیمی — بدون دلیل مشخص)"] += 1
        else:
            reasons[r[:60]] += 1
    for r, c in reasons.most_common(12):
        print(f"   {c:4,}×  {r}")
    labeled = len(junk_h) - generic
    pct = round(labeled / max(len(junk_h), 1) * 100, 1)
    print(f"\nدارای دلیل مشخص: {labeled:,}/{len(junk_h):,} ({pct}٪)" + ("  ⚠️ دلایل عمومی قدیمی برای ML کم‌ارزش‌ترند" if generic > len(junk_h) * 0.3 else "  ✅"))

    # ---------------- C) دقت دسته‌بندی ----------------
    hr("C) دقت دسته‌بندی (توافق قاعده‌ای با اصلاحات انسانی)")
    agree = disagree = 0
    mism = []
    for h in hist:
        p = products.get(h["canonical_key"])
        if not p:
            continue
        rule = normalize_category(p["category_key"], p["title_fa"] or "")
        if rule == h["new_category"]:
            agree += 1
        else:
            disagree += 1
            if len(mism) < 8:
                mism.append(((p["title_fa"] or "")[:40], rule, h["new_category"]))
    tot = agree + disagree
    if tot:
        print(f"روی {tot:,} اصلاح انسانی: قاعده‌ای همان جواب انسان را می‌داد در {agree:,} ({round(agree/tot*100,1)}٪)")
        print(f"(یعنی خطای تخمینی قواعد فعلی ≈ {round(disagree/tot*100,1)}٪ — ML دقیقاً باید این شکاف را ببندد)")
        if mism:
            print("نمونه‌ی اختلاف‌ها (عنوان | قاعده می‌گفت | انسان کرد):")
            for t, o, n in mism:
                print(f"   {t} | {o} → {n}")
    else:
        print("اصلاح دسته‌ای ثبت نشده — دقت قابل‌سنجش نیست.")

    # توافق AI با انسان (محصولاتی که AI دسته داده و انسان بعداً همان را manual کرده)
    ai_agree = ai_tot = 0
    for h in hist:
        p = products.get(h["canonical_key"])
        if p and (p.get("category_source") == "ai") and p.get("category_std") == h["new_category"]:
            ai_agree += 1
        if p and (p.get("category_source") == "ai"):
            ai_tot += 1
    if ai_tot:
        print(f"\nمحصولات با دسته‌ی AI که انسان تأییدشان کرد: {ai_agree:,}/{ai_tot:,} ({round(ai_agree/ai_tot*100,1)}٪)")

    # ---------------- D) کالاهای باقی‌مانده ----------------
    hr("D) باقی‌مانده برای بررسی")
    remaining = defaultdict(int)
    rem_total = 0
    for l in listings.values():
        if l["quality_status"] == "VERIFIED" and not is_human_verified(l):
            p = products.get(l["canonical_key"])
            if p:
                remaining[std_of(p)] += 1
                rem_total += 1
    for cat, n in sorted(remaining.items(), key=lambda x: -x[1]):
        print(f"   {cat:14s} {n:,}")
    pend = db.fetchone("SELECT COUNT(*) c FROM store_listings WHERE quality_status IN ('PENDING','NEEDS_AI_REVIEW');")["c"]
    ai_q = db.fetchone("SELECT COUNT(*) c FROM store_listings WHERE quality_status='NEEDS_AI_REVIEW';")["c"]
    print(f"\nجمع باقی‌مانده (تاییدشده بدون بازدید انسانی): {rem_total:,}")
    print(f"در صف/معلق: {pend:,} (از آن صف AI: {ai_q:,})")

    # ---------------- E) کارنامه‌ی آمادگی ML ----------------
    hr("E) کارنامه‌ی آمادگی ML")
    flags = []

    # E1) پوشش طلایی هر دسته (محصول با حداقل یک ✋)
    gold = defaultdict(int)
    for l in hv:
        p = products.get(l["canonical_key"])
        if p:
            gold[std_of(p)] += 1
    weak = {c: n for c, n in gold.items() if n < 70}
    strong = {c: n for c, n in gold.items() if n >= 70}
    print(f"دسته‌های با پوشش طلایی کافی (≥۷۰): {len(strong)} → " + ", ".join(f"{c}({n})" for c, n in sorted(strong.items(), key=lambda x: -x[1])))
    if weak:
        print(f"⚠️ پوشش ضعیف (<۷۰): " + ", ".join(f"{c}({n})" for c, n in sorted(weak.items(), key=lambda x: -x[1])))
    flags.append(("برچسب طلایی هر دسته", len(strong) >= 5))

    # E2) توازن برچسب کیفیت
    q = Counter(l["quality_status"] for l in listings.values())
    clean = q.get("VERIFIED", 0)
    junk_all = sum(v for k, v in q.items() if k not in ("VERIFIED", "PENDING", "NEEDS_AI_REVIEW", ""))
    print(f"\nکیفیت: clean={clean:,} | junk={junk_all:,} (نسبت {round(clean/max(clean+junk_all,1)*100)}٪/{round(junk_all/max(clean+junk_all,1)*100)}٪)")
    flags.append(("توازن clean/junk معقول (junk بین ۱۰ تا ۶۰٪)", 0.10 <= junk_all / max(clean + junk_all, 1) <= 0.60))

    # E3) پوشش توضیحات
    with_desc = sum(1 for l in listings.values() if (l["description"] or "").strip())
    print(f"توضیحات: {with_desc:,}/{len(listings):,} ({round(with_desc/max(len(listings),1)*100)}٪)")
    flags.append(("پوشش توضیحات > ۲۰٪", with_desc / max(len(listings), 1) > 0.20))

    # E4) تکراری‌های دقیق باقی‌مانده
    try:
        from dedupe_listings import find_exact_groups
        dup_extra = sum(len(v) - 1 for v in find_exact_groups().values())
    except Exception:
        dup_extra = -1
    print(f"تکراری دقیق باقی‌مانده: {dup_extra:,}")
    flags.append(("تکراری دقیق < ۵۰۰", 0 <= dup_extra < 500))

    # E5) زامبی
    verified_keys = {l["canonical_key"] for l in listings.values() if l["quality_status"] == "VERIFIED"}
    zombies = len(products) - len(verified_keys)
    print(f"محصولات زامبی (بدون آگهی تاییدشده): {zombies:,}")
    flags.append(("زامبی < ۲۰٪ کل محصولات", zombies < len(products) * 0.20))

    # خلاصه
    print("\n" + "=" * 64)
    print("🧾 جمع‌بندی آمادگی:")
    ok = 0
    for name, passed in flags:
        print(f"   {'✅' if passed else '⚠️'} {name}")
        ok += passed
    print(f"\nامتیاز: {ok}/{len(flags)} — " + ("آماده‌ی شروع آموزش هستید! 🚀" if ok == len(flags) else "موارد ⚠️ را به‌مرور کامل کنید؛ مانع شروع نیستند."))


if __name__ == "__main__":
    main()
