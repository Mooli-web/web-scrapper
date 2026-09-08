# -*- coding: utf-8 -*-
"""
🕵️ تحقیق جنایی برچسب‌ها — investigate_labels.py
================================================
صحنه‌ی جرم را برای یک دسته بازسازی می‌کند: هر آیتم ✋ از کجا آمده (گروهی/تکی/AI)،
چه زمانی، و آیا واقعاً بازدید شده یا در جاروی گروهی قلاب شده است.

سیگنال‌های تشخیصی:
  • دلیل «✋ تأیید گروهی شما» = جاروی گروهی (داشبورد ✓✓ یا میز بررسی)
    — این‌ها شاید هرگز تک‌به‌تک دیده نشده باشند!
  • دلیل «✋ تأیید شما» = کلیک تکی واقعی
  • تاریخچه‌ی تغییر دسته (category_history) = انتخاب فعال انسان با زمان
  • عنوان‌های هرز (خریدار/نصب بازی/...) میان تاییدشده‌ها = بلعیده شدن در جارو

اجرا (پوشه 5_unified_local_hub):
    python investigate_labels.py desktop-pc            # فقط گزارش جنایی
    python investigate_labels.py desktop-pc --requeue group
        # همه‌ی تاییدهای گروهی این دسته → برگشت به صف بررسی (✋ پاک می‌شود،
        # وضعیت VERIFIED می‌ماند چون قانون سالمش می‌داند؛ فقط دوباره در میز
        # بررسی ظاهر می‌شوند تا با چشم دیده شوند)
    python investigate_labels.py desktop-pc --requeue suspicious
        # فقط گروهی‌های مشکوک (عنوان هرز یا بدون تاریخچه‌ی انتخاب دسته)
"""

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402

GROUP_REASON_MARK = "✋ تأیید گروهی شما"
JUNK_TITLE_RE = re.compile(
    r"^(خریدار|خرید|فروشنده و خریدار|نصب|کالشکن|پلی2|معاوضه)|کپی\s*خور|گیفت|اشتراک", re.I)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_requeue = any(a.startswith("--requeue") for a in sys.argv[1:])
    category = args[0] if args else "desktop-pc"

    products = {r["canonical_key"]: r for r in db.fetchall(
        "SELECT canonical_key, title_fa, category_std, category_source FROM canonical_products;")}
    hist = db.fetchall("SELECT canonical_key, old_category, new_category, created_at FROM category_history ORDER BY id;")
    hist_by_key = {}
    for h in hist:
        hist_by_key.setdefault(h["canonical_key"], []).append(h)

    # آیتم‌های تاییدشده‌ی انسانی در این دسته
    rows = db.fetchall("""
        SELECT l.id, l.canonical_key, l.title_fa, l.price_toman, l.store_key, l.rejection_reason
        FROM store_listings l
        WHERE l.is_verified = 1 AND (l.rejection_reason LIKE '✋%' OR l.rejection_reason LIKE '%تایید شما%')
    """)
    in_cat = [r for r in rows
              if products.get(r["canonical_key"], {}).get("category_std") == category]

    print("=" * 64)
    print(f"🕵️ تحقیق جنایی — دسته «{category}»")
    print("=" * 64)
    print(f"کل آیتم‌های ✋ در این دسته: {len(in_cat):,}")

    by_reason = Counter()
    swept, singles, suspicious = [], [], []
    for r in in_cat:
        reason = r["rejection_reason"] or ""
        if GROUP_REASON_MARK in reason:
            by_reason["گروهی (جارو)"] += 1
            swept.append(r)
        else:
            by_reason["تکی (کلیک واقعی)"] += 1
            singles.append(r)
        has_choice = bool(hist_by_key.get(r["canonical_key"]))
        if GROUP_REASON_MARK in reason and not has_choice:
            suspicious.append(r)
        elif GROUP_REASON_MARK in reason and JUNK_TITLE_RE.search(r["title_fa"] or ""):
            suspicious.append(r)

    print("منبع تایید:")
    for k, v in by_reason.most_common():
        print(f"   {k}: {v:,}")
    print(f"\n🔴 امضای «جارو شده بدون انتخاب فعال»: {len(suspicious):,}")
    print("   (گروهی + هیچ تاریخچه‌ی تغییر دسته برای محصولشان نیست، یا عنوان هرز دارند)")

    junk_titled = [r for r in in_cat if JUNK_TITLE_RE.search(r["title_fa"] or "")]
    print(f"🔴 عنوان هرز میان تاییدشده‌ها (خریدار/نصب/کپی‌خور...): {len(junk_titled):,}")
    for r in junk_titled[:10]:
        print(f"     • [{r['store_key']}] {(r['title_fa'] or '')[:55]}")

    # زمان‌بندی تغییر دسته‌ها به این دسته (فوران = جاروی گروهی)
    moved_in = [(h["created_at"], products.get(h["canonical_key"], {}).get("title_fa", "?"))
                for h in hist if h["new_category"] == category]
    if moved_in:
        ts = Counter(t[:16] for t, _ in moved_in)
        print(f"\n⏱ انتقال‌ها به «{category}» بر اساس دقیقه (فوران = گروهی):")
        for t, c in ts.most_common(6):
            print(f"   {t}  →  {c} مورد")

    print("\nنمونه‌ی جارو‌شده‌ها (گروهی بدون انتخاب دسته):")
    for r in swept[:12]:
        print(f"   • [{r['store_key']}] {(r['title_fa'] or '')[:55]}")

    if not do_requeue:
        print("\n🔍 حالت گزارش. برای برگرداندن به صف بررسی:")
        print("   python investigate_labels.py " + category + " --requeue group        (همه‌ی گروهی‌های این دسته)")
        print("   python investigate_labels.py " + category + " --requeue suspicious  (فقط مشکوک‌ها)")
        return

    mode = "suspicious" if "suspicious" in sys.argv else "group"
    targets = suspicious if mode == "suspicious" else swept
    print(f"\n↩️ برگرداندن {len(targets):,} آیتم به صف بررسی (✋ پاک می‌شود؛ VERIFIED قانونی می‌ماند)...")
    n = 0
    for r in targets:
        db.execute("""UPDATE store_listings SET rejection_reason='', confidence_score=0 WHERE id=?;""", (r["id"],))
        n += 1
    print(f"✅ {n:,} آیتم به میز بررسی برگشت — در داشبورد «اجرای مجدد پالایش» لازم نیست؛ فقط /review را باز کن.")


if __name__ == "__main__":
    main()
