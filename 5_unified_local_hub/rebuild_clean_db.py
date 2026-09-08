# -*- coding: utf-8 -*-
"""
🧹 بازسازی تمیز دیتابیس هاب — rebuild_clean_db.py
===================================================
مشکل: canonical_products های فعلی با نرمال‌ساز قدیمی (برند dell جعلی، کلیدهای
item_XXXX تصادفی، دسته‌های تکراری) ساخته شده‌اند. این اسکریپت دیتابیس را از صفر
با نرمال‌ساز فیکس‌شده بازمی‌سازد و کش بازبینی AI را (که با زحمت و توکن جمع شده!)
دست‌نخورده برمی‌گرداند — یعنی قضاوت‌های AI بدون صرف حتی یک توکن دوباره اعمال می‌شوند.

اجرا (پوشه 5_unified_local_hub):

    python rebuild_clean_db.py            # فقط بازسازی + بازیابی کش (سینک را خودت از داشبورد بزن)
    python rebuild_clean_db.py --pull     # بازسازی + سینک کامل ۴ بازار + پالایش + اعمال کش (همه‌کاره)

چه می‌کند؟
  ۱. بکاپ کامل دیتابیس فعلی → data/market_backup_تاریخ.db (هیچ‌چیز از دست نمی‌رود)
  ۲. بکاپ جدول ai_review_cache → exports/ai_review_cache_backup.json
  ۳. دیتابیس نو با schema.sql تمیز ساخته می‌شود
  ۴. کش AI بازیابی می‌شود
  ۵. (با --pull) دانلود کامل ۴ بازار + پالایش لایه ۱
  ۶. قضاوت‌های AI از کش، رایگان اعمال می‌شود
  ۷. آمار قبل/بعد چاپ می‌شود (مثلاً حذف برند dell های جعلی)
"""

import argparse
import json
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent
DB = HUB / "data" / "market.db"
CACHE_BAK = HUB / "exports" / "ai_review_cache_backup.json"


def read_cache_from_old_db() -> list:
    if not DB.exists():
        return []
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT title_hash, title, is_device, reason_fa, confidence, model FROM ai_review_cache;"
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []  # جدول کش نبود (نسخه خیلی قدیمی)
    finally:
        conn.close()


def old_stats() -> dict:
    if not DB.exists():
        return {}
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    out = {}
    try:
        out["listings"] = conn.execute("SELECT COUNT(*) c FROM store_listings;").fetchone()["c"]
        out["canonical"] = conn.execute("SELECT COUNT(*) c FROM canonical_products;").fetchone()["c"]
        out["dell_fake"] = conn.execute(
            "SELECT COUNT(*) c FROM canonical_products WHERE brand='dell' AND canonical_key LIKE 'dell_%'"
        ).fetchone()["c"]
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true", help="بعد از بازسازی، سینک کامل ۴ بازار هم اجرا شود")
    args = ap.parse_args()

    print("=" * 60)
    print("🧹 بازسازی تمیز دیتابیس هاب")
    print("=" * 60)

    if not DB.exists():
        print("❌ دیتابیس فعلی پیدا نشد — چیزی برای بازسازی نیست.")
        sys.exit(1)

    # ---- ۱. آمار قبل ----
    before = old_stats()
    print(f"📊 قبل: {before.get('listings', '?')} آگهی | {before.get('canonical', '?')} محصول کانونیکال"
          + (f" | {before.get('dell_fake', '?')} کلید dell مشکوک" if before.get("dell_fake") else ""))

    # ---- ۲. بکاپ کش AI ----
    cache_rows = read_cache_from_old_db()
    CACHE_BAK.parent.mkdir(parents=True, exist_ok=True)
    CACHE_BAK.write_text(json.dumps(cache_rows, ensure_ascii=False), encoding="utf-8")
    print(f"💾 بکاپ کش AI: {len(cache_rows)} عنوان → {CACHE_BAK.name}")

    # ---- ۳. جابه‌جایی دیتابیس قدیمی ----
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB.with_name(f"market_backup_{stamp}.db")
    for suf in ("-wal", "-shm"):
        p = DB.with_name(DB.name + suf)
        if p.exists():
            shutil.move(str(p), str(backup_path.with_name(backup_path.name + suf)))
    shutil.move(str(DB), str(backup_path))
    print(f"🗄️ دیتابیس قدیمی → {backup_path.name} (اگر همه‌چیز خوب بود، بعداً حذفش کن)")

    # ---- ۴. ساخت دیتابیس نو + import ماژول‌ها (ترتیب مهم: بعد از جابه‌جایی!) ----
    sys.path.insert(0, str(HUB))
    from database.db_manager import db          # noqa: E402  (اینجا schema نو ساخته می‌شود)
    from core.ai_reviewer import ai_reviewer    # noqa: E402  (جدول کش نو ساخته می‌شود)

    tables = {r["name"] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table';")}
    print(f"✅ دیتابیس نو ساخته شد ({len(tables)} جدول)")

    # ---- ۵. بازیابی کش AI ----
    if cache_rows:
        db.executemany(
            """INSERT OR REPLACE INTO ai_review_cache
               (title_hash, title, is_device, reason_fa, confidence, model)
               VALUES (?, ?, ?, ?, ?, ?);""",
            [(r["title_hash"], r["title"], r["is_device"], r["reason_fa"],
              r["confidence"], r["model"]) for r in cache_rows],
        )
        print(f"♻️ کش AI بازیابی شد: {len(cache_rows)} عنوان (بدون صرف توکن)")

    # ---- ۶. سینک کامل (اختیاری) ----
    if args.pull:
        print("🌐 سینک کامل ۴ بازار شروع شد (چند دقیقه)...")
        from sync.pull_cloud_databases import cloud_puller  # noqa: E402
        res = cloud_puller.pull_all_and_sync()
        print(f"   دریافت شد: {res.get('total_ingested')} آیتم | فرصت آربیتراژ: {res.get('arbitrage_opportunities')}")
    else:
        print("\n👉 حالا در داشبورد دکمه «دانلود و همگام‌سازی کامل» را بزن،")
        print("   بعد دکمه «اجرای پالایش»، بعد دکمه «🤖 بازبینی هوشمند» (کش‌ها رایگان اعمال می‌شوند).")
        print("   ⚠️ توجه: سینک واقعی برای پر شدن دیتابیس نو لازم است — بدون آن دیتابیس خالی است!")

    # ---- ۷. پالایش + اعمال کش ----
    if args.pull:
        from core.data_cleaner import data_purifier  # noqa: E402
        res = data_purifier.run_full_purification_pipeline()
        b = res.get("breakdown", {})
        print(f"🧽 پالایش: {json.dumps(b, ensure_ascii=False)}")
        applied = ai_reviewer.apply_cached_verdicts()
        print(f"♻️ از کش اعمال شد: {applied} آیتم (رایگان)")

    # ---- ۸. آمار بعد ----
    if args.pull:
        after = old_stats()
        print(f"📊 بعد: {after.get('listings', 0)} آگهی | {after.get('canonical', 0)} محصول کانونیکال"
              f" | dell: {after.get('dell_fake', 0)}")
        pend = ai_reviewer.count_pending()
        print(f"🤖 صف AI (عنوان‌های تازه): {pend} — با دکمه بنفش یا دستور max_batches ادامه بده")
    print("\n🎉 بازسازی تمام شد.")


if __name__ == "__main__":
    main()
