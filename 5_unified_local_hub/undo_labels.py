# -*- coding: utf-8 -*-
"""
↩️ برگرداندن اشتباهات لیبل‌زنی — undo_labels.py
===================================================
برای وقتی که اشتباه زدی: چرت/تایید/دسته. سه حالت:

۱) برگرداندن یک آگهی چرت‌شده (🗑 اشتباهی):
     python undo_labels.py listing <آگهی_id>
   → وضعیت PENDING می‌شود (پالایش بعدی دوباره قضاوت می‌کند؛ اگر قانع‌کننده
     نبود صف AI می‌رود) + الگوی exact-titleِ مرتبط غیرفعال می‌شود.

۲) برگرداندن یک تایید انسانی (✅ اشتباهی):
     python undo_labels.py unverify <آگهی_id>
   → فقط قفل ✋ برداشته می‌شود؛ وضعیت VERIFIED می‌ماند (قوانین همان را
     می‌گفتند) — اگر هم چرت کردن می‌خواهی، بعدش listing را بزن.

۳) پاک کردن یک الگوی آموخته‌شده (اگر خود الگو مشکل‌ساز است):
     python undo_labels.py signal <signal_id>
   (فهرست id الگوها: python undo_labels.py signals)

یافتن id آگهی: در داشبورد روی آگهی hover کن یا از خروجی API (فیلد id).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402


def listing(id_):
    row = db.fetchone("SELECT id, title_fa, quality_status, rejection_reason FROM store_listings WHERE id=?;", (id_,))
    if not row:
        print(f"❌ آگهی با id={id_} پیدا نشد.")
        return
    print(f"آگهی: {row['title_fa'][:60]}")
    print(f"وضعیت فعلی: {row['quality_status']} | دلیل: {(row['rejection_reason'] or '')[:60]}")

    # اگر الگوی exact-title مرتبطی هست، غیرفعالش کن
    from core.normalizer import clean_persian_text, extract_primary_product_title
    exact = clean_persian_text(extract_primary_product_title(row["title_fa"] or "")).lower()
    sig = db.fetchone("SELECT id, signal FROM learned_junk_signals WHERE exact_title=?;", (exact,))
    if sig:
        db.execute("DELETE FROM learned_junk_signals WHERE id=?;", (sig["id"],))
        print(f"🗑 الگوی آموخته‌شده‌ی مرتبط حذف شد (id={sig['id']} «{sig['signal']}»)")

    db.execute("""UPDATE store_listings SET quality_status='PENDING', is_verified=0,
                  rejection_reason='برگشت از تصمیم انسانی — در انتظار قضاوت مجدد',
                  confidence_score=0 WHERE id=?;""", (id_,))
    print("↩️ آگهی به صف قضاوت مجدد برگشت — در داشبورد «اجرای مجدد پالایش» را بزن.")


def unverify(id_):
    row = db.fetchone("SELECT id, title_fa, rejection_reason FROM store_listings WHERE id=?;", (id_,))
    if not row:
        print(f"❌ آگهی با id={id_} پیدا نشد.")
        return
    db.execute("""UPDATE store_listings SET rejection_reason='', confidence_score=0
                  WHERE id=?;""", (id_,))
    print(f"↩️ قفل انسانیِ «{row['title_fa'][:50]}» برداشته شد (وضعیت VERIFIED ماند).")


def signals():
    rows = db.fetchall("SELECT id, signal, exact_title, times_hit FROM learned_junk_signals ORDER BY id DESC LIMIT 50;")
    if not rows:
        print("الگویی یاد گرفته نشده.")
        return
    for r in rows:
        print(f"   id={r['id']:3d} | «{r['signal']}» | نمونه: {(r['exact_title'] or '')[:40]} | حذف‌ها: {r['times_hit'] or 0}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "listing" and len(sys.argv) > 2:
        listing(int(sys.argv[2]))
    elif cmd == "unverify" and len(sys.argv) > 2:
        unverify(int(sys.argv[2]))
    elif cmd == "signal" and len(sys.argv) > 2:
        n = db.execute("DELETE FROM learned_junk_signals WHERE id=?;", (int(sys.argv[2]),))
        print("✅ الگو حذف شد." if n else "❌ پیدا نشد.")
    elif cmd == "signals":
        signals()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
