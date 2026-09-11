#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""آمار و خروجی آماده‌ی آموزش ML برای «حذف» و «دسته‌بندی» آگهی‌ها.

دو مدل هدف:
  A) حذف/نگه‌داشتن (دودویی):  keep=1 / delete=0
  B) دسته‌بندی (چندرده‌ای):    یکی از ۱۶ دسته‌ی استاندارد، فقط روی ردیف‌های keep

منابع برچسب (به ترتیب اولویت، آخری برنده):
  ۱) دفترکل ایجنت  exports/review/decisions.jsonl
  ۲) برچسب دستی    exports/review/decisions_ui_*.dsl   (روی سیستم تو)

این فایل فقط می‌خواند؛ با --export دو فایل آموزشی می‌نویسد:
  exports/ml/quality_train.jsonl   {id,title,price,label}
  exports/ml/category_train.jsonl  {id,title,price,label}

اجرا (همین‌جا یا روی سیستم تو — برچسب‌های دستی‌ات خودکار شمرده می‌شوند):
    python3 ml_stats.py
    python3 ml_stats.py --export
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))

BUNDLE = HUB / "exports" / "training_bundle"
REVIEW = HUB / "exports" / "review"
ML = HUB / "exports" / "ml"

from apply_decisions_to_db import latest_decisions  # noqa: E402
import review_queue as rq  # noqa: E402


def _load_jsonl(p: Path):
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", action="store_true", help="فایل آموزشی بنویس")
    args = ap.parse_args()

    # ---- بارگذاری داده خام ----
    title, price, canon = {}, {}, {}
    for r in _load_jsonl(BUNDLE / "listings.jsonl"):
        title[r["id"]] = r.get("title_fa") or ""
        price[r["id"]] = r.get("price_toman") or 0
        canon[r["id"]] = r.get("canonical_key") or ""
    cat_std = {}
    for c in _load_jsonl(BUNDLE / "canonical_products.jsonl"):
        cat_std[c["canonical_key"]] = c.get("category_std") or ""

    # ---- برچسب ایجنت ----
    lab: dict[int, dict] = {}
    for lid, d in latest_decisions().items():
        lab[lid] = {"decision": d["decision"],
                    "category": d.get("category") or "",
                    "reason": d.get("reason_code") or "",
                    "source": "agent"}

    # ---- برچسب دستی (روی سیستم تو) ----
    manual_files = sorted(REVIEW.glob("decisions_ui_*.dsl"))
    for p in manual_files:
        for row in rq.parse_dsl(p.read_text(encoding="utf-8")):
            if "id" not in row:
                continue
            lab[row["id"]] = {"decision": row["decision"],
                              "category": row.get("category") or "",
                              "reason": row.get("reason_code") or "",
                              "source": "manual"}

    # ---- ترکیب برچسب نهایی برای دو تسک ----
    keep, delete, uncertain = [], [], 0
    cat_count = Counter()
    reason_count = Counter()
    quality_rows, category_rows = [], []
    for lid, L in lab.items():
        if lid not in title:
            continue
        d = L["decision"]
        if d == "junk":
            delete.append(lid)
            reason_count[L["reason"] or "OTHER"] += 1
            quality_rows.append((lid, 0))
        elif d == "uncertain":
            uncertain += 1
            continue                       # برای آموزش دودویی کنار می‌ماند
        elif d in ("verify", "set-category"):
            keep.append(lid)
            quality_rows.append((lid, 1))
            cat = L["category"] or cat_std.get(canon.get(lid, ""), "")
            if cat in rq.CATEGORIES:
                cat_count[cat] += 1
                if d == "verify" or L["category"]:
                    category_rows.append((lid, cat))
        else:
            continue

    labeled = len(lab)
    total = len(title)

    print("=" * 64)
    print("📊 آمار داده برای آموزش ML")
    print("=" * 64)
    print(f"\n  کل آگهی‌ها:            {total:>7,}")
    print(f"  برچسب‌خورده:           {labeled:>7,}  ({labeled/total*100:.1f}٪)")
    print(f"    ایجنت:               {sum(1 for L in lab.values() if L['source']=='agent'):>7,}")
    print(f"    دستی (تو):           {sum(1 for L in lab.values() if L['source']=='manual'):>7,}")
    print(f"  نگه‌داشتنی (keep):     {len(keep):>7,}")
    print(f"  حذف (delete):          {len(delete):>7,}")
    print(f"  نامطمئن (کنار):        {uncertain:>7,}")
    print(f"  بدون برچسب (باقی):     {total-labeled:>7,}")

    print(f"\n  ── تسک A: حذف/نگه‌داشتن ──")
    n_pos, n_neg = len(keep), len(delete)
    print(f"    keep  = {n_pos:,}   delete = {n_neg:,}")
    if n_neg:
        print(f"    نسبت عدم‌تعادل keep:delete = {n_pos/n_neg:.2f} : 1")
    print(f"    نمونه‌ی قابل‌آموزش A = {n_pos+n_neg:,}  "
          f"(train {int((n_pos+n_neg)*0.8):,} / val {int((n_pos+n_neg)*0.1):,} / test {int((n_pos+n_neg)*0.1):,})")

    print(f"\n  ── تسک B: دسته‌بندی (فقط keep با دسته) ──")
    n_cat = sum(cat_count.values())
    print(f"    نمونه‌ی قابل‌آموزش B = {n_cat:,}")
    print(f"    دسته‌های پرشده: {len([c for c in cat_count if cat_count[c]>0])} از {len(rq.CATEGORIES)}")
    for c in sorted(rq.CATEGORIES, key=lambda k: -cat_count[k]):
        n = cat_count[c]
        bar = "█" * min(40, n // max(1, max(cat_count.values()) // 40))
        flag = "  ⚠️ کم" if 0 < n < 50 else ""
        print(f"      {c:<12} {n:>6,}  {bar}{flag}")
    if cat_count:
        mx, mn = max(cat_count.values()), min(v for v in cat_count.values() if v)
        print(f"    عدم‌تعادل کلاس: بزرگ‌ترین/کوچک‌ترین = {mx/mn:.0f}x")

    print(f"\n  ── دلیل‌های حذف (برای مدل A) ──")
    for r, n in reason_count.most_common():
        print(f"      {r:<20} {n:>6,}")

    # ---- قضاوت امکان‌پذیری ----
    print("\n" + "=" * 64)
    print("🧭 قضاوت")
    ok = True
    if n_cat < 1000:
        ok = False
        print(f"  ❌ تسک B فقط {n_cat:,} نمونه دارد — برای ۱۶ کلاس کم است؛ برگرد به برچسب‌زنی.")
    else:
        small = [c for c in rq.CATEGORIES if 0 < cat_count[c] < 30]
        if small:
            print(f"  ⚠️  تسک B: کلاس‌های کم‌نمونه (<30): {', '.join(small)} — یا برچسب بیشتر، یا ادغام.")
        print(f"  ✅ تسک B با {n_cat:,} نمونه برای یک مدل متن‌پایه (TF-IDF/char-ngram + LR یا MLP) کافی است.")
    if n_pos + n_neg < 2000:
        ok = False
        print(f"  ❌ تسک A فقط {n_pos+n_neg:,} نمونه دارد — کم است.")
    else:
        print(f"  ✅ تسک A با {n_pos+n_neg:,} نمونه کافی است؛ عدم‌تعادل با وزن‌دهی/stratify حل می‌شود.")

    if args.export:
        ML.mkdir(parents=True, exist_ok=True)
        with (ML / "quality_train.jsonl").open("w", encoding="utf-8") as fh:
            for lid, y in quality_rows:
                fh.write(json.dumps({"id": lid, "title": title[lid],
                                     "price": price[lid], "label": y}, ensure_ascii=False) + "\n")
        with (ML / "category_train.jsonl").open("w", encoding="utf-8") as fh:
            for lid, c in category_rows:
                fh.write(json.dumps({"id": lid, "title": title[lid],
                                     "price": price[lid], "label": c}, ensure_ascii=False) + "\n")
        print(f"\n  📄 نوشته شد: {ML/'quality_train.jsonl'} و {ML/'category_train.jsonl'}")

    print(f"\n  نتیجه‌ی کلی: {'✅ آماده‌ی آموزش' if ok else '⛔ هنوز به برچسب دستی نیاز است'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
