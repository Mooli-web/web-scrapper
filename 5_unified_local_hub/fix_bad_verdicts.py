# -*- coding: utf-8 -*-
"""
🩹 اصلاح تصمیم‌های اشتباه AI — fix_bad_verdicts.py
===================================================
بر اساس حسابرسی نمونه‌گیری، سه کلاس تصمیم اشتباه شناسایی شد:
  ۱) آگهی‌های «خرید/معاوضه» که تایید شده بودند (باید حذف شوند — لایه ۱ الان خودش می‌گیرد)
  ۲) هارد/SSD/رم/مادربرد که «جانبی» رد شده بودند (در اسکوپ هستند — دوباره بازبینی)
  ۳) سیستم‌های گیمینگ کامل که رد شده بودند (دستگاه واقعی‌اند — دوباره بازبینی)

این اسکریپت:
  - کش AI این دسته‌ها را پاک می‌کند (تا با پرامپت اصلاح‌شده دوباره قضاوت شوند)
  - پالایش را دوباره اجرا می‌کند (آگهی‌های خرید/معاوضه این بار رایگان در لایه ۱ حذف می‌شوند)
  - می‌گوید بعدش drain_ai_queue.py را اجرا کنی (فقط همین دسته‌ها توکن می‌خورند)

اجرا:  python fix_bad_verdicts.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402

# کلیدواژه‌های دسته‌های آسیب‌دیده (برای پاک‌کردن هدفمند کش)
AFFECTED_KEYWORDS = (
    "معاوضه", "پرداخت آنی", "خرید",
    "هارد", "اس اس دی", "اساس دی", "ssd", "hdd", "دیسک",
    "مادربرد", "سیستم گیمینگ", "سیستم گیم", "سیستم رندر",
    "کیندل", "کتاب خوان", "کتابخوان", "رافیک", "ریگ",
    "رم ", "رام ",
)
# عنوان‌هایی که با «خرید» شروع نمی‌شوند ولی کلمه خرید دارند و فروش واقعی‌اند
SAFE_PATTERNS = ("قابل معاوضه",)


def is_affected(title: str) -> bool:
    t = (title or "").lower()
    if any(s in t for s in SAFE_PATTERNS):
        # «قابل معاوضه» فروش است؛ فقط اگر کلیدواژه‌ی دیگری هم دارد بازبینی شود
        has_other = any(k in t for k in AFFECTED_KEYWORDS if k not in ("معاوضه", "خرید"))
        return has_other
    return any(k in t for k in AFFECTED_KEYWORDS)


def main():
    print("=" * 60)
    print("🩹 اصلاح تصمیم‌های اشتباه AI (پس از سخت‌گیرانه‌شدن قوانین)")
    print("=" * 60)

    rows = db.fetchall("SELECT title_hash, title FROM ai_review_cache;")
    victim_hashes = [r["title_hash"] for r in rows if is_affected(r["title"] or "")]
    print(f"📋 کش AI: {len(rows)} عنوان | آسیب‌دیده (بازبینی مجدد): {len(victim_hashes)}")

    if victim_hashes:
        db.executemany(
            "DELETE FROM ai_review_cache WHERE title_hash = ?;",
            [(h,) for h in victim_hashes],
        )
        print(f"🗑️ {len(victim_hashes)} تصمیم قدیمی از کش حذف شد (بقیه دست‌نخورده).")

    # NEW: قفلِ تصمیم AI را برای همین دسته‌ها باز کن — تصمیم‌های AI با اجرای
    # مجدد پالایش بازنویسی نمی‌شوند (قفل هستند)، پس بدون این مرحله هیچ‌وقت
    # دوباره قضاوت نمی‌شدند. قانون قطعی جدید (اسم آغازین هارد/SSD/مادربرد/رم)
    # در پالایش بعدی این‌ها را رایگان و بی‌واسطه تایید می‌کند.
    unlocked = db.execute("""
        UPDATE store_listings SET quality_status = 'PENDING', rejection_reason = '', confidence_score = 0
        WHERE (rejection_reason LIKE '🤖%' OR quality_status = 'AI_REJECTED')
          AND (
                LOWER(title_fa) LIKE '%هارد%'
             OR LOWER(title_fa) LIKE '%ssd%'
             OR LOWER(title_fa) LIKE '%hdd%'
             OR LOWER(title_fa) LIKE '%اس اس دی%'
             OR LOWER(title_fa) LIKE '%مادربرد%'
             OR LOWER(title_fa) LIKE '%سیستم گیم%'
             OR LOWER(title_fa) LIKE '%کیندل%'
             OR LOWER(title_fa) LIKE '%کتاب خوان%'
             OR LOWER(title_fa) LIKE '%کتابخوان%'
             OR LOWER(title_fa) LIKE '%رافیک%'
          )
          AND title_fa NOT LIKE '%خنک%';
    """)
    print(f"🔓 قفل {unlocked} تصمیم AI آسیب‌دیده باز شد (سیستم‌های خنک‌کننده کنار گذاشته شدند).")

    # پالایش مجدد: خرید/معاوضه‌ها رایگان در لایه ۱ حذف می‌شوند؛
    # ذخیره‌سازی/قطعات دوباره به صف AI می‌روند (فقط همین‌ها توکن می‌خورند)
    from core.data_cleaner import data_purifier  # noqa: E402
    res = data_purifier.run_full_purification_pipeline()
    b = res.get("breakdown", {})
    print(f"🧽 پالایش مجدد: تایید={b.get('verified_clean')} | جانبی={b.get('accessory_or_junk')} "
          f"| صف AI={b.get('needs_ai_review')}")

    print()
    print("👉 حالا اجرا کن:  python drain_ai_queue.py")
    print("   (فقط دسته‌های پاک‌شده از کش توکن مصرف می‌کنند — بقیه رایگان می‌مانند)")
    print("   بعد از اتمام، دوباره نمونه بگیر:  python ai_quality_sample.py")


if __name__ == "__main__":
    main()
