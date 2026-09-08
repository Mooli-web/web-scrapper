# -*- coding: utf-8 -*-
"""
🔍 بازبینی اختلاف‌های قانون↔انسان — review_disagreements.py
==============================================================
با قانون جدید تاکسونومی، هر جا «قانون فعلی» با «انتخاب دستی شما» فرق دارد
لیست می‌کند — گروه‌بندی‌شده، تا خطاهای دستیِ خودتان را در داشبورد اصلاح کنید:

  • اگر قانون درست می‌گوید (مثلاً هدفون بود که شما اشتباهی mobile کردید)
    → در داشبورد همان محصول را 🗂 به دسته‌ی درست برگردانید
  • اگر انتخاب شما درست بود (قانون هنوز بلد نیست) → دست نزنید؛ همان دیتای
    طلایی ML است

اجرا:  python review_disagreements.py [limit]
(پیش‌فرض ۱۵ نمونه در هر گروه)
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402
from core.taxonomy import normalize_category, category_label  # noqa: E402


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    hist = db.fetchall("""
        SELECT h.canonical_key, h.old_category, h.new_category, p.title_fa, p.category_key
        FROM category_history h
        LEFT JOIN canonical_products p ON p.canonical_key = h.canonical_key
        ORDER BY h.id ASC;
    """)

    groups = defaultdict(list)
    for h in hist:
        rule_now = normalize_category(h["category_key"], h["title_fa"] or "")
        if rule_now != h["new_category"]:
            groups[(rule_now, h["new_category"])].append(h["title_fa"] or "(بی‌عنوان)")

    total = sum(len(v) for v in groups.values())
    print("=" * 64)
    print(f"🔍 اختلاف قانونِ جدید با انتخاب‌های دستی شما: {total:,} مورد در {len(groups)} مسیر")
    print("=" * 64)
    print("برای هر مسیر: اگر قانون درست است، در داشبورد 🗂 اصلاح کنید؛ اگر شما درست بودید، دست نزنید (دیتای ML!).\n")

    for (rule, human), titles in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(f"—— قانون می‌گوید «{category_label(rule)}» ولی شما «{category_label(human)}» کردید: {len(titles):,} مورد ——")
        for t in titles[:limit]:
            print(f"   • {t[:60]}")
        if len(titles) > limit:
            print(f"   … و {len(titles) - limit:,} مورد دیگر")
        print()


if __name__ == "__main__":
    main()
