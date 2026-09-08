# -*- coding: utf-8 -*-
"""
🗂️ ممیزی کامل دسته‌بندی با AI — audit_categories.py
======================================================
همه‌ی محصولاتِ هنوز دسته‌ی AI نگرفته را (به‌همراه توضیحات آگهی) به Groq
می‌فرستد تا دسته‌ی استانداردشان قطعی/اصلاح شود. دسته‌ی قاعده‌ای فقط نقطه‌ی
شروع است؛ AI با شواهد عنوان + توضیحات تصمیم می‌گیرد.

اجرا (پوشه 5_unified_local_hub):

    python audit_categories.py            # تا پایان یا ۱۰ دور پیاپی بدون پیشرفت
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.ai_reviewer import ai_reviewer   # noqa: E402
from core.groq_client import groq_client   # noqa: E402
from database.db_manager import db         # noqa: E402


def remaining() -> int:
    try:
        r = db.fetchone("""
            SELECT COUNT(DISTINCT l.canonical_key) AS c
            FROM store_listings l JOIN canonical_products c ON l.canonical_key = c.canonical_key
            WHERE l.is_verified = 1 AND COALESCE(c.category_source, '') != 'ai';
        """)
        return r["c"] if r else 0
    except Exception:
        return -1


def main():
    print("=" * 60)
    print("🗂️ ممیزی کامل دسته‌بندی با AI (عنوان + توضیحات)")
    print("=" * 60)
    if not groq_client.is_configured():
        print("❌ کلید Groq تنظیم نشده — .env را بررسی کن.")
        sys.exit(1)
    print(f"🔑 کلیدها: {len(groq_client.api_keys)} | مدل: {groq_client.active_model}")
    print(f"📋 محصولات در انتظار دسته‌ی AI: {remaining():,}\n")

    stalled = 0
    total_done = total_changed = 0
    round_no = 0
    while True:
        left = remaining()
        if left <= 0:
            print("\n🎉 همه‌ی محصولات دسته‌ی AI گرفتند!")
            break
        if stalled >= 10:
            print(f"\n⏹️ ۱۰ دور پیاپی بدون پیشرفت — متوقف شدم ({left:,} باقی). بعداً دوباره اجرا کن.")
            break
        round_no += 1
        print(f"———— دور {round_no} | باقی‌مانده: {left:,} ————")
        res = ai_reviewer.run_category_audit(max_batches=40, batch_size=50)
        done = res.get("processed", 0)
        total_done += done
        total_changed += res.get("categories_changed", 0)
        print(f"  دسته‌بندی‌شده: {done} | اصلاح دسته: {res.get('categories_changed', 0)}"
              + (f" | ⚠️ {'; '.join(res['errors'][:1])}" if res.get("errors") else ""))
        if done == 0:
            stalled += 1
            wait = 90 if any("429" in e for e in res.get("errors", [])) else 20
            print(f"  ⏳ {wait} ثانیه صبر و ادامه... ({stalled}/10)")
            time.sleep(wait)
        else:
            stalled = 0
        time.sleep(2)

    print("\n📊 جمع‌بندی:")
    print(f"  دسته‌بندی‌شده با AI در این اجرا: {total_done:,}")
    print(f"  دسته‌های اصلاح‌شده:            {total_changed:,}")
    print(f"  باقی‌مانده:                     {remaining():,}")


if __name__ == "__main__":
    main()
