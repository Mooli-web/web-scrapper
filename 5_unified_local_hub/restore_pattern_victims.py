# -*- coding: utf-8 -*-
"""
🔁 بازگردانی قربانیان الگوهای قدیمی — restore_pattern_victims.py
===================================================================
مشکل رفع‌شده: الگوهای آموخته‌شده‌ی قدیمی، هر عنوانی را که با کلمه‌ی آغازینِ
آگهیِ تأییدشده شروع می‌شد حذف می‌کردند (نمونه: تیک روی «مادربرد سوخته» ←
همه‌ی مادربردها حذف!). الان الگو فقط عنوانِ دقیقاً یکسان را می‌گیرد.

این اسکریپت آگهی‌هایی را که قربانی همان الگوهای قدیمی شده‌اند بازمی‌گرداند:
وضعیتشان PENDING می‌شود تا پالایش بعدی با قوانین جدید (و در صورت نیاز AI)
دوباره درباره‌شان قضاوت کند.

اجرا (پوشه 5_unified_local_hub):
    python restore_pattern_victims.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db_manager import db  # noqa: E402


def main():
    print("=" * 62)
    print("🔁 بازگردانی قربانیان الگوهای آموخته‌شده‌ی قدیمی")
    print("=" * 62)

    signals = db.fetchall("SELECT signal, example_title, exact_title FROM learned_junk_signals;") or []
    if not signals:
        print("الگویی یاد گرفته نشده — کاری نیست.")
        return
    print(f"الگوهای موجود: {len(signals)}")
    for s in signals:
        print(f"  • «{s['signal']}» — مثال: {(s['example_title'] or '')[:50]}")

    # ردیابی الگوهای قدیمی که exact_title خالی دارند → با مثال پر می‌کنیم
    from core.normalizer import clean_persian_text, extract_primary_product_title
    for s in signals:
        if not (s["exact_title"] or "").strip() and (s["example_title"] or "").strip():
            exact = clean_persian_text(extract_primary_product_title(s["example_title"])).lower()
            db.execute("UPDATE learned_junk_signals SET exact_title = ? WHERE signal = ?;",
                       (exact, s["signal"]))
    print("\n✅ الگوهای قدیمی به حالت «فقط عنوانِ دقیق» محدود شدند.")

    # بازگردانی: آگهی‌هایی که با دلیل «الگوی آموخته‌شده» رد شده‌اند اما عنوانشان
    # با مثالِ دقیق یکی نیست (قربانیان واقعی)
    rows = db.fetchall("""
        SELECT id, title_fa FROM store_listings
        WHERE quality_status = 'ACCESSORY_OR_JUNK'
          AND rejection_reason LIKE 'الگوی آموخته%';
    """) or []
    victims = []
    sig_map = {s["signal"]: (s["exact_title"] or "") for s in signals}
    from core.data_cleaner import StandardDataPurifier
    from core.normalizer import clean_persian_text, extract_primary_product_title

    def norm(t):
        return clean_persian_text(extract_primary_product_title(t or "")).lower()

    for r in rows:
        first = norm(r["title_fa"]).split(" ", 1)[0]
        exact = sig_map.get(first, "")
        if exact and norm(r["title_fa"]) != exact:
            victims.append((r["id"], (r["title_fa"] or "")[:50]))

    print(f"\nقربانیان یافت‌شده: {len(victims)}")
    for vid, title in victims[:10]:
        print(f"  ↩️  {title}")

    if victims:
        db.executemany("""
            UPDATE store_listings SET quality_status='PENDING', is_verified=0,
                   rejection_reason='بازگردانی: قربانی الگوی قدیمی — در انتظار قضاوت مجدد',
                   confidence_score=0
            WHERE id = ?;
        """, [(v[0],) for v in victims])
        print(f"\n✅ {len(victims)} آگهی به صف قضاوت مجدد بازگشتند.")
    else:
        print("قربانی‌ای با این روش یافت نشد (خبر خوب!)")

    print("\n👉 حالا در داشبورد «اجرای مجدد پالایش» را بزن (و در صورت صف AI، دکمه بنفش).")


if __name__ == "__main__":
    main()
