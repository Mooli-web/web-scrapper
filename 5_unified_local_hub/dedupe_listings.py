# -*- coding: utf-8 -*-
"""
🧹 حذف آگهی‌های تکراری (دقیق + فازی) — dedupe_listings.py
============================================================
دو گذر:

  گذر ۱ (دقیق): همان فروشگاه + همان عنوانِ نرمال‌شده + همان قیمت ⇒ تکراری قطعی.
  گذر ۲ (فازی) NEW: همان فروشگاه + همان محصولِ کانونیکال + پوشش عنوان ≥ ۹۰٪
     (قیمت‌ها ممکن است کمی فرق کنند — نمونه‌ی واقعی: آگهی دوبار‌پست‌شده با
     قیمت چانه‌زده‌شده). ایمن است چون canonical_key خودش مدل را یکسان‌سازی کرده.

اجرا (پوشه 5_unified_local_hub):
    python dedupe_listings.py               # گزارش هر دو گذر (بدون حذف)
    python dedupe_listings.py --purge       # حذف دقیق + فازی (جدیدترین می‌ماند)
    python dedupe_listings.py --purge --exact-only   # فقط گذر دقیق

نکته: چند آگهیِ متفاوت از فروشندگان مختلف برای «یک محصول» تکرار نیست —
داده‌ی معتبر رقابتی است و حذف نمی‌شود (معیار ما همان-فروشگاه است).
"""

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402
from core.normalizer import clean_persian_text  # noqa: E402

SIM_THRESHOLD = 0.90


def _tok_sim(a: str, b: str) -> float:
    """پوششِ کوتاه‌ترین عنوان داخل بلندترین — مقاوم در برابر کلمات افزوده."""
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    if inter < 3:          # عنوان‌های خیلی کوتاه — ریسک تشابه کاذب
        return 0.0
    return inter / min(len(wa), len(wb))


def find_exact_groups():
    rows = db.fetchall("SELECT id, store_key, item_id, title_fa, price_toman FROM store_listings ORDER BY id ASC;")
    groups = defaultdict(list)
    for r in rows:
        key = (r["store_key"], clean_persian_text(r["title_fa"] or "").lower(), r["price_toman"] or 0)
        groups[key].append(r)
    return {k: v for k, v in groups.items() if len(v) > 1}


def find_fuzzy_groups():
    rows = db.fetchall("""
        SELECT l.id, l.store_key, l.item_id, l.title_fa, l.price_toman, l.canonical_key
        FROM store_listings l ORDER BY l.id ASC;
    """)
    buckets = defaultdict(list)
    for r in rows:
        buckets[(r["store_key"], r["canonical_key"])].append(r)

    groups = []
    for bucket in buckets.values():
        if len(bucket) < 2 or len(bucket) > 80:
            continue
        clusters = []
        for r in bucket:
            placed = False
            for cl in clusters:
                if _tok_sim(clean_persian_text(cl[0]["title_fa"] or "").lower(),
                            clean_persian_text(r["title_fa"] or "").lower()) >= SIM_THRESHOLD:
                    cl.append(r)
                    placed = True
                    break
            if not placed:
                clusters.append([r])
        groups.extend(cl for cl in clusters if len(cl) > 1)
    return groups


def _show(title, groups, unit):
    print(f"\n—— {title}: {len(groups):,} گروه | {unit:,} ردیف اضافه ——")
    for g in sorted(groups, key=len, reverse=True)[:6]:
        if isinstance(g, list):
            r0 = g[0]
            print(f"   {len(g)}× | {(r0['title_fa'] or '')[:44]} | {sorted(x['price_toman'] or 0 for x in g)[:3]} | {r0['store_key']}")


def _purge(groups):
    deleted = 0
    for g in (groups.values() if isinstance(groups, dict) else groups):
        keep = max(r["id"] for r in g)
        for r in g:
            if r["id"] != keep:
                db.execute("DELETE FROM store_listings WHERE id=?;", (r["id"],))
                deleted += 1
    return deleted




def dedupe_exact_quiet() -> int:
    """NEW: حذف بی‌صدا‌ی تکراری‌های دقیق برای چرخه‌ی خودکار (خروجی: تعداد حذف)."""
    groups = find_exact_groups()
    if not groups:
        return 0
    return _purge(groups)

def main():
    purge = "--purge" in sys.argv
    exact_only = "--exact-only" in sys.argv
    print("=" * 62)
    print("🧹 گزارش تکراری‌ها (گذر دقیق + گذر فازی)")
    print("=" * 62)

    exact = find_exact_groups()
    extra_exact = sum(len(v) - 1 for v in exact.values())
    _show("گذر ۱ — دقیق (عنوان+قیمت یکسان)", list(exact.values()), extra_exact)

    fuzzy = []
    extra_fuzzy = 0
    if not exact_only:
        fuzzy = find_fuzzy_groups()
        extra_fuzzy = sum(len(g) - 1 for g in fuzzy)
        _show("گذر ۲ — فازی (همان محصول، پوشش ≥۹۰٪، قیمت متفاوت)", fuzzy, extra_fuzzy)

    if not purge:
        print(f"\n🔍 حالت گزارش — چیزی حذف نشد. برای حذف: --purge (یا --purge --exact-only)")
        return

    d1 = _purge(exact)
    d2 = 0
    if not exact_only:
        d2 = _purge(fuzzy)
    print(f"\n✅ دقیق: {d1:,} حذف | فازی: {d2:,} حذف (جدیدترین نسخه‌ی هر گروه ماند)")
    print("👉 در داشبورد «اجرای مجدد پالایش» را بزن.")


if __name__ == "__main__":
    main()
