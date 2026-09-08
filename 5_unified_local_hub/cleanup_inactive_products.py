# -*- coding: utf-8 -*-
"""
🧟 پاکسازی محصولات زامبی — cleanup_inactive_products.py
========================================================
«محصول زامبی» = محصول کانونیکالی که هیچ آگهی تاییدشده‌ای ندارد — معمولاً
ساخته‌شده توسط آگهی‌های چرتی که بعداً رد شده‌اند. این‌ها آمار «تعداد محصولات»
را متورم می‌کنند (نمونه‌ی واقعی: متفرقه ۳,۳۵۱ محصول با فقط ۲۸ آگهی).

اجرا (پوشه 5_unified_local_hub):

    python cleanup_inactive_products.py            # فقط گزارش (dry-run)
    python cleanup_inactive_products.py --purge    # حذف واقعی

حذف شامل: محصول زامبی + آگهی‌های ردشده‌ی آن (کلاً چرت) + تاریخچه قیمت آن.
کش AI دست‌نخورده می‌ماند. قبل از purge به‌صورت خودکار بکاپ از دیتابیس گرفته می‌شود.
"""

import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402


def find_zombies():
    rows = db.fetchall("""
        SELECT c.canonical_key, c.title_fa, c.brand,
               (SELECT COUNT(*) FROM store_listings l
                 WHERE l.canonical_key = c.canonical_key) AS listings,
               (SELECT COUNT(*) FROM store_listings l
                 WHERE l.canonical_key = c.canonical_key AND l.is_verified = 1) AS verified
        FROM canonical_products c
        WHERE NOT EXISTS (
            SELECT 1 FROM store_listings l
            WHERE l.canonical_key = c.canonical_key AND l.is_verified = 1
        );
    """)
    return rows


def main():
    purge = "--purge" in sys.argv
    print("=" * 62)
    print("🧟 پاکسازی محصولات زامبی (بدون آگهی تاییدشده)")
    print("=" * 62)

    zombies = find_zombies()
    total_products = (db.fetchone("SELECT COUNT(*) AS c FROM canonical_products;") or {"c": 0})["c"]
    zombie_listings = sum(z["listings"] for z in zombies)
    print(f"کل محصولات: {total_products:,}")
    print(f"زامبی: {len(zombies):,} محصول ({round(len(zombies)/max(total_products,1)*100,1)}٪)"
          f" با {zombie_listings:,} آگهیِ همراه (همگی ردشده)")

    # نمونه بر اساس برند
    from collections import Counter
    brands = Counter((z["brand"] or "other") for z in zombies)
    print("برندهای غالب زامبی‌ها:", ", ".join(f"{b}({n})" for b, n in brands.most_common(6)))
    print("\nنمونه:")
    for z in zombies[:8]:
        print(f"  • {(z['title_fa'] or '')[:55]}")

    if not purge:
        print("\n🔍 حالت گزارش (چیزی حذف نشد). برای حذف واقعی:  python cleanup_inactive_products.py --purge")
        return

    # بکاپ خودکار
    db_path = db.db_path
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.with_name(f"market_backup_zombies_{stamp}.db")
    shutil.copy2(db_path, backup)
    print(f"\n💾 بکاپ: {backup.name}")

    # NEW: پیش از حذف، ردشده‌های این محصولات به‌عنوان نمونه‌ی junk در آرشیو
    # آموزش ذخیره می‌شوند — هیچ داده‌ی حذف‌شده‌ای برای ML از دست نمی‌رود.
    import json as _json
    out = Path(__file__).resolve().parent / "exports" / "ml_training"
    out.mkdir(parents=True, exist_ok=True)
    arch = out / "purged_junk_archive.jsonl"
    keys_pre = [z["canonical_key"] for z in zombies]
    n_archived = 0
    for i in range(0, len(keys_pre), 400):
        chunk = keys_pre[i:i + 400]
        p = ",".join("?" * len(chunk))
        for r in db.fetchall(f"""
            SELECT title_fa, description, price_toman, store_key, quality_status, rejection_reason
            FROM store_listings WHERE canonical_key IN ({p});
        """, tuple(chunk)):
            with open(arch, "a", encoding="utf-8") as f:
                f.write(_json.dumps({
                    "title": r["title_fa"], "desc": (r["description"] or "")[:400],
                    "price": r["price_toman"] or 0, "store": r["store_key"],
                    "label": "junk",
                    "label_source": "human" if "✋" in (r["rejection_reason"] or "") else (
                        "ai" if (r["rejection_reason"] or "").startswith("🤖") else "rule"),
                    "reason": (r["rejection_reason"] or "")[:200],
                    "archived_from": "zombie-purge",
                }, ensure_ascii=False) + "\n")
            n_archived += 1
    if n_archived:
        print(f"🗄 {n_archived:,} ردیف به آرشیو آموزش افزوده شد: exports/ml_training/purged_junk_archive.jsonl")

    keys = [z["canonical_key"] for z in zombies]
    ph = ",".join("?" * len(keys))
    for i in range(0, len(keys), 400):
        chunk = keys[i:i + 400]
        p = ",".join("?" * len(chunk))
        db.execute(f"DELETE FROM price_history WHERE canonical_key IN ({p});", tuple(chunk))
        db.execute(f"DELETE FROM store_listings WHERE canonical_key IN ({p});", tuple(chunk))
        db.execute(f"DELETE FROM canonical_products WHERE canonical_key IN ({p});", tuple(chunk))

    remaining = (db.fetchone("SELECT COUNT(*) AS c FROM canonical_products;") or {"c": 0})["c"]
    print(f"✅ {len(keys):,} محصول زامبی + آگهی‌هایشان حذف شدند. محصولات باقی‌مانده: {remaining:,}")
    print("💡 حالا در داشبورد: «اجرای مجدد پالایش» + تب تحلیل را رفرش کن.")


if __name__ == "__main__":
    main()
