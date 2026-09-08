# -*- coding: utf-8 -*-
"""راه‌اندازی تست‌های هاب — دیتابیس ایزوله‌ی موقت برای هر تست."""
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HUB))
# نکته: مسیر دیوار «انتها»ی path است تا تداخل نام پکیج server بین دو پروژه پیش نیاید
sys.path.append(str(HUB.parent / "2_divar_cloud"))  # برای تست junk_filter خزنده

import pytest  # noqa: E402


TABLES = [
    "store_listings", "canonical_products", "arbitrage_opportunities",
    "price_history", "sync_logs", "ai_review_cache", "learned_junk_signals",
]


@pytest.fixture()
def clean_db(tmp_path, monkeypatch):
    """دیتابیس موقت تمیز برای هر تست (فایل واقعی لمس نمی‌شود)."""
    from database.db_manager import db
    monkeypatch.setattr(db, "db_path", tmp_path / "test.db")
    db._init_db()
    for t in TABLES:
        try:
            db.execute(f"DELETE FROM {t};")
        except Exception:
            pass
    # مهاجرت‌های runtime روی دیتابیس موقت
    from core.taxonomy import ensure_category_columns
    from core.ai_reviewer import ai_reviewer
    ensure_category_columns()
    ai_reviewer._ensure_cache_table()

    # ریست کش‌های ماژولی
    from core.data_cleaner import load_learned_signals, _LEARNED_SIGNALS
    _LEARNED_SIGNALS.clear()
    load_learned_signals(force=True)
    yield db
    _LEARNED_SIGNALS.clear()


@pytest.fixture()
def fast_ai(monkeypatch):
    """Groq شبیه‌سازی‌شده — بدون شبکه و بدون انتظار."""
    from core import ai_reviewer as ar
    from core.groq_client import groq_client

    def fake_chat(system, user, max_tokens=2000):
        import json
        items = json.loads(user.split("\n\n", 1)[1])
        return {"verdicts": [
            {"i": it["i"], "is_device": "گوشی" in it["title"],
             "category": "mobile", "reason_fa": "تست", "confidence": 0.9}
            for it in items
        ]}

    monkeypatch.setattr(groq_client, "chat_json", fake_chat)
    monkeypatch.setattr(groq_client, "is_configured", lambda: True)
    monkeypatch.setattr(groq_client, "api_keys", ["gsk_test"])
    monkeypatch.setattr(ar.time, "sleep", lambda s: None)
    return groq_client
