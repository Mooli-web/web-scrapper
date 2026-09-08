# -*- coding: utf-8 -*-
"""
🐞 دیباگ کامل برچسب‌های انسانی — debug_labels.py
==================================================
سه آزمایش مستقل — هر کدام جداگانه PASS/FAIL می‌دهد تا دقیقاً معلوم شود
مشکل (اگر باشد) در کدام لایه است:

  A) دیتابیس: چه چیزهایی واقعاً ذخیره شده؟ (هیستوگرام وضعیت‌ها + همه‌ی
    _variantهای متن تایید + نمونه‌ها با بایت‌های واقعی hex)
  B) سرور زنده: endpoint شمارنده چه برمی‌گرداند؟ (اگر هاب روشن باشد)
  C) مسیر نوشتن: یک ردیف آزمایشی می‌سازد، با همان مسیرِ دکمه‌ی ✅ تایید
     می‌کند، پس می‌خواند، و در پایان پاک می‌کند — write-path تست می‌شود.

اجرا:  python debug_labels.py [category]
(پیش‌فرض category=mobile)
"""

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402

HUMAN_PATTERNS = [
    ("✋ در ابتدای دلیل", "rejection_reason LIKE '✋%'"),
    ("«تایید گروهی شما»", "rejection_reason LIKE '%تایید گروهی شما%'"),
    ("«تایید شما»", "rejection_reason LIKE '%تایید شما%'"),
    ("«تأیید ... شما» (با ئ عربی)", "rejection_reason LIKE '%تأیید%شما%'"),
    ("«تائید ... شما»", "rejection_reason LIKE '%تائید%شما%'"),
]


def section_a():
    print("\n" + "—" * 20 + " A) دیتابیس " + "—" * 20)
    total = db.fetchone("SELECT COUNT(*) c FROM store_listings;")["c"]
    verified = db.fetchone("SELECT COUNT(*) c FROM store_listings WHERE is_verified=1;")["c"]
    print(f"کل آگهی‌ها: {total:,} | تاییدشده: {verified:,}")

    hist = db.fetchall("""SELECT quality_status, COUNT(*) n FROM store_listings GROUP BY 1 ORDER BY n DESC;""")
    print("هیستوگرام وضعیت‌ها:")
    for h in hist:
        print(f"   {h['quality_status'] or '(خالی)':20s} {h['n']:,}")

    print("شمارش variantهای متنِ تایید انسانی (مجموع این‌ها = عدد ✋):")
    total_human = 0
    for label, cond in HUMAN_PATTERNS:
        n = db.fetchone(f"SELECT COUNT(*) c FROM store_listings WHERE is_verified=1 AND {cond};")["c"]
        total_human += n
        print(f"   {label:32s} {n:,}")
    union = db.fetchone("SELECT COUNT(*) c FROM store_listings WHERE is_verified=1 AND (" +
                        " OR ".join(c for _, c in HUMAN_PATTERNS) + ");")["c"]
    print(f"   {'مجموع (بدون تداخل)':32s} {union:,}")

    recent = db.fetchall("""SELECT id, item_id, rejection_reason FROM store_listings
                            WHERE is_verified=1 AND rejection_reason != ''
                            ORDER BY id DESC LIMIT 5;""")
    print("۵ دلیلِ اخیر (با hex بایت‌های ابتدایی):")
    for r in recent:
        hx = (r["rejection_reason"] or "")[:8].encode("utf-8").hex()
        print(f"   id={r['id']} ({r['item_id']}) hex={hx} | «{(r['rejection_reason'] or '')[:45]}»")
    return union


def section_b(category):
    print("\n" + "—" * 20 + " B) سرور زنده " + "—" * 20)
    try:
        import requests
        r = requests.get(f"http://localhost:7000/api/analytics/category-products",
                         params={"category": category, "limit": 1}, timeout=6)
        d = r.json()
        print(f"HTTP {r.status_code} | api_build={d.get('api_build')} | دسته={d.get('category')}")
        print(f"   products={d.get('total')} | listings={d.get('listings_total')} | "
              f"✋ محصول={d.get('human_verified_products')} آگهی={d.get('human_verified_listings')}")
        item = (d.get("items") or [{}])[0]
        print(f"   نمونه‌ی اولین آیتم: is_human_verified={item.get('is_human_verified', 'فیلد نیست!')}")
        if not d.get("api_build"):
            print("   ⚠️ api_build نیست — سرور کد قدیمی اجرا می‌کند (ری‌استارت لازم)")
        return d
    except Exception as e:
        print(f"⚠️ سرور در دسترس نیست ({type(e).__name__}) — بخش B رد شد")
        return None


def section_c():
    print("\n" + "—" * 20 + " C) مسیر نوشتن (تست end-to-end) " + "—" * 20)
    key = "debug_write_test_product"
    try:
        db.execute("DELETE FROM store_listings WHERE canonical_key=?;", (key,))
        db.execute("DELETE FROM canonical_products WHERE canonical_key=?;", (key,))
        db.execute("""INSERT INTO canonical_products (canonical_key, title_fa, brand, category_key)
                      VALUES (?, ?, 'other', 'digital');""", (key, "آزمایش دیباگ — هدفون تست"))
        db.execute("""INSERT INTO store_listings
                      (canonical_key, store_key, item_id, title_fa, price_toman, condition, quality_status)
                      VALUES (?, 'divar', 'debug_item_1', 'آزمایش دیباگ — هدفون تست', 1000000, 'کارکرده', 'VERIFIED');""",
                   (key,))
        row_id = db.fetchone("SELECT id FROM store_listings WHERE canonical_key=? AND item_id='debug_item_1';", (key,))["id"]

        from core.data_cleaner import data_purifier
        applied = data_purifier.apply_agent_decisions(
            [{"id": row_id, "decision": "VERIFIED", "reason": "✋ تأیید دیباگ", "confidence": 100.0}])
        back = db.fetchone("SELECT is_verified, quality_status, rejection_reason FROM store_listings WHERE id=?;", (row_id,))
        hex_reason = (back["rejection_reason"] or "")[:8].encode("utf-8").hex()
        ok = applied == 1 and back["is_verified"] == 1 and back["rejection_reason"].startswith("✋")
        print(f"نوشت: applied={applied} | خواند: verified={back['is_verified']} دلیل hex={hex_reason}")
        print(f"   {'✅ PASS — مسیر نوشتن سالم است' if ok else '❌ FAIL — مسیر نوشتن مشکل دارد!'}")
        return ok
    finally:
        db.execute("DELETE FROM store_listings WHERE canonical_key=?;", (key,))
        db.execute("DELETE FROM canonical_products WHERE canonical_key=?;", (key,))
        print("   (ردیف آزمایشی پاک شد)")


def main():
    category = sys.argv[1] if len(sys.argv) > 1 else "mobile"
    print("=" * 62)
    print(f"🐞 دیباگ کامل برچسب‌های انسانی (دسته: {category})")
    print("=" * 62)
    union = section_a()
    srv = section_b(category)
    write_ok = section_c()

    print("\n" + "=" * 62)
    print("🧾 جمع‌بندی خودکار:")
    db_total = db.fetchone("SELECT COUNT(*) c FROM store_listings WHERE is_verified=1 AND rejection_reason LIKE '%شما%';")["c"]
    if srv and srv.get("human_verified_listings", 0) == 0 and union > 0:
        print("   ❌ دیتابیس برچسب دارد ولی سرور صفر می‌دهد → کد سرور قدیمی/ناسازگار است (ری‌استارت + فایل جدید)")
    elif srv and srv.get("human_verified_listings") not in (None, 0):
        print(f"   ✅ شمارنده‌ی سرور کار می‌کند ({srv['human_verified_listings']} آگهی ✋ در «{srv.get('category')}»)")
        print("   ℹ️ این عدد مال همین دسته است — برای دیدن مجموع، دسته‌های دیگر را هم باز کنید")
    if write_ok:
        print("   ✅ ذخیره‌سازی تایید سالم است — اگر آگهی «به نظر» ذخیره نمی‌شود،")
        print("      مشکل نمایش است: از این به بعد ردیف‌های تاییدشده نشان «✓ تاییدشده» دارند")
    print("   ℹ️ عدد «آگهی تاییدشده» (کل) با تاییدِ شما تغییر نمی‌کند — آن آگهی‌ها از قبل")
    print("      تایید بودند؛ متریکی که بالا می‌رود «✋ ... با تایید شما» است.")


if __name__ == "__main__":
    main()
