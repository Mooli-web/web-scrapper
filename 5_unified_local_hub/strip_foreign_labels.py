#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پاک‌کردن هر برچسبی که این ایجنت نزده است — انسانی و AI.

چرا این فایل لازم است
---------------------
صاحب داده می‌خواهد بقیه‌ی آگهی‌ها را خودش دستی برچسب بزند. برای این کار
صف باید «تمیز» باشد: نه تیک انسانیِ قبلی رویش باشد، نه رأی AI. وگرنه
نمی‌داند کدام ردیف واقعاً بی‌تصمیم است.

برچسب در این دیتابیس در پنج جا می‌نشیند و این ابزار هر پنج تا را می‌زند.
جا انداختن حتی یکی یعنی صف «تمیز» به‌ظاهر تمیز است و در عمل آلوده — همان
باگی که یک بار کار را هدر داد.

  ۱) store_listings.is_verified
  ۲) store_listings.quality_status
  ۳) store_listings.rejection_reason   (✋ = انسان، 🤖 = AI، [کد] = ایجنت)
  ۴) store_listings.confidence_score
  ۵) canonical_products.category_std / category_source  ('manual' | 'ai')
  ۶) ai_review_cache                    (کل جدول = رأی AI)

قاعده‌ی اصلی
-----------
**ملاک «برچسبِ ایجنت» بودن، دفترکل است نه حدس از روی ایموجی.**
هر id که در exports/review/decisions.jsonl رأی دارد دست‌نخورده می‌ماند؛
بقیه به وضعیت اولیه‌ی اسکیما برمی‌گردند:
    is_verified=0, quality_status='PENDING', rejection_reason='',
    confidence_score=0

این از «هرجا ✋ یا 🤖 دیدی پاک کن» امن‌تر است، چون برچسب‌هایی که هیچ
پیشوندی ندارند (مثلاً quality_status='ACCESSORY_OR_JUNK' که data_cleaner
می‌گذارد) هم گرفته می‌شوند.

هیچ ردیفی حذف نمی‌شود. فقط برچسب‌ها صفر می‌شوند.

    python3 strip_foreign_labels.py              # پیش‌نمایش، چیزی نمی‌نویسد
    python3 strip_foreign_labels.py --apply      # نوشتن، با نسخه‌ی پشتیبان
    python3 strip_foreign_labels.py --everything # حتی برچسب ایجنت (ریست کامل)

`category_history` عمداً دست‌نخورده می‌ماند: یک گزارش append-only از
اصلاحات است، هیچ کد مسیری از آن برچسب نمی‌خواند، و پاک‌کردنش فقط
قابلیت حسابرسی را از بین می‌برد. با --purge-history صریح پاک می‌شود.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))

from apply_decisions_to_db import LEDGER, latest_decisions  # noqa: E402

DEFAULT_DB = HUB / "data" / "market.db"

# وضعیت اولیه‌ی اسکیما (database/schema.sql، ستون‌های purification)
BLANK = (0, "PENDING", "", 0.0)

AI_STATUSES = ("AI_REJECTED", "NEEDS_AI_REVIEW")


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table});")}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def audit(conn: sqlite3.Connection, agent_ids: set[int]) -> dict:
    """وضعیت فعلی را می‌شمارد. چیزی نمی‌نویسد."""
    out: dict = {}
    total = conn.execute("SELECT COUNT(*) FROM store_listings").fetchone()[0]
    out["total_listings"] = total

    out["by_status"] = dict(conn.execute(
        "SELECT COALESCE(NULLIF(quality_status,''),'(خالی)'), COUNT(*) "
        "FROM store_listings GROUP BY 1 ORDER BY 2 DESC").fetchall())

    # منبع برچسب. ترتیب مهم است: اول دفترکل (ملاک واقعی)، بعد پیشوندها.
    # نسخه‌ی اول فقط از روی پیشوند حدس می‌زد و ردیفی را که در دفترکل بود
    # ولی پیشوند نداشت «منبع نامعلوم» نشان می‌داد — گزارشی که با قاعده‌ی
    # خودِ ابزار نمی‌خواند.
    src = Counter()
    for lid, reason, status in conn.execute(
            "SELECT id, COALESCE(rejection_reason,''), COALESCE(quality_status,'') "
            "FROM store_listings"):
        if lid in agent_ids:
            src["ایجنت (طبق دفترکل — می‌ماند)"] += 1
        elif reason.startswith("✋"):
            src["انسانی (✋ — پاک می‌شود)"] += 1
        elif reason.startswith("🤖") or status in AI_STATUSES:
            src["AI (🤖 — پاک می‌شود)"] += 1
        elif status in ("PENDING", ""):
            src["بی‌تصمیم (چیزی برای پاک‌کردن نیست)"] += 1
        else:
            src["منبع نامعلوم (پاک می‌شود)"] += 1
    out["by_source"] = dict(src)

    out["agent_ids_in_ledger"] = len(agent_ids)
    out["agent_ids_in_db"] = conn.execute(
        f"SELECT COUNT(*) FROM store_listings WHERE id IN "
        f"({','.join(str(int(i)) for i in agent_ids) or 'NULL'})").fetchone()[0] \
        if agent_ids else 0

    out["labeled_rows"] = conn.execute(
        "SELECT COUNT(*) FROM store_listings WHERE NOT ("
        "is_verified=0 AND quality_status='PENDING' "
        "AND rejection_reason='' AND confidence_score=0)").fetchone()[0]

    cc = _cols(conn, "canonical_products")
    if "category_source" in cc:
        out["by_category_source"] = dict(conn.execute(
            "SELECT COALESCE(NULLIF(category_source,''),'(خالی)'), COUNT(*) "
            "FROM canonical_products GROUP BY 1 ORDER BY 2 DESC").fetchall())
        out["category_rows_to_clear"] = conn.execute(
            "SELECT COUNT(*) FROM canonical_products "
            "WHERE category_source IN ('ai','manual')").fetchone()[0]
    else:
        out["by_category_source"] = {}
        out["category_rows_to_clear"] = 0
        out["note_no_category_source"] = True

    out["ai_cache_rows"] = (conn.execute(
        "SELECT COUNT(*) FROM ai_review_cache").fetchone()[0]
        if _table_exists(conn, "ai_review_cache") else 0)

    out["category_history_rows"] = (conn.execute(
        "SELECT COUNT(*) FROM category_history").fetchone()[0]
        if _table_exists(conn, "category_history") else 0)
    return out


def strip(conn: sqlite3.Connection, keep_ids: set[int], apply: bool,
          purge_history: bool) -> dict:
    """برچسب‌های غیرایجنت را صفر می‌کند. apply=False یعنی فقط بشمار.

    ⚠️ وقتی apply=True این تابع خودش commit می‌کند. عمداً: نسخه‌ی اول
    کامیت نمی‌کرد و اگر صداکننده تراکنش را باز نمی‌کرد، هیچ اتفاقی نمی‌افتاد
    و بی‌صدا «موفق» برمی‌گشت — همان شکست خاموشی که یک بار کار را هدر داد.
    """
    # idها در یک جدول موقت می‌روند: فهرست NOT IN با ده‌هزار id هم کند است
    # هم به سقف متغیرهای SQL می‌خورد.
    conn.execute("DROP TABLE IF EXISTS _keep_ids")
    conn.execute("CREATE TEMP TABLE _keep_ids (id INTEGER PRIMARY KEY)")
    conn.executemany("INSERT OR IGNORE INTO _keep_ids VALUES (?)",
                     [(int(i),) for i in keep_ids])

    where_keep = "id NOT IN (SELECT id FROM _keep_ids)"
    n_listings = conn.execute(
        f"SELECT COUNT(*) FROM store_listings WHERE {where_keep} AND NOT ("
        "is_verified=0 AND quality_status='PENDING' "
        "AND rejection_reason='' AND confidence_score=0)").fetchone()[0]

    has_cat = "category_source" in _cols(conn, "canonical_products")
    n_cat = conn.execute(
        "SELECT COUNT(*) FROM canonical_products "
        "WHERE category_source IN ('ai','manual')").fetchone()[0] if has_cat else 0

    n_ai = (conn.execute("SELECT COUNT(*) FROM ai_review_cache").fetchone()[0]
            if _table_exists(conn, "ai_review_cache") else 0)

    n_hist = 0
    if purge_history and _table_exists(conn, "category_history"):
        n_hist = conn.execute("SELECT COUNT(*) FROM category_history").fetchone()[0]

    if apply:
        conn.execute(
            f"UPDATE store_listings SET is_verified=?, quality_status=?, "
            f"rejection_reason=?, confidence_score=? WHERE {where_keep}", BLANK)
        if has_cat:
            conn.execute("UPDATE canonical_products SET category_std='', "
                         "category_source='' WHERE category_source IN ('ai','manual')")
        if _table_exists(conn, "ai_review_cache"):
            conn.execute("DELETE FROM ai_review_cache")
        if n_hist:
            conn.execute("DELETE FROM category_history")
        conn.commit()          # بدون این، شکست خاموش است
    conn.execute("DROP TABLE IF EXISTS _keep_ids")

    return {"listings": n_listings, "categories": n_cat,
            "ai_cache": n_ai, "history": n_hist}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--ledger", default=str(LEDGER))
    ap.add_argument("--apply", action="store_true", help="واقعاً بنویس")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--everything", action="store_true",
                    help="برچسب ایجنت را هم پاک کن (ریست کامل؛ دفترکل دست‌نخورده می‌ماند)")
    ap.add_argument("--purge-history", action="store_true",
                    help="category_history را هم پاک کن (پیش‌فرض: می‌ماند)")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"❌ دیتابیس پیدا نشد: {db}")
        return 1

    agent = latest_decisions(Path(args.ledger))
    keep = set() if args.everything else set(agent)

    conn = sqlite3.connect(db)
    try:
        a = audit(conn, set(agent))
        print("=" * 66)
        print("🧹 پاک‌کردن برچسب‌های غیرایجنت (انسانی + AI)")
        print("=" * 66)
        print(f"\n  دیتابیس: {db}")
        print(f"  کل آگهی‌ها: {a['total_listings']:,}")
        print(f"  برچسب‌دار: {a['labeled_rows']:,}")
        print(f"  دفترکل ایجنت: {a['agent_ids_in_ledger']:,} رأی "
              f"({a['agent_ids_in_db']:,} تای آن در این دیتابیس هست)")

        print("\n  برچسب‌ها به تفکیک منبع:")
        for k, v in a["by_source"].items():
            print(f"    {k:<22} {v:>7,}")

        print("\n  quality_status فعلی:")
        for k, v in a["by_status"].items():
            print(f"    {k:<22} {v:>7,}")

        if a["by_category_source"]:
            print("\n  category_source روی canonical_products:")
            for k, v in a["by_category_source"].items():
                print(f"    {k:<22} {v:>7,}")

        print(f"\n  ردیف ai_review_cache: {a['ai_cache_rows']:,}")
        print(f"  ردیف category_history: {a['category_history_rows']:,} "
              f"({'پاک می‌شود' if args.purge_history else 'دست‌نخورده می‌ماند'})")

        plan = strip(conn, keep, apply=False, purge_history=args.purge_history)
        print("\n  آنچه پاک می‌شود:")
        print(f"    برچسب آگهی در store_listings   {plan['listings']:>7,}")
        print(f"    دسته‌ی ai/manual               {plan['categories']:>7,}")
        print(f"    کل ai_review_cache            {plan['ai_cache']:>7,}")
        if plan["history"]:
            print(f"    category_history              {plan['history']:>7,}")
        print(f"    {'— هیچ ردیفی حذف نمی‌شود، فقط برچسب صفر می‌شود —':^7}")

        if not args.apply:
            print("\n✋ پیش‌نمایش بود؛ چیزی نوشته نشد. برای نوشتن: --apply")
            return 0

        if not args.no_backup:
            bak = db.with_suffix(db.suffix + f".bak-strip-{datetime.now():%Y%m%d-%H%M%S}")
            conn.close()
            shutil.copy2(db, bak)
            print(f"\n💾 نسخه‌ی پشتیبان: {bak.name}")
            conn = sqlite3.connect(db)

        strip(conn, keep, apply=True, purge_history=args.purge_history)

        # راستی‌آزمایی پس از نوشتن: فقط exit code صفر ملاک نیست.
        after = audit(conn, keep)
        total_after = after["total_listings"]
        ok = True
        if total_after != a["total_listings"]:
            print(f"\n❌ تعداد ردیف‌ها عوض شد: {a['total_listings']:,} → "
                  f"{total_after:,}. این ابزار نباید ردیفی حذف کند.")
            ok = False
        if after["ai_cache_rows"] != 0:
            print(f"\n❌ ai_review_cache خالی نشد: {after['ai_cache_rows']:,} ردیف مانده")
            ok = False
        if after["labeled_rows"] > len(keep):
            print(f"\n❌ {after['labeled_rows']:,} ردیف هنوز برچسب دارد ولی فقط "
                  f"{len(keep):,} رأی ایجنت نگه‌داشته شد")
            ok = False
        if not ok:
            print("   ⛔ نتیجه با انتظار نمی‌خواند. از نسخه‌ی پشتیبان برگردان.")
            return 1

        print(f"\n✅ نوشته شد و راستی‌آزمایی شد.")
        print(f"   ردیف‌ها: {total_after:,} (هیچ حذفی نشد)")
        print(f"   برچسب‌دارِ باقی‌مانده: {after['labeled_rows']:,} = رأی‌های ایجنت")
        print(f"   ai_review_cache: {after['ai_cache_rows']:,}")
        print("\n   بعدی: python3 apply_decisions_to_db.py --apply")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
