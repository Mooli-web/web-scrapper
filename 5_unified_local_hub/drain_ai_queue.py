# -*- coding: utf-8 -*-
"""
🤖 تخلیه کامل صف بازبینی AI — drain_ai_queue.py
==================================================
مستقل از curl و مرورگر: صف NEEDS_AI_REVIEW را تا صفر شدن پیش می‌برد؛
محدودیت نرخ (429) را خودش با صبر مدیریت می‌کند و کش‌ها را رایگان اعمال می‌کند.

اجرا (پوشه 5_unified_local_hub — هاب می‌تواند باز یا بسته باشد):

    python drain_ai_queue.py

هر دور: تا ۴۰ دسته‌ی ۵۰تایی (۲,۰۰۰ آیتم) می‌فرستد؛ اگر همه‌ی کلیدها به
محدودیت خوردند ۹۰ ثانیه صبر می‌کند و ادامه می‌دهد. بعد از ۵ دور پیاپی
خطای غیرنرخ، می‌ایستد تا بی‌نهایت لوپ نشود.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.ai_reviewer import ai_reviewer   # noqa: E402
from core.groq_client import groq_client   # noqa: E402


def main():
    print("=" * 60)
    print("🤖 تخلیه کامل صف بازبینی هوشمند")
    print("=" * 60)

    if not groq_client.is_configured():
        print("❌ کلید Groq تنظیم نشده — .env را بررسی کن (GROQ_API_KEY).")
        sys.exit(1)

    print(f"🔑 کلیدها: {len(groq_client.api_keys)} | مدل: {groq_client.active_model}")
    print(f"📋 صف فعلی: {ai_reviewer.count_pending()} آگهی\n")

    round_no = 0
    total_api = total_cached = 0
    consecutive_errors = 0

    while True:
        pending = ai_reviewer.count_pending()
        if pending == 0:
            print("\n🎉 صف کاملاً خالی شد!")
            break
        if consecutive_errors >= 5:
            print("\n⏹️ ۵ دور پیاپی خطا — برای جلوگیری از لوپ بی‌پایان متوقف شدم.")
            print("   لاگ بالا را بررسی کن (کلید؟ مدل؟ رله؟) و دوباره اجرا کن.")
            break

        round_no += 1
        print(f"———— دور {round_no} | صف: {pending:,} ————")
        res = ai_reviewer.run_review(max_batches=40, batch_size=50)
        total_api += res.get("api_processed", 0)
        total_cached += res.get("cached_applied", 0)
        print(f"  AI: {res['api_processed']} (تایید {res['api_verified']} / رد {res['api_rejected']})"
              f" | کش رایگان: {res['cached_applied']}"
              f" | توقف نرخ: {res.get('rate_limit_waits', 0)}"
              f" | باقی: {res['still_pending']:,}")

        if res.get("errors"):
            consecutive_errors += 1
            is_rate = any("429" in e for e in res["errors"])
            wait = 90 if is_rate else 20
            print(f"  ⚠️ {'; '.join(res['errors'][:2])}")
            print(f"  ⏳ {wait} ثانیه صبر و ادامه... (دور خطا {consecutive_errors}/5)")
            time.sleep(wait)
        else:
            consecutive_errors = 0
            if res["still_pending"] == 0:
                print("\n🎉 صف کاملاً خالی شد!")
                break
            time.sleep(2)

    stats = ai_reviewer.get_stats()
    print("\n📊 جمع‌بندی:")
    print(f"  پردازش‌شده با API در این اجرا: {total_api:,}")
    print(f"  اعمال‌شده از کش (رایگان):      {total_cached:,}")
    print(f"  باقی‌مانده در صف:               {stats['pending_review']:,}")
    print(f"  کل توکن مصرفی از ابتدا:        {stats['groq_tokens_used']:,}")


if __name__ == "__main__":
    main()
