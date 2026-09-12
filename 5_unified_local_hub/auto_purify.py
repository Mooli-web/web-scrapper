#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سرویس پالایش خودکار — سیاست متعادل، همیشه‌روشن.

برای هر آگهیِ بازبینی‌نشده مدل را اجرا می‌کند و سه کار می‌کند:
  ۱) delete_prob ≥ T_DEL (پیش‌فرض ۰.۹۵)  → خودکار حذف (j MODEL_REJECT)
  ۲) category_conf ≥ T_CAT (پیش‌فرض ۰.۹۰) → خودکار دسته‌بندی (s <cat>)
  ۳) بقیه                                  → صف جداگانه‌ی بازبینی دستی

خروجی‌ها:
  - exports/review/decisions_auto.dsl        تصمیم‌های خودکار (در دفترکل می‌نشیند)
  - exports/review/manual_review_queue.jsonl صف دستی (id، عنوان، قیمت، دو حدس برتر)

اجرا:
    python auto_purify.py --once --dry-run     # یک‌بار، فقط گزارش (چیزی نمی‌نویسد)
    python auto_purify.py --once               # یک‌بار، دفترکل را به‌روز می‌کند
    python auto_purify.py --watch 300          # هر ۵ دقیقه، همیشه‌روشن
    python auto_purify.py --once --apply-db    # علاوه بر دفترکل، market.db را هم بنویس
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))

import review_queue as rq
import ml_predict as P
from apply_decisions_to_db import latest_decisions

REVIEW = HUB / "exports" / "review"
AUTO_DSL = REVIEW / "decisions_auto.dsl"
MANUAL_Q = REVIEW / "manual_review_queue.jsonl"


def load_listings(source: str):
    if source == "db":
        from database.db_manager import LocalDatabaseManager
        db = LocalDatabaseManager()
        with db.get_connection() as c:
            return [{"id": r[0], "title": r[1] or "", "price": r[2] or 0}
                    for r in c.execute("SELECT id, title_fa, price_toman FROM store_listings")]
    return [{"id": json.loads(l)["id"], "title": json.loads(l).get("title_fa") or "",
             "price": json.loads(l).get("price_toman") or 0}
            for l in (HUB / "exports/training_bundle/listings.jsonl").read_text(encoding="utf-8").splitlines()]


def run_once(source, t_del, t_cat, dry, apply_db):
    decided = set(latest_decisions().keys())
    todo = [x for x in load_listings(source) if x["id"] not in decided]
    auto, manual = [], []
    for x in todo:
        pr = P.predict(x["title"], x["price"])
        if not pr["wanted"]:
            auto.append(f"{x['id']} j MODEL_REJECT # لوازم جانبی/متفرقه — نامطلوب")
        elif pr["delete_prob"] >= t_del:
            auto.append(f"{x['id']} j MODEL_REJECT # اطمینان حذف {pr['delete_prob']:.2f}")
        elif pr["category_conf"] >= t_cat:
            auto.append(f"{x['id']} s {pr['category']} # اطمینان {pr['category_conf']:.2f}")
        else:
            manual.append({**x, **pr})

    n_unwanted = sum(1 for a in auto if "نامطلوب" in a)
    print(f"📊 بررسی {len(todo):,} آگهی بازبینی‌نشده")
    print(f"   خودکار حذف (نامطلوب/آشغال): {sum(1 for a in auto if ' j ' in a):,} "
          f"(از آن لوازم جانبی/متفرقه: {n_unwanted:,})")
    print(f"   خودکار دسته‌بندی:  {sum(1 for a in auto if ' s ' in a):,}")
    print(f"   صف بازبینی دستی:   {len(manual):,}")

    if dry:
        print("   (dry-run — چیزی نوشته نشد)")
        return

    # تصمیم‌های خودکار → DSL → دفترکل
    AUTO_DSL.write_text("// تصمیم‌های خودکار مدل پالایش\n" + "\n".join(auto) + "\n", encoding="utf-8")
    bad = [a for a in auto if not rq.parse_dsl(a + "\n")]
    if bad:
        print(f"   ⚠️ {len(bad)} سطر نامعتبر رد شد")
    subprocess.run([sys.executable, "review_queue.py", "apply", "--session", "AUTO",
                    "--file", AUTO_DSL.name], cwd=HUB, check=True,
                   stdout=subprocess.DEVNULL)
    print(f"   ✅ {len(auto):,} تصمیم خودکار در دفترکل نشست (نشست AUTO)")

    # صف دستی → فایل جداگانه
    with MANUAL_Q.open("w", encoding="utf-8") as fh:
        for m in manual:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"   📋 صف دستی: {MANUAL_Q}  ({len(manual):,} مورد)")
    print(f"      بازبینی با:  python predict_ui.py   (از کم‌اطمینان‌ترین)")

    if apply_db:
        subprocess.run([sys.executable, "apply_decisions_to_db.py", "--apply"], cwd=HUB, check=True)
        print("   ✅ market.db به‌روز شد")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["bundle", "db"], default="bundle")
    ap.add_argument("--once", action="store_true", help="یک‌بار اجرا کن و بیرون برو")
    ap.add_argument("--watch", type=int, metavar="SEC", help="هر SEC ثانیه تکرار کن (همیشه‌روشن)")
    ap.add_argument("--dry-run", action="store_true", help="فقط گزارش، چیزی ننویس")
    ap.add_argument("--apply-db", action="store_true", help="market.db را هم به‌روز کن")
    ap.add_argument("--t-del", type=float, default=0.95, help="آستانه‌ی اطمینان حذف")
    ap.add_argument("--t-cat", type=float, default=0.90, help="آستانه‌ی اطمینان دسته‌بندی")
    args = ap.parse_args()

    if not (args.once or args.watch):
        ap.error("یا --once یا --watch SEC لازم است")

    if args.once:
        run_once(args.source, args.t_del, args.t_cat, args.dry_run, args.apply_db)
    else:
        print(f"🔄 حالت همیشه‌روشن: هر {args.watch} ثانیه (Ctrl-C برای توقف)")
        while True:
            run_once(args.source, args.t_del, args.t_cat, args.dry_run, args.apply_db)
            time.sleep(args.watch)


if __name__ == "__main__":
    main()
