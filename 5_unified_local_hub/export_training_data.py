# -*- coding: utf-8 -*-
"""
🎓 خروجی دیتای آموزش ML — export_training_data.py
===================================================
زحمت انسانیِ شما (تغییر دسته‌ها، تاییدها، تیک‌های چرت) را به دیتاست‌های
استاندارد آموزش تبدیل می‌کند — برای هر مدلی (fastText، scikit-learn،
transformers، ...) نه فقط Groq.

سه خروجی در exports/ml_training/:

  ۱) category_train.jsonl — دسته‌بندی: (title, desc, brand, store, price) → category
     با label_source = manual | ai | rule (برای وزن‌دهی: manual قابل‌اعتمادترین)
  ۲) corrections.jsonl   — золوت آموزش: مثال‌های «قبلاً X بود، انسان Y کرد»
     (دارای old_category و new_category — دقیقاً جایی که مدل/قاعده اشتباه می‌کرد)
  ۳) quality_train.jsonl — کالا/چرت: (title, desc, price, store) → clean | junk
     با label_source = human | ai | rule

اجرا:  python export_training_data.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402
from core.taxonomy import ensure_category_columns  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "exports" / "ml_training"


def write_jsonl(name, rows):
    path = OUT_DIR / name
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path, len(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # FIX: این ستون‌ها/جدول در schema.sql نیستند و runtime ساخته می‌شوند؛
    # بدون این خط، روی دیتابیس نوساخته «no such column: c.category_std» می‌داد.
    ensure_category_columns()
    print("=" * 62)
    print("🎓 ساخت دیتاست‌های آموزش از برچسب‌های انسانی/AI")
    print("=" * 62)

    # ---------- ۱) دسته‌بندی ----------
    products = db.fetchall("""
        SELECT c.canonical_key, c.title_fa, c.category_std, c.category_source
        FROM canonical_products c
        WHERE COALESCE(c.category_std, '') != '';
    """)
    # نمونه‌ی متنی هر محصول: اولین آگهی با توضیحات
    texts = {}
    for r in db.fetchall("""
        SELECT canonical_key, MIN(title_fa) AS t, MIN(COALESCE(NULLIF(description, ''), '')) AS d
        FROM store_listings GROUP BY canonical_key;
    """):
        texts[r["canonical_key"]] = (r["t"] or "", r["d"] or "")

    cat_rows = []
    by_source = {"manual": 0, "ai": 0, "rule": 0}
    for p in products:
        t, d = texts.get(p["canonical_key"], ("", ""))
        src = p["category_source"] or "rule"
        by_source[src] = by_source.get(src, 0) + 1
        cat_rows.append({
            "title": t or p["title_fa"], "desc": (d or "")[:400],
            "brand": "", "store": "", "price": 0,
            "category": p["category_std"], "label_source": src,
        })
    p1, n1 = write_jsonl("category_train.jsonl", cat_rows)

    # ---------- ۲) اصلاحات انسانی (طلا) ----------
    hist = db.fetchall("""
        SELECT h.canonical_key, h.old_category, h.old_source, h.new_category, h.created_at
        FROM category_history h ORDER BY h.id ASC;
    """)
    corr_rows = []
    for h in hist:
        t, d = texts.get(h["canonical_key"], ("", ""))
        corr_rows.append({
            "title": t, "desc": (d or "")[:400],
            "old_category": h["old_category"] or "(unknown)",
            "old_source": h["old_source"] or "rule",
            "new_category": h["new_category"],
            "changed_by": "human", "changed_at": h["created_at"],
        })
    p2, n2 = write_jsonl("corrections.jsonl", corr_rows)

    # ---------- ۳) کیفیت (کالا/چرت) ----------
    listings = db.fetchall("""
        SELECT title_fa, description, price_toman, store_key, quality_status,
               rejection_reason, confidence_score
        FROM store_listings WHERE COALESCE(quality_status, '') != '' AND COALESCE(quality_status,'') != 'PENDING';
    """)
    JUNK = {"ACCESSORY_OR_JUNK", "DEFECTIVE_PARTS", "FAKE_PRICE", "CONFIRMED_JUNK", "AI_REJECTED", "REJECTED_BY_AGENT"}
    q_rows, q_by_src = [], {"human": 0, "ai": 0, "rule": 0}
    for l in listings:
        label = "clean" if l["quality_status"] == "VERIFIED" else "junk"
        reason = l["rejection_reason"] or ""
        if "✋" in reason or "Agent" in reason:
            src = "human"
        elif reason.startswith("🤖"):
            src = "ai"
        else:
            src = "rule"
        if l["quality_status"] == "CONFIRMED_JUNK":
            src = "human"
        q_by_src[src] = q_by_src.get(src, 0) + 1
        q_rows.append({
            "title": l["title_fa"], "desc": (l["description"] or "")[:400],
            "price": l["price_toman"] or 0, "store": l["store_key"],
            "label": label, "label_source": src, "confidence": l["confidence_score"] or 0,
            "reason": (l["rejection_reason"] or "")[:200],  # NEW: دلیل (خام) برای ML
        })
    p3, n3 = write_jsonl("quality_train.jsonl", q_rows)

    # ---------- گزارش ----------
    print(f"\n① {p1.name}: {n1:,} نمونه دسته‌بندی "
          f"(manual: {by_source.get('manual', 0):,} | ai: {by_source.get('ai', 0):,} | rule: {by_source.get('rule', 0):,})")
    print(f"② {p2.name}: {n2:,} اصلاح انسانی X→Y (طلات‌ترین بخش — مدل دقیقاً از اشتباهات می‌آموزد)")
    print(f"③ {p3.name}: {n3:,} نمونه کالا/چرت "
          f"(human: {q_by_src.get('human', 0):,} | ai: {q_by_src.get('ai', 0):,} | rule: {q_by_src.get('rule', 0):,})")
    if n2 == 0:
        print("\n💡 هنوز اصلاح دستی ثبت نشده — با دکمه 🗂 در داشبورد دسته عوض کن؛ هر تغییر از این به بعد ثبت می‌شود.")
    print(f"\n📁 خروجی: {OUT_DIR}")
    print("📊 جمع‌بندی: هرچه manual/human بیشتر، دیتاست گران‌بهاتر — این‌ها برچسب طلایی برای ML هستند.")


if __name__ == "__main__":
    main()
