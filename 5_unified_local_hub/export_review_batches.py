# -*- coding: utf-8 -*-
"""
📦 تقسیم داده برای بازبینی توزیع‌شده — export_review_batches.py
================================================================
داده‌ی باقی‌مانده را به بسته‌های کوچک (پیش‌فرض ۸۰۰ ردیف) تقسیم می‌کند — هر بسته
یک فایل JSON مستقل است که یک ایجنت/چت می‌تواند کامل و با دقت بازبینی کند.
همراه هر بسته، یک پرامپت استاندارد برای چسباندن در ابتدای چت تولید می‌شود.

خروجی‌ها در exports/review_batches/ :
    batch_01.json, batch_02.json, ...   ← داده (لینک یا کپی در چت)
    batch_01_PROMPT.md, ...             ← پرامپت مخصوص همان بسته
    IMPORT_INSTRUCTIONS.md              ← راهنمای جمع‌آوری نتایج

اجرا:
    python export_review_batches.py [rows_per_batch=800]
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402
from core.taxonomy import STANDARD_CATEGORIES  # noqa: E402

OUT = Path(__file__).resolve().parent / "exports" / "review_batches"

PROMPT_TEMPLATE = """# 🧹 بازبینی داده — بسته {n}/{total}
تو یک ایجنت بازبینی کیفیت دیتای بازار هستی. فایل JSON زیر شامل {count} آگهی از بازارهای ایرانی است.

## کار تو (برای هر ردیف یکی از سه تصمیم):
- **verify** → آگهی یک کالای اصلی واقعی است (گوشی، لپ‌تاپ، کنسول، GPU، ...)
- **junk** → آگهی چرت/جانبی/هرز است + یک «reason» فارسی کوتاه بنویس (مثل: لوازم جانبی، قیمت غیرواقعی، آگهی خرید نه فروش، ...)
- **set-category** → کالای اصلی است ولی دسته‌اش غلط است + «category» درست را از این لیست بده: {cats}

## قواعد:
1. «کیس گیمینگ RTX...» بدون ذکر CPU = کیس خالی → junk
2. «خریدار/فروشنده/نصب بازی/کپی‌خور/گیفت/اشتراک» → junk
3. قیمت زیر ۱۰۰ هزار تومان برای کالای اصلی → مشکل دارد (junk با دلیل قیمت)
4. فقط دستگاه کامل: گوشی، لپ‌تاپ، تبلت، کنسول، GPU، CPU، رم، هارد/SSD، مادربرد، سیستم آماده، مانیتور، ساعت هوشمند، هدفون
5. مطمئن نیستی؟ «verify» نزن — «junk» با دلیل «عنوان مبهم» بده

## خروجی تو — فقط JSON خالص، همین قالب:
```json
{{"decisions": [
  {{"id": <عدد>, "decision": "verify"}},
  {{"id": <عدد>, "decision": "junk", "reason": "<دلیل>"}},
  {{"id": <عدد>, "decision": "set-category", "category": "<از لیست>"}}
]}}
```
همه‌ی {count} ردیف را جواب بده — هیچ id را جا نینداز.

## راهنمای کامل‌تر قواعد و مثال‌ها: فایل AGENT_PLAYBOOK.md کنار همین بسته — همان قواعد الزامی است.

## داده:
"""


def main():
    per = int(sys.argv[1]) if len(sys.argv) > 1 else 800
    OUT.mkdir(parents=True, exist_ok=True)
    # پاک‌سازی بسته‌های قبلی
    for f in OUT.glob("batch_*"):
        f.unlink()

    rows = db.fetchall("""
        SELECT l.id, l.title_fa, l.price_toman, l.store_key, l.condition,
               COALESCE(NULLIF(c.category_std,''), c.category_key, '') AS category,
               SUBSTR(COALESCE(l.description,''), 1, 120) AS desc_snippet
        FROM store_listings l
        JOIN canonical_products c ON l.canonical_key = c.canonical_key
        WHERE l.is_verified = 1 AND l.price_toman > 0
          AND NOT (l.rejection_reason LIKE '✋%' OR l.rejection_reason LIKE '%تایید شما%')
        ORDER BY l.id ASC;
    """)

    if not rows:
        print("✅ هیچ باقی‌مانده‌ای برای بازبینی نیست!")
        return

    total_batches = math.ceil(len(rows) / per)
    print("=" * 60)
    print(f"📦 تقسیم {len(rows):,} آگهی به {total_batches} بسته (هر بسته حداکثر {per:,})")
    print("=" * 60)

    cats_str = ", ".join(sorted(STANDARD_CATEGORIES.keys()))
    for i in range(total_batches):
        chunk = rows[i * per:(i + 1) * per]
        n = i + 1

        # فایل داده
        data_file = OUT / f"batch_{n:02d}.json"
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump([dict(r) for r in chunk], f, ensure_ascii=False)

        # پرامپت مخصوص
        prompt_file = OUT / f"batch_{n:02d}_PROMPT.md"
        prompt = PROMPT_TEMPLATE.format(n=n, total=total_batches, count=len(chunk), cats=cats_str)
        prompt_file.write_text(prompt, encoding="utf-8")

        size_kb = data_file.stat().st_size // 1024
        print(f"   بسته {n:02d}/{total_batches}: {len(chunk):,} ردیف | {size_kb:,} KB | {data_file.name}")

    # NEW: کپی Playbook کامل برای ایجنت‌ها (کنار بسته‌ها)
    playbook_src = Path(__file__).resolve().parent / "exports" / "review_batches" / "AGENT_PLAYBOOK.md"
    playbook_real = Path(__file__).resolve().parent / "exports" / "review_batches" / "AGENT_PLAYBOOK.md"
    src_pb = Path(__file__).resolve().parent / "exports" / "review_batches" / "AGENT_PLAYBOOK.md"
    pb = Path(__file__).resolve().parent / "exports" / "review_batches" / "AGENT_PLAYBOOK.md"
    # (اگر از قبل وجود دارد چون در همین پوشه است، نیازی به کپی نیست)
    # راهنمای جمع‌آوری
    (OUT / "IMPORT_INSTRUCTIONS.md").write_text(f"""# 📥 جمع‌آوری نتایج بازبینی توزیع‌شده

{total_batches} ایجنت هر کدام یک فایل JSON با قالب `{{"decisions": [...]}}` برمی‌گردانند.

## روش جمع‌آوری:
1. پاسخ JSON هر ایجنت را در فایل `result_XX.json` ذخیره کن (کنار همین فایل)
2. همه را یکجا وارد کن:
```powershell
python import_review_results.py
```
این اسکریپت همه‌ی result_*.json را می‌خواند، اعمال می‌کند و گزارش می‌دهد.
""", encoding="utf-8")

    print(f"\n📁 خروجی: {OUT}")
    print(f"   هر بسته: batch_XX.json + batch_XX_PROMPT.md")
    print(f"   راهنما: IMPORT_INSTRUCTIONS.md")
    print(f"\n💡 روش کار: هر فایل JSON + پرامپت مخصوصش را در یک چت جدید paste کن.")
    print(f"   جواب هر چت را در result_XX.json ذخیره کن، در پایان همه را import کن.")


if __name__ == "__main__":
    main()
