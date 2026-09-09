#!/usr/bin/env python3
"""نشاندن دفترکل بازبینی روی دیتابیس بازار.

دفترکل (exports/review/decisions.jsonl) ضمیمه‌ای است: یک آگهی ممکن است چند بار
تصمیم گرفته باشد. این ابزار «آخرین رأی» هر آگهی را می‌گیرد و روی
store_listings / canonical_products می‌نشاند.

قاعده‌ی سفت: **هیچ ردیفی حذف نمی‌شود.** کالای حذف‌شده فقط
quality_status='CONFIRMED_JUNK' می‌گیرد تا هم برگشت‌پذیر باشد و هم در آمار
بماند. پیش‌فرض dry-run است؛ نوشتن فقط با --apply.

    python3 apply_decisions_to_db.py                 # پیش‌نمایش
    python3 apply_decisions_to_db.py --apply         # نوشتن (با نسخه‌ی پشتیبان)
    python3 apply_decisions_to_db.py --db مسیر.db --apply
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent
LEDGER = HUB / "exports" / "review" / "decisions.jsonl"
DEFAULT_DB = HUB / "data" / "market.db"

# نگاشت تصمیم → وضعیت کیفی. «کنارگذاشته» یعنی از آموزش بیرون می‌ماند ولی
# برچسب قطعی نخورده.
STATUS = {
    "verify": "VERIFIED",
    "junk": "CONFIRMED_JUNK",
    "uncertain": "NEEDS_REVIEW",
}

REASON_FA = {
    "OUT_OF_SCOPE": "خارج از حوزه: کالای کلکسیونی/غیردیجیتال",
    "PRICE_BELOW_FLOOR": "قیمت اعلامی زیر کف معتبر است",
    "PRICE_PLACEHOLDER": "قیمت جای‌نگهدار (ارقام تکراری)",
    "PRICE_UNREALISTIC": "قیمت غیرواقعی برای این برند/مدل",
    "TRADE_REQUEST": "درخواست معاوضه، نه فروش کالا",
    "PARTS_OR_BROKEN": "قطعه/کالای معیوب یا اوراقی",
    "SERVICE_NOT_PRODUCT": "خدمات است نه کالا",
    "COUNTERFEIT_CLAIM": "ادعای کالای طرح/کپی از برند دیگر",
    "AMBIGUOUS_NO_MODEL": "عنوان مبهم بدون نوع/مدل مشخص",
    "ACCESSORY": "لوازم جانبی که به‌جای خود کالا آگهی شده",
    "BUNDLE_UNPRICED": "بسته‌ی چندقلمی بدون قیمت تفکیکی",
}


def latest_decisions(path: Path = LEDGER) -> dict[int, dict]:
    """آخرین رأی هر آگهی (رکوردهای خوشه‌ای روی آگهی‌هایشان باز می‌شوند)."""
    out: dict[int, dict] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("scope") == "audit":
                continue          # ممیزی کور رأی جدید نیست، فقط سنجش است
            ids = r.get("affected_ids") or (
                [r["ref"]] if isinstance(r.get("ref"), int) else [])
            for i in ids:
                out[i] = r
    return out


def _existing(conn: sqlite3.Connection) -> dict[int, tuple]:
    rows = conn.execute(
        "SELECT id, is_verified, quality_status, canonical_key FROM store_listings"
    ).fetchall()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def project(conn: sqlite3.Connection, decisions: dict[int, dict], apply: bool):
    """تصمیم‌ها را روی دیتابیس می‌نشاند. خروجی: گزارش شمارش‌ها."""
    have = _existing(conn)
    plan: Counter = Counter()
    missing: list[int] = []
    changed = skipped = 0
    cat_by_key: dict[str, str] = {}

    for lid, d in sorted(decisions.items()):
        if lid not in have:
            missing.append(lid)
            continue
        old_verified, old_status, ckey = have[lid]
        dec = d["decision"]
        if dec == "set-category":
            # بازطبقه‌بندی خالص: وضعیت دست نمی‌خورد
            cat = d.get("category")
            if ckey and cat:
                cat_by_key[ckey] = cat
            plan["set-category"] += 1
            continue
        new_status = STATUS[dec]
        new_verified = 1 if dec == "verify" else 0
        if dec == "verify" and d.get("category") and ckey:
            cat_by_key[ckey] = d["category"]
        if dec == "junk":
            code = d.get("reason_code") or ""
            reason = f"[{code}] {REASON_FA.get(code, 'حذف‌شده در بازبینی دستی')}"
        elif dec == "uncertain":
            reason = "نامطمئن: از مجموعه‌ی آموزش بیرون می‌ماند"
        else:
            reason = ""
        plan[f"{dec}:{new_status}"] += 1
        if (old_verified, old_status) == (new_verified, new_status):
            skipped += 1
            continue
        changed += 1
        if apply:
            conn.execute(
                "UPDATE store_listings SET is_verified=?, quality_status=?, "
                "rejection_reason=?, confidence_score=? WHERE id=?",
                (new_verified, new_status, reason,
                 100.0 if dec == "verify" else 0.0, lid),
            )
    if apply:
        for ckey, cat in cat_by_key.items():
            conn.execute(
                "UPDATE canonical_products SET category_key=? WHERE canonical_key=?",
                (cat, ckey),
            )
    plan["category_updates"] = len(cat_by_key)
    plan["_changed"] = changed
    plan["_skipped"] = skipped
    plan["_missing"] = len(missing)
    return plan, missing, cat_by_key


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB), help="مسیر market.db")
    ap.add_argument("--ledger", default=str(LEDGER))
    ap.add_argument("--apply", action="store_true",
                    help="واقعاً بنویس (پیش‌فرض: پیش‌نمایش)")
    ap.add_argument("--no-backup", action="store_true",
                    help="نسخه‌ی پشتیبان نگیر (پیش‌فرض: می‌گیرد)")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"❌ دیتابیس پیدا نشد: {db}")
        return 1
    decisions = latest_decisions(Path(args.ledger))
    print(f"📒 دفترکل: {len(decisions)} آگهی با رأی قطعی")

    conn = sqlite3.connect(db)
    try:
        # ۱) همیشه اول پیش‌نمایش (بدون نوشتن)
        plan, missing, _cats = project(conn, decisions, apply=False)
        print("\nبرنامه‌ی اجرا:")
        for k in sorted(k for k in plan if not k.startswith("_")):
            print(f"   {k:<34} {plan[k]:>6}")
        print(f"\n   بدون تغییر (از قبل همین وضعیت)   {plan['_skipped']:>6}")
        print(f"   آگهیِ حاضر در دفترکل ولی نه در دیتابیس {plan['_missing']:>6}")
        if missing[:5]:
            print(f"   نمونه: {missing[:5]}")
        if not args.apply:
            print("\n✋ پیش‌نمایش بود؛ چیزی نوشته نشد. برای نوشتن: --apply")
            return 0
        # ۲) پشتیبان «پیش از» هر نوشتن
        if not args.no_backup:
            bak = db.with_suffix(db.suffix + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
            conn.close()
            shutil.copy2(db, bak)
            print(f"\n💾 نسخه‌ی پشتیبان: {bak.name}")
            conn = sqlite3.connect(db)
        # ۳) نوشتن در یک تراکنش
        with conn:
            project(conn, decisions, apply=True)
        print("✅ نوشته شد.")
        n = conn.execute(
            "SELECT quality_status, COUNT(*) FROM store_listings GROUP BY 1 "
            "ORDER BY 2 DESC").fetchall()
        print("\nوضعیت کیفی دیتابیس پس از اجرا:")
        for s, c in n:
            print(f"   {s or '(خالی)':<22} {c:>7}")
    except Exception as e:                      # noqa: BLE001
        conn.rollback()
        print(f"❌ برگردانده شد: {e}")
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
