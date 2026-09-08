# -*- coding: utf-8 -*-
"""
🕵️ تشخیص تاییدهای انسانی — check_human_labels.py
=====================================================
جواب می‌دهد: تاییدهای ✋ شما چندتاست، در کدام دسته‌ها/فروشگاه‌ها ثبت شده،
و نمونه‌ی دلایل واقعی ذخیره‌شده چه شکلی‌اند (برای دیباگ شمارنده).

اجرا (پوشه 5_unified_local_hub):
    python check_human_labels.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402


def main():
    print("=" * 62)
    print("🕵️ گزارش برچسب‌های انسانی (✋ تایید / 🗑 چرت)")
    print("=" * 62)

    # ۱) کل تاییدهای انسانی — با هر الگویی که ذخیره شده باشد
    r_all = db.fetchone("SELECT COUNT(*) AS c FROM store_listings WHERE is_verified=1 AND (rejection_reason LIKE '%تایید%' OR rejection_reason LIKE '%✋%');")
    r_hand = db.fetchone("SELECT COUNT(*) AS c FROM store_listings WHERE rejection_reason LIKE '✋%';")
    r_junk = db.fetchone("SELECT COUNT(*) AS c FROM store_listings WHERE quality_status='CONFIRMED_JUNK';")
    print(f"\nکل آگهی‌های تاییدشده: {db.fetchone('SELECT COUNT(*) c FROM store_listings WHERE is_verified=1;')['c']:,}")
    print(f"تاییدهای انسانی (✋ در ابتدای دلیل): {r_hand['c']:,}")
    print(f"تاییدهای دارای کلمه‌ی «تایید» در دلیل: {r_all['c']:,}")
    print(f"تیک‌های چرت (CONFIRMED_JUNK): {r_junk['c']:,}")

    # ۲) تفکیک دسته‌ای تاییدهای ✋
    rows = db.fetchall("""
        SELECT COALESCE(NULLIF(c.category_std, ''), c.category_key, '?') AS cat,
               COUNT(*) AS n
        FROM store_listings l LEFT JOIN canonical_products c ON l.canonical_key = c.canonical_key
        WHERE l.rejection_reason LIKE '✋%'
        GROUP BY 1 ORDER BY n DESC;
    """)
    if rows:
        print("\n✋ تاییدهای انسانی به تفکیک دسته:")
        for r in rows:
            print(f"   {r['cat']:16s} {r['n']:,}")
    else:
        print("\n⚠️ هیچ ردیفی با دلیلِ شروع‌شونده با ✋ پیدا نشد!")

    # ۳) نمونه‌ی دلایلِ تاییدهای احتمالی (برای دیدن پیشوند واقعی)
    samples = db.fetchall("""
        SELECT quality_status, rejection_reason, COUNT(*) AS n
        FROM store_listings
        WHERE is_verified=1 AND rejection_reason != ''
        GROUP BY 1, 2 ORDER BY n DESC LIMIT 8;
    """)
    if samples:
        print("\nنمونه‌ی دلایلِ آگهی‌های تاییدشده (پرتکرار):")
        for s in samples:
            print(f"   [{s['quality_status']}] {s['n']:,}× — «{(s['rejection_reason'] or '')[:60]}»")


    # ۴) آخرین ردیف‌های تاییدشده با دلیل — با بایت‌های واقعی (برای شکار تفاوت‌های نامرئی)
    recent = db.fetchall("""
        SELECT id, rejection_reason FROM store_listings
        WHERE is_verified=1 AND rejection_reason != ''
        ORDER BY id DESC LIMIT 3;
    """)
    if recent:
        print("\nآخرین دلایل ذخیره‌شده (با بایت‌های ابتدایی — اگر دو نسخه ایموجی/حرف متفاوت باشند، hex فرق می‌کند):")
        for s in recent:
            hx = (s["rejection_reason"] or "")[:6].encode("utf-8").hex()
            print(f"   id={s['id']} | hex={hx} | «{(s['rejection_reason'] or '')[:50]}»")
    print("\n—— راهنمای تفسیر ——")
    print("• اگر «✋ در ابتدای دلیل» صفر ولی «کلمه‌ی تایید» زیاد است: پیشوند ذخیره‌شده")
    print("  فرق دارد — نمونه‌ی بالا را برای من بفرست تا شمارنده را هماهنگ کنم.")
    print("• اگر هر دو صفرند: تاییدها ثبت نشده‌اند — احتمالاً دکمه‌ی دیگری زده‌اید یا")
    print("  هاب هنگام تایید، کد قدیمی اجرا می‌کرده است.")
    print("• اگر عدد درست است ولی در دسته‌ی اشتباه: شمارنده‌ی پنجره، مال همان دسته است.")


if __name__ == "__main__":
    main()
