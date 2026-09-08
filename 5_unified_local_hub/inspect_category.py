# -*- coding: utf-8 -*-
"""
🔬 کالبدشکافی یک دسته — inspect_category.py
==============================================
ترکیب دسته را بر اساس «منبع دسته» (manual/ai/rule) می‌شکند و از هر کوه
نمونه می‌آورد — تا معلوم شود اشتباهات فاحش در کدام کوه‌اند:

    python inspect_category.py desktop-pc [نمونه‌ها]
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402

SRC_FA = {"manual": "🗂 دستِ شما", "ai": "🤖 هوش مصنوعی", "rule": "📐 قانون", "": "❓ خالی"}


def main():
    cat = sys.argv[1] if len(sys.argv) > 1 else "desktop-pc"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 12

    rows = db.fetchall("""
        SELECT p.canonical_key, p.title_fa, p.category_source,
               (SELECT COUNT(*) FROM store_listings l WHERE l.canonical_key = p.canonical_key AND l.is_verified = 1) AS v,
               (SELECT COUNT(*) FROM store_listings l WHERE l.canonical_key = p.canonical_key
                  AND l.is_verified = 1 AND (l.rejection_reason LIKE '✋%' OR l.rejection_reason LIKE '%تایید شما%')) AS hv
        FROM canonical_products p
        WHERE p.category_std = ?;
    """, (cat,))

    print("=" * 64)
    print(f"🔬 کالبدشکافی «{cat}» — {len(rows):,} محصول")
    print("=" * 64)

    by_src = Counter(r["category_source"] or "" for r in rows)
    print("ترکیب بر اساس منبع دسته:")
    for s, c in by_src.most_common():
        print(f"   {SRC_FA.get(s, s):16s} {c:,}")

    for src in ("ai", "rule", "manual", ""):
        cohort = [r for r in rows if (r["category_source"] or "") == src]
        if not cohort:
            continue
        with_hv = sum(1 for r in cohort if r["hv"] > 0)
        print(f"\n—— {SRC_FA.get(src, src)} ({len(cohort):,} محصول | {with_hv:,} محصول دارای ✋) ——")
        for r in cohort[:n]:
            mark = "✋" if r["hv"] > 0 else " "
            print(f"   {mark} {(r['title_fa'] or '')[:58]}")

    print("\n💡 راهنما: اشتباهات فاحش معمولاً در کوهِ بدون ✋ همان منبع‌اند —")
    print("   نمونه‌ی هر کوه را ببین؛ اگر کوهِ ai/rule پر از خطاست، همان منبع مقصر است.")


if __name__ == "__main__":
    main()
