#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بررسی کیفیت قیمت — پرچم‌گذاری قیمت‌های پرت با دقت بالا.

روش (محافظه‌کار، precision-محور):
  برای هر دسته، کرانه‌های قیمت از listingهای **نگه‌داشتنی** (verify/set-category)
  همان دسته محاسبه می‌شود — یعنی قیمتی که انسان‌ها تأیید کرده‌اند. سه سیگنال:

  1) BELOW_FLOOR  : قیمت زیر p1 نگه‌داشتنی‌های دسته  → غیرممکن/کلاهبرداری/placeholder
  2) ABOVE_CEILING: قیمت بالای (max نگه‌داشتنی‌ها × ۲) → اشتباه تایپی (مثلاً ۶۲۰ میلیارد)
  3) PLACEHOLDER  : ارقام تکراری (۱۱۱۱۱۱۱، ۵۵۵۵۵)      → قیمت ساختگی

چرا محافظه‌کار: قیمت ارزان می‌تواند «تخفیف واقعی» باشد، پس فقط موارد **قطعی**
(خیلی دور از کرانه) پرچم می‌شوند و برای بازبینی می‌روند، نه حذف خودکار.

خروجی:
  - exports/review/price_flags.jsonl   {id,title,price,category,signal,detail}
  - گزارش شمارش روی کنسول

اجرا:
    python price_check.py                # از باندل
    python price_check.py --source db    # از market.db
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from collections import defaultdict
import numpy as np

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))
from apply_decisions_to_db import latest_decisions  # noqa

REVIEW = HUB / "exports" / "review"
BUNDLE = HUB / "exports" / "training_bundle"
OUT = REVIEW / "price_flags.jsonl"
CEIL_MULT = 2.0          # سقف = max نگه‌داشتنی‌ها × این


def load_listings(source: str):
    if source == "db":
        from database.db_manager import LocalDatabaseManager
        db = LocalDatabaseManager()
        with db.get_connection() as c:
            return [{"id": r[0], "title": r[1] or "", "price": r[2] or 0}
                    for r in c.execute("SELECT id, title_fa, price_toman FROM store_listings")]
    return [{"id": json.loads(l)["id"], "title": json.loads(l).get("title_fa") or "",
             "price": json.loads(l).get("price_toman") or 0}
            for l in (BUNDLE / "listings.jsonl").read_text(encoding="utf-8").splitlines()]


def is_placeholder(price: int) -> bool:
    """ارقام تکراری: همه‌ی رقم‌ها یکی (و حداقل ۴ رقم)."""
    s = str(price)
    return len(s) >= 4 and len(set(s)) == 1


def category_bounds(listings, dec):
    """کف (p1) و سقف (max×CEIL_MULT) هر دسته از نگه‌داشتنی‌ها."""
    by_cat = defaultdict(list)
    for r in listings:
        d = dec.get(r["id"])
        if d and d.get("category") and r["price"] > 0 \
           and d.get("decision") in ("verify", "set-category"):
            by_cat[d["category"]].append(r["price"])
    bounds = {}
    for c, ps in by_cat.items():
        a = np.array(ps)
        # کف = ۱٪ میانه (فقط قیمت واقعاً غیرممکن)؛ سقف = max × CEIL_MULT (تایپو)
        bounds[c] = (float(np.median(a)) * 0.01, float(a.max()) * CEIL_MULT, len(ps))
    return bounds


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["bundle", "db"], default="bundle")
    args = ap.parse_args()

    listings = load_listings(args.source)
    dec = latest_decisions()
    bounds = category_bounds(listings, dec)

    flags = []
    counts = defaultdict(int)
    for r in listings:
        p = r["price"]
        if p <= 0:
            continue
        d = dec.get(r["id"])
        cat = d.get("category") if d else None
        signal = detail = None
        if is_placeholder(p):
            signal, detail = "PLACEHOLDER", f"ارقام تکراری ({p:,})"
        elif cat and cat in bounds:
            floor, ceil, _ = bounds[cat]
            if p < floor:
                signal, detail = "BELOW_FLOOR", f"{p:,} < کف {cat} ({int(floor):,})"
            elif p > ceil:
                signal, detail = "ABOVE_CEILING", f"{p:,} > سقف {cat} ({int(ceil):,})"
        if signal:
            counts[signal] += 1
            flags.append({"id": r["id"], "title": r["title"], "price": p,
                          "category": cat or "", "signal": signal, "detail": detail})

    REVIEW.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for f in flags:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    print("=" * 60)
    print("🔍 بررسی کیفیت قیمت")
    print("=" * 60)
    print(f"  کل listingها:        {len(listings):>7,}")
    print(f"  پرچم‌خورده:           {len(flags):>7,}  ({len(flags)/len(listings)*100:.1f}٪)")
    for s in ("BELOW_FLOOR", "ABOVE_CEILING", "PLACEHOLDER"):
        print(f"    {s:<14}{counts[s]:>7,}")
    print(f"\n  📄 {OUT}")
    print("  این‌ها برای **بازبینی** است (حذف خودکار نه) — قیمت ارزان می‌تواند تخفیف واقعی باشد.")
    print("\n  نمونه‌ها:")
    for f in sorted(flags, key=lambda x: x["price"])[:5]:
        print(f"    [{f['signal']}] {f['price']:>13,}  {f['category']:<10} {f['title'][:36]}")
    for f in sorted(flags, key=lambda x: -x["price"])[:3]:
        print(f"    [{f['signal']}] {f['price']:>13,}  {f['category']:<10} {f['title'][:36]}")


if __name__ == "__main__":
    main()
