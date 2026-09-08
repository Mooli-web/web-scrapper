# -*- coding: utf-8 -*-
"""
🔍 نمونه‌گیری کیفیت تصمیم‌های AI — ai_quality_sample.py
========================================================
۳۰ تصمیم تصادفی گروک (تاییدشده + ردشده) را به‌صورت متن تمیز چاپ می‌کند
تا برای بازبینی انسانی/ایجنت کپی شود. اجرا:

    python ai_quality_sample.py            # ۳۰ نمونه (۱۵ تایید + ۱۵ رد)
    python ai_quality_sample.py 50         # نمونه‌ی بزرگ‌تر
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402


def sample(query: str, n: int):
    rows = db.fetchall(query, (n,))
    return rows


def main():
    per_side = max(5, (int(sys.argv[1]) if len(sys.argv) > 1 else 30) // 2)

    verified = sample("""
        SELECT title_fa, price_toman, store_key, rejection_reason, confidence_score
        FROM store_listings
        WHERE quality_status='VERIFIED' AND rejection_reason LIKE '🤖%'
        ORDER BY RANDOM() LIMIT ?;
    """, per_side)

    rejected = sample("""
        SELECT title_fa, price_toman, store_key, rejection_reason, confidence_score
        FROM store_listings
        WHERE quality_status='AI_REJECTED'
        ORDER BY RANDOM() LIMIT ?;
    """, per_side)

    totals = db.fetchone("""
        SELECT
          COUNT(CASE WHEN quality_status='VERIFIED' AND rejection_reason LIKE '🤖%' THEN 1 END) ai_v,
          COUNT(CASE WHEN quality_status='AI_REJECTED' THEN 1 END) ai_r
        FROM store_listings;
    """) or {"ai_v": 0, "ai_r": 0}

    print("=" * 66)
    print("🔍 نمونه‌گیری کیفیت تصمیم‌های AI — برای بازبینی")
    print("=" * 66)
    print(f"کل تاییدشده‌های AI: {totals['ai_v']:,} | کل ردشده‌های AI: {totals['ai_r']:,}")
    print(f"نمونه‌ی امروز: {len(verified)} تایید + {len(rejected)} رد (تصادفی)")
    print()
    print("———— ✅ تاییدشده توسط AI (آیا واقعا کالای اصلی‌اند؟) ————")
    for i, r in enumerate(verified, 1):
        price = f"{r['price_toman']:,}"
        print(f"V{i:02d}| {r['title_fa'][:58]}")
        print(f"    {price} ت | {r['store_key']} | {r['rejection_reason'][:50]}")
    print()
    print("———— ❌ ردشده توسط AI (آیا واقعا چرت/جانبی‌اند؟) ————")
    for i, r in enumerate(rejected, 1):
        price = f"{r['price_toman']:,}"
        print(f"R{i:02d}| {r['title_fa'][:58]}")
        print(f"    {price} ت | {r['store_key']} | {r['rejection_reason'][:50]}")
    print()
    print("📋 همه‌ی این بلوک را کپی و برای بازبینی بفرست.")
    print("   برای هر خطی که مخالفتی، شماره‌اش را بنویس (مثلاً: V03 غلطه، R11 غلطه).")


if __name__ == "__main__":
    main()
