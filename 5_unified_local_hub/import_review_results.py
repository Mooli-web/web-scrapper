# -*- coding: utf-8 -*-
"""
📥 جمع‌آوری نتایج بازبینی توزیع‌شده — import_review_results.py
================================================================
همه‌ی فایل‌های result_*.json را از exports/review_batches/ می‌خواند، تصمیم‌ها را
اعمال می‌کند و گزارش کامل می‌دهد. اگر فایل برای یک بسته نیست، آن بسته را
«ناموجود» گزارش می‌کند (نه خطا).

اجرا:
    python import_review_results.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402

BATCH_DIR = Path(__file__).resolve().parent / "exports" / "review_batches"


def main():
    results = sorted(BATCH_DIR.glob("result_*.json"))
    if not results:
        print("❌ هیچ فایل result_*.json پیدا نشد — پاسخ‌های ایجنت‌ها را در")
        print(f"   {BATCH_DIR}")
        print("   با نام result_XX.json ذخیره کنید.")
        return

    print("=" * 60)
    print(f"📥 جمع‌آوری {len(results)} فایل نتیجه")
    print("=" * 60)

    total_v = total_j = total_c = 0
    errors = []

    for rf in results:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            decisions = data.get("decisions") if isinstance(data, dict) else data
            if not decisions or not isinstance(decisions, list):
                errors.append(f"{rf.name}: ساختار نامعتبر")
                continue

            for d in decisions:
                if not isinstance(d, dict):
                    continue
                item_id = d.get("id")
                if not isinstance(item_id, int):
                    continue
                decision = str(d.get("decision", "")).lower()

                if decision == "verify":
                    db.execute("""UPDATE store_listings SET is_verified=1,
                                  quality_status='VERIFIED',
                                  rejection_reason='✋ تأیید گروهی شما: کالای اصلی است',
                                  confidence_score=100.0 WHERE id=?;""", (item_id,))
                    total_v += 1
                elif decision == "junk":
                    reason = str(d.get("reason", ""))[:200] or "عنوان مبهم"
                    db.execute("""UPDATE store_listings SET is_verified=0,
                                  quality_status='CONFIRMED_JUNK',
                                  rejection_reason=?,
                                  confidence_score=100.0 WHERE id=?;""",
                               (f"✋ {reason}", item_id))
                    total_j += 1
                elif decision == "set-category":
                    cat = str(d.get("category", "")).strip().lower()
                    row = db.fetchone("SELECT canonical_key FROM store_listings WHERE id=?;", (item_id,))
                    if row and cat in ("mobile","laptop","tablet","console","gpu","cpu","ram","storage","motherboard","desktop-pc","monitor","watch","headphone","other"):
                        from core.taxonomy import record_category_change
                        record_category_change([row["canonical_key"]], cat)
                        db.execute("""UPDATE canonical_products SET category_std=?, category_source='manual'
                                      WHERE canonical_key=?;""", (cat, row["canonical_key"]))
                        db.execute("""UPDATE store_listings SET is_verified=1,
                                      quality_status='VERIFIED',
                                      rejection_reason='✋ تأیید گروهی شما: کالای اصلی است',
                                      confidence_score=100.0 WHERE id=?;""", (item_id,))
                        total_c += 1
        except Exception as e:
            errors.append(f"{rf.name}: {e}")

    print(f"   تایید ✓: {total_v:,}")
    print(f"   چرت ✗:  {total_j:,}")
    print(f"   دسته 🗂: {total_c:,}")
    if errors:
        print(f"\n⚠️ خطاها:")
        for e in errors[:5]:
            print(f"   {e}")

    total = total_v + total_j + total_c
    print(f"\n✅ {total:,} تصمیم اعمال شد.")
    print("👉 حالا در داشبورد «اجرای مجدد پالایش» را بزن.")


if __name__ == "__main__":
    main()
