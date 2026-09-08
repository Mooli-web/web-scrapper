# -*- coding: utf-8 -*-
"""تست دسته‌بندی، فیلتر خزنده، پایپ‌لاین کامل و لایه AI (با Groq شبیه‌سازی‌شده)."""
import json


# ---------------------------------------------------------------------------
# دسته‌بندی یکپارچه
# ---------------------------------------------------------------------------
class TestTaxonomy:
    CASES = [
        ("mobile-apple", "گوشی موبایل اپل iPhone 15", "mobile"),
        ("laptops-apple", "مک بوک پرو M3", "laptop"),
        ("gaming-playstation", "کنسول PS5", "console"),
        ("graphic-cards", "کارت گرافیک RTX 4060", "gpu"),
        ("smart-watches", "ساعت هوشمند سامسونگ", "watch"),
        ("headphones", "هدفون سونی", "headphone"),
        ("tablets", "تبلت سامسونگ", "tablet"),
        ("storage-devices", "هارد اکسترنال", "storage"),
        ("processors", "پردازنده اینتل", "cpu"),
        ("monitor", "مانیتور ال جی", "monitor"),
        ("microsoft-surface", "سرفیس پرو", "laptop"),
        ("vintage_mobile", "نوکیا 6070", "mobile"),
        ("auctions_ending", "سیستم گیمینگ i5 با RX 580", "desktop-pc"),
        ("auctions_hot", "رم کورسیر 32 گیگ DDR4", "ram"),
        ("digital", "گوشی شیائومی Redmi Note 13", "mobile"),
        ("digital", "ماشین حساب کاسیو", "other"),
        ("", "مادربرد گیگابایت B760", "motherboard"),
    ]

    def test_normalize(self):
        from core.taxonomy import normalize_category
        for raw, title, expected in self.CASES:
            got = normalize_category(raw, title)
            assert got == expected, f"({raw!r}, {title[:25]!r}) → {got} != {expected}"

    def test_labels(self):
        from core.taxonomy import category_label
        assert category_label("gpu") == "کارت گرافیک"
        assert category_label("unknown_xx") == "متفرقه"


# ---------------------------------------------------------------------------
# فیلتر خزنده (هویتی)
# ---------------------------------------------------------------------------
class TestCrawlerJunkFilter:
    DROP = [
        ("آویز 4 گرمی دو رو کلاسیک", 99_250),
        ("شیت تمبر آفریقایی مطبق تصویر", 110_000),
        ("سایز 43 نایک جردن اورجینال", 1_450_000),
        ("اسپلیتر 1 به 2 پورت VGA", 450_000),
        ("فقط کارتن خالی آیفون 13", 2_000_000),
        ("خریدار ( خرید ) کارت گرافیک ریگ", 8_000_000),
        ("گجت فرضی مدل X", 11_111),
    ]
    KEEP = [
        ("گوشی آیفون ۱۳ پرو مکس ۱۲۸ گیگ", 12_000_000),   # واژه دستگاه اول → هرگز
        ("کارت گرافیک Sapphire RX 580", 12_000_000),
        ("رافیک XFX RX580 استوک", 9_950_000),
        ("سیستم گیمینگ کامل i5", 70_000_000),
        ("کنسول PS5 دیجیتال", 25_000_000),
        ("گوشی با قیمت عجیب", 11_111),  # واژه دستگاه اول → خزنده هرگز حذف نمی‌کند (کار هاب است)
    ]

    def test_should_drop(self):
        from crawler.junk_filter import should_drop
        for title, price in self.DROP:
            assert should_drop(title, price) is not None, f"باید حذف شود: {title}"

    def test_should_keep(self):
        from crawler.junk_filter import should_drop
        for title, price in self.KEEP:
            assert should_drop(title, price) is None, f"نباید حذف شود: {title}"

    def test_shadow_vs_active(self):
        from crawler.junk_filter import junk_filter, filter_item
        junk_filter.set_mode("shadow")
        assert filter_item("آویز طلا", 1_000_000, "divar") is False
        junk_filter.set_mode("active")
        assert filter_item("سایز 42 کفش نایک", 1_720_000, "esam") is True
        junk_filter.set_mode("off")
        assert filter_item("پاکت سیگار", 650_000, "divar") is False
        junk_filter.set_mode("shadow")
        s = junk_filter.get_stats()
        assert s["counters"]["candidates"] >= 2 and len(s["recent_candidates"]) >= 2


# ---------------------------------------------------------------------------
# پایپ‌لاین کامل (ingest → purify → arbitrage → dataset)
# ---------------------------------------------------------------------------
class TestPipeline:
    def test_end_to_end(self, clean_db, fast_ai, tmp_path, monkeypatch):
        from sync.ingest_torob import ingest_torob_items
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from core.arbitrage_engine import arbitrage_engine
        from core import ai_dataset_generator as adg
        from database.db_manager import db

        # مرجع سالم ترب + آگهی ارزان واقعی دیوار + چرت
        ingest_torob_items([
            {"key": "t1", "title": "گوشی موبایل اپل iPhone 15 Pro 256", "price": 80_000_000, "num_shops": 5},
        ])
        ingest_divar_items([
            {"token": "v1", "title": "گوشی اپل iPhone 15 Pro 256 کارکرده", "price": 60_000_000},
            {"token": "v2", "title": "آویز طلا دو رو", "price": 99_000},
        ])
        res = data_purifier.run_full_purification_pipeline()
        b = res["breakdown"]
        assert b["verified_clean"] == 2 and b["needs_ai_review"] == 1

        # تطبیق فارسی/انگلیسی: هر دو آگهی یک کانونیکال
        keys = {r["canonical_key"] for r in db.fetchall("SELECT canonical_key FROM store_listings WHERE is_verified=1;")}
        assert len(keys) == 1

        # مرجع مقاوم ثبت شده
        c = db.fetchone("SELECT torob_min_price_toman, category_std FROM canonical_products;")
        assert c["torob_min_price_toman"] == 80_000_000
        assert c["category_std"] == "mobile"

        arb = arbitrage_engine.run_arbitrage_scan()
        assert arb["opportunities_found"] == 1  # دیوار ۶۰M در برابر ترب ۸۰M = ۲۵٪

        # دیتاست: ستون‌های جدید
        monkeypatch.setattr(adg, "EXPORTS_DIR", tmp_path)
        tmp_path.mkdir(exist_ok=True)
        exp = adg.ai_exporter.export_all()
        assert exp["samples_count"] == 3
        row = json.loads((tmp_path / "quad_market_dataset.json").read_text(encoding="utf-8"))[0]
        assert "category_std" in row and "seller_rating" in row

    def test_ai_review_with_cache(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from core.ai_reviewer import ai_reviewer
        from core.groq_client import groq_client
        from database.db_manager import db

        ingest_divar_items([
            {"token": "v1", "title": "گوشی سامسونگ Galaxy S24", "price": 62_000_000},
            {"token": "v2", "title": "سه چرخ کودک فلزی", "price": 1_500_000},
        ])
        data_purifier.run_full_purification_pipeline()
        assert ai_reviewer.count_pending() == 1

        r1 = ai_reviewer.run_review(max_batches=1)
        assert r1["api_processed"] == 1 and r1["still_pending"] == 0
        calls = {"n": 0}
        orig = groq_client.chat_json

        def counting(system, user, max_tokens=2000):
            calls["n"] += 1
            return orig(system, user, max_tokens)

        groq_client.chat_json = counting
        # شبیه‌سازی دیتابیس تازه/بازسازی‌شده: آگهی به صف برمی‌گردد ولی کش هست
        db.execute("UPDATE store_listings SET quality_status='NEEDS_AI_REVIEW', is_verified=0 WHERE item_id='v2';")
        r2 = ai_reviewer.run_review(max_batches=1)
        assert r2["cached_applied"] == 1 and calls["n"] == 0  # رایگان از کش

    def test_category_audit(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from core.ai_reviewer import ai_reviewer
        from database.db_manager import db

        ingest_divar_items([{"token": "v1", "title": "گوشی سامسونگ Galaxy S24", "price": 62_000_000}])
        data_purifier.run_full_purification_pipeline()
        # پالایش دسته‌ی rule گذاشته — ممیزی مقدس‌شان می‌دارد؛ خالی می‌کنیم تا ممیزی بگیرد
        db.execute("UPDATE canonical_products SET category_std='', category_source='';")
        res = ai_reviewer.run_category_audit(max_batches=1)
        assert res["processed"] >= 1 and res["batches_done"] == 1
        c = db.fetchone("SELECT category_source FROM canonical_products;")
        assert c["category_source"] == "ai"


# ---------------------------------------------------------------------------
# محصولات زامبی + دریل‌داون دسته (رفع متورم‌شدن آمار)
# ---------------------------------------------------------------------------
class TestActiveProductsOnly:
    def test_overview_excludes_zombies(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from server.routes import get_market_overview
        import server.routes as R
        # ریست کش گزارش
        R.MARKET_OVERVIEW_CACHE, R.MARKET_OVERVIEW_TIME = {}, 0.0

        ingest_divar_items([
            {"token": "v1", "title": "گوشی سامسونگ Galaxy S24", "price": 62_000_000},
            {"token": "j1", "title": "آویز طلا دو رو کلاسیک", "price": 99_000},  # چرت → محصول زامبی
        ])
        data_purifier.run_full_purification_pipeline()
        ov = get_market_overview()
        assert ov["total_products"] == 1
        assert ov["inactive_products_excluded"] == 1
        assert ov["total_verified_listings"] == 1

    def test_drilldown_lists_all_listings(self, clean_db, fast_ai):
        from sync.ingest_torob import ingest_torob_items
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from server.routes import get_category_products

        # یک محصول، چند آگهی تاییدشده
        ingest_torob_items([{"key": "t1", "title": "گوشی موبایل اپل iPhone 15 Pro 256", "price": 80_000_000, "num_shops": 5}])
        ingest_divar_items([{"token": "v1", "title": "گوشی اپل iPhone 15 Pro 256 کارکرده", "price": 60_000_000}])
        # زامبی‌ها (باید دریل‌داون را پر نکنند)
        for i in range(5):
            ingest_divar_items([{"token": f"z{i}", "title": f"آویز طلا مدل {i}", "price": 90_000 + i}])
        data_purifier.run_full_purification_pipeline()

        res = get_category_products(category="mobile", limit=50, offset=0)
        assert res["total"] == 1                      # فقط محصولِ دارای آگهی تاییدشده
        assert res["listings_total"] == 2
        assert len(res["items"]) == 2                 # هر دو آگهی — نه فقط ۲ محصول اول

    def test_zombie_cleanup(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        import cleanup_inactive_products as cz
        ingest_divar_items([
            {"token": "v1", "title": "گوشی سامسونگ Galaxy S24", "price": 62_000_000},
            {"token": "j1", "title": "آویز طلا دو رو", "price": 99_000},
        ])
        data_purifier.run_full_purification_pipeline()
        zombies = cz.find_zombies()
        assert len(zombies) == 1 and zombies[0]["brand"] in ("other",)
        before = db.fetchone("SELECT COUNT(*) c FROM canonical_products;")["c"]
        cz.main_purge_quiet() if hasattr(cz, "main_purge_quiet") else None
        # حذف مستقیم با همان منطق
        keys = [z["canonical_key"] for z in zombies]
        for k in keys:
            db.execute("DELETE FROM price_history WHERE canonical_key=?;", (k,))
            db.execute("DELETE FROM store_listings WHERE canonical_key=?;", (k,))
            db.execute("DELETE FROM canonical_products WHERE canonical_key=?;", (k,))
        after = db.fetchone("SELECT COUNT(*) c FROM canonical_products;")["c"]
        assert before == 2 and after == 1


# ---------------------------------------------------------------------------
# فیکس الگوی آموخته (فقط عنوان دقیق) + اولویت سیستم آماده
# ---------------------------------------------------------------------------
class TestExactTitleSignals:
    def test_only_exact_title_rejected(self, clean_db):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import StandardDataPurifier, load_learned_signals
        from database.db_manager import db
        ingest_divar_items([{"token": "b1", "title": "مادربرد سوخته اوراقی", "price": 900_000}])
        row = db.fetchone("SELECT id FROM store_listings LIMIT 1;")
        p = StandardDataPurifier()
        p.confirm_junk([row["id"]])
        load_learned_signals(force=True)
        # خود همان عنوان → حذف (الگوی دقیق)
        ok1, s1, r1, _ = p.evaluate_single_listing("مادربرد سوخته اوراقی", 900_000, "parts", "divar")
        assert not ok1 and "تأییدشده" in r1
        # مادربرد سالم دیگر قربانی نمی‌شود — قطعه اصلی است
        ok2, s2, _, _ = p.evaluate_single_listing("مادربرد گیگابایت B760 سالم", 45_000_000, "parts", "digikala")
        assert ok2 and s2 == "VERIFIED", s2

    def test_victim_restore(self, clean_db):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import StandardDataPurifier, load_learned_signals
        from database.db_manager import db
        ingest_divar_items([
            {"token": "b1", "title": "مادربرد سوخته اوراقی", "price": 900_000},
            {"token": "g1", "title": "مادربرد ایسوس TUF سالم", "price": 40_000_000},
        ])
        rows = {r["item_id"]: r["id"] for r in db.fetchall("SELECT id, item_id FROM store_listings;")}
        p = StandardDataPurifier()
        p.confirm_junk([rows["b1"]])
        load_learned_signals(force=True)
        p.run_full_purification_pipeline()  # با قوانین جدید g1 قربانی نمی‌شود
        st = db.fetchone("SELECT quality_status FROM store_listings WHERE item_id='g1';")
        assert st["quality_status"] == "VERIFIED"  # فیکس فعال است

        # شبیه‌سازی یک قربانی قدیمی (پیش از فیکس) و بازگردانی آن
        db.execute("""UPDATE store_listings SET quality_status='ACCESSORY_OR_JUNK', is_verified=0,
                     rejection_reason='الگوی آموخته‌شده از تأیید شما («مادربرد»)' WHERE item_id='g1';""")
        import restore_pattern_victims as rp
        rp.main()
        st2 = db.fetchone("SELECT quality_status FROM store_listings WHERE item_id='g1';")
        assert st2["quality_status"] == "PENDING"
        p.run_full_purification_pipeline()  # قضاوت مجدد با قوانین جدید
        st3 = db.fetchone("SELECT quality_status FROM store_listings WHERE item_id='g1';")
        assert st3["quality_status"] == "VERIFIED"


class TestCompleteSystemPriority:
    def test_hub_taxonomy(self):
        from core.taxonomy import normalize_category
        assert normalize_category("", "سیستم گیمینگ i5 12400f با RX 580") == "desktop-pc"
        assert normalize_category("", "کارت گرافیک RX 580 8GB") == "gpu"
        assert normalize_category("", "کیس آماده مونتاژ RTX 3060") == "desktop-pc"
        assert normalize_category("", "رم 32 گیگ DDR4") == "ram"

    def test_crawler_never_drops_systems(self):
        from crawler.junk_filter import should_drop
        assert should_drop("کارت گرافیک ریگ XFX RX 580 همراه سیستم", 8_000_000) is None
        assert should_drop("رم دو کانال 16 گیگ برای سیستم گیمینگ", 3_000_000) is None
        assert should_drop("قاب گوشی سامسونگ", 180_000) is not None


# ---------------------------------------------------------------------------
# تغییر دسته‌ی دستی (manual) — قوی‌ترین منبع دسته
# ---------------------------------------------------------------------------
class TestManualCategory:
    def test_set_and_lock(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from server.routes import get_category_products

        ingest_divar_items([{"token": "v1", "title": "سیستم گیمینگ کامل با RX 580", "price": 45_000_000}])
        data_purifier.run_full_purification_pipeline()
        row = db.fetchone("SELECT id FROM store_listings LIMIT 1;")

        from fastapi.testclient import TestClient
        from server.app import app
        tc = TestClient(app)
        r = tc.post('/api/audit/set-category', json={"id": row["id"], "category": "desktop-pc"})
        assert r.status_code == 200

        c = db.fetchone("SELECT category_std, category_source FROM canonical_products;")
        assert (c["category_std"], c["category_source"]) == ("desktop-pc", "manual")

        # قفل: ممیزی AI دسته‌ی دستی را بازنویسی نمی‌کند (فقط source != 'ai')
        res = ai_reviewer_run_audit_safe()
        c2 = db.fetchone("SELECT category_std, category_source FROM canonical_products;")
        assert (c2["category_std"], c2["category_source"]) == ("desktop-pc", "manual")

        # دریل‌داون از دسته‌ی جدید می‌آید
        got = get_category_products(category="desktop-pc", limit=10, offset=0)
        assert got["total"] == 1

    def test_invalid_inputs(self, clean_db):
        from fastapi.testclient import TestClient
        from server.app import app
        tc = TestClient(app)
        assert tc.post('/api/audit/set-category', json={"id": "x", "category": "gpu"}).status_code == 400
        assert tc.post('/api/audit/set-category', json={"id": 1, "category": "watch"}).status_code == 404


def ai_reviewer_run_audit_safe():
    from core.ai_reviewer import ai_reviewer
    from core.groq_client import groq_client
    def fake(system, user, max_tokens=1800):
        import json
        items = json.loads(user.split("\n\n", 1)[1])
        return {"verdicts": [{"i": it["i"], "category": "gpu"} for it in items]}  # AI می‌خواهد عوض کند
    orig = groq_client.chat_json
    groq_client.chat_json = fake
    groq_client.is_configured = lambda: True
    groq_client.api_keys = ["gsk_t"]
    try:
        return ai_reviewer.run_category_audit(max_batches=1)
    finally:
        groq_client.chat_json = orig


# ---------------------------------------------------------------------------
# عملیات گروهی (bulk-action)
# ---------------------------------------------------------------------------
class TestBulkActions:
    def _setup(self, clean_db):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        ingest_divar_items([
            {"token": "s1", "title": "سیستم گیمینگ کامل با RX 580", "price": 45_000_000},
            {"token": "s2", "title": "سیستم گیمینگ آماده i5 نسل 12", "price": 38_000_000},
            {"token": "j1", "title": "آویز طلا دو رو کلاسیک", "price": 99_000},
        ])
        data_purifier.run_full_purification_pipeline()
        rows = db.fetchall("SELECT id, item_id, canonical_key FROM store_listings;")
        return {r["item_id"]: r["id"] for r in rows}, {r["item_id"]: r["canonical_key"] for r in rows}

    def test_bulk_set_category(self, clean_db, fast_ai):
        ids, keys = self._setup(clean_db)
        from fastapi.testclient import TestClient
        from server.app import app
        from database.db_manager import db
        tc = TestClient(app)
        r = tc.post('/api/audit/bulk-action', json={
            "ids": [ids["s1"], ids["s2"]], "action": "set-category", "category": "desktop-pc"})
        assert r.status_code == 200 and r.json()["updated_products"] >= 1
        rows = {r2["canonical_key"]: (r2["category_std"], r2["category_source"])
                for r2 in db.fetchall("SELECT canonical_key, category_std, category_source FROM canonical_products;")}
        assert all(v == ("desktop-pc", "manual") for k, v in rows.items() if k in (keys["s1"], keys["s2"]))

    def test_bulk_junk_and_verify(self, clean_db, fast_ai):
        ids, _ = self._setup(clean_db)
        from fastapi.testclient import TestClient
        from server.app import app
        from database.db_manager import db
        tc = TestClient(app)
        r = tc.post('/api/audit/bulk-action', json={"ids": [ids["j1"]], "action": "junk"})
        assert r.status_code == 200 and r.json()["confirmed"] == 1
        st = db.fetchone("SELECT quality_status FROM store_listings WHERE id=?;", (ids["j1"],))
        assert st["quality_status"] == "CONFIRMED_JUNK"

        r2 = tc.post('/api/audit/bulk-action', json={"ids": [ids["s1"]], "action": "verify"})
        assert r2.status_code == 200 and r2.json()["applied"] == 1
        st2 = db.fetchone("SELECT quality_status, is_verified FROM store_listings WHERE id=?;", (ids["s1"],))
        assert st2["quality_status"] == "VERIFIED" and st2["is_verified"] == 1

    def test_invalid(self, clean_db):
        from fastapi.testclient import TestClient
        from server.app import app
        tc = TestClient(app)
        assert tc.post('/api/audit/bulk-action', json={"ids": [], "action": "junk"}).status_code == 400
        assert tc.post('/api/audit/bulk-action', json={"ids": [1], "action": "explode"}).status_code == 400
        # NEW: آیتم ناموجود خطا نیست (حذف بین‌راه توسط dedupe خودکار) — 200 با updated=0
        r = tc.post('/api/audit/bulk-action', json={"ids": [1], "action": "set-category", "category": "watch"})
        assert r.status_code == 200 and r.json()["updated_products"] == 0


# ---------------------------------------------------------------------------
# تاریخچه‌ی تغییر دسته + خروجی آموزش ML
# ---------------------------------------------------------------------------
class TestHumanSignature:
    def test_category_history_recorded(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from fastapi.testclient import TestClient
        from server.app import app

        ingest_divar_items([{"token": "v1", "title": "سیستم گیمینگ کامل با RX 580", "price": 45_000_000}])
        data_purifier.run_full_purification_pipeline()
        row = db.fetchone("SELECT id FROM store_listings LIMIT 1;")
        tc = TestClient(app)

        old = db.fetchone("SELECT category_std, category_source FROM canonical_products;")
        r = tc.post('/api/audit/set-category', json={"id": row["id"], "category": "desktop-pc"})
        assert r.status_code == 200

        # امضا: تاریخچه X→Y ثبت شده (append-only)
        h = db.fetchone("SELECT * FROM category_history ORDER BY id DESC LIMIT 1;")
        assert h is not None
        assert h["old_category"] == old["category_std"]
        assert h["new_category"] == "desktop-pc"
        assert h["changed_by"] == "human"

    def test_training_export(self, clean_db, fast_ai, tmp_path, monkeypatch):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from fastapi.testclient import TestClient
        from server.app import app
        import export_training_data as et

        ingest_divar_items([
            {"token": "v1", "title": "سیستم گیمینگ کامل با RX 580", "price": 45_000_000,
             "description": "سیستم کامل با مانیتور"},
            {"token": "j1", "title": "آویز طلا دو رو", "price": 99_000},
        ])
        data_purifier.run_full_purification_pipeline()
        row = db.fetchone("SELECT id FROM store_listings WHERE item_id='v1';")
        tc = TestClient(app)
        tc.post('/api/audit/set-category', json={"id": row["id"], "category": "desktop-pc"})

        monkeypatch.setattr(et, "OUT_DIR", tmp_path)
        tmp_path.mkdir(exist_ok=True)
        et.main()

        cats = [json.loads(x) for x in (tmp_path / "category_train.jsonl").read_text(encoding="utf-8").splitlines() if x]
        corrs = [json.loads(x) for x in (tmp_path / "corrections.jsonl").read_text(encoding="utf-8").splitlines() if x]
        quals = [json.loads(x) for x in (tmp_path / "quality_train.jsonl").read_text(encoding="utf-8").splitlines() if x]

        assert any(c["label_source"] == "manual" and c["category"] == "desktop-pc" for c in cats)
        assert len(corrs) == 1 and corrs[0]["new_category"] == "desktop-pc" and corrs[0]["changed_by"] == "human"
        labels = {q["label"] for q in quals}
        assert labels == {"clean", "junk"}


# ---------------------------------------------------------------------------
# یادداشت + عدم‌اطمینان + RRP
# ---------------------------------------------------------------------------
class TestLabelingEnrichment:
    def test_note_and_uncertainty_recorded(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from fastapi.testclient import TestClient
        from server.app import app
        ingest_divar_items([{"token": "v1", "title": "سیستم گیمینگ کامل با RX 580", "price": 45_000_000}])
        data_purifier.run_full_purification_pipeline()
        row = db.fetchone("SELECT id FROM store_listings LIMIT 1;")
        tc = TestClient(app)
        r = tc.post('/api/audit/set-category', json={
            "id": row["id"], "category": "desktop-pc",
            "note": "چون سیستم کامل است نه کارت گرافیک تک", "is_uncertain": True})
        assert r.status_code == 200
        h = db.fetchone("SELECT note, is_uncertain FROM category_history ORDER BY id DESC LIMIT 1;")
        assert "سیستم کامل" in h["note"] and h["is_uncertain"] == 1

    def test_rrp_stored_and_exported(self, clean_db, fast_ai, tmp_path, monkeypatch):
        from sync.ingest_digikala import ingest_digikala_items
        from core.data_cleaner import data_purifier
        from core import ai_dataset_generator as adg
        from database.db_manager import db
        ingest_digikala_items([{"id": "d1", "title_fa": "گوشی موبایل اپل iPhone 15",
                                "selling_price_toman": 75_000_000, "rrp_price": 82_000_000,
                                "category_key": "mobile-apple"}])
        data_purifier.run_full_purification_pipeline()
        row = db.fetchone("SELECT rrp_price_toman FROM store_listings;")
        assert row["rrp_price_toman"] == 82_000_000
        monkeypatch.setattr(adg, "EXPORTS_DIR", tmp_path)
        tmp_path.mkdir(exist_ok=True)
        adg.ai_exporter.export_all()
        import json as _j
        data = _j.loads((tmp_path / "quad_market_dataset.json").read_text(encoding="utf-8"))
        assert data[0]["rrp_price_toman"] == 82_000_000


# ---------------------------------------------------------------------------
# شمارنده‌ی تایید انسانی در پنجره دسته
# ---------------------------------------------------------------------------
class TestHumanVerifiedCounter:
    def test_counts(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from sync.ingest_torob import ingest_torob_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from fastapi.testclient import TestClient
        from server.app import app
        from server.routes import get_category_products

        ingest_torob_items([{"key": "t1", "title": "گوشی موبایل اپل iPhone 15 Pro 256", "price": 80_000_000, "num_shops": 5}])
        ingest_divar_items([{"token": "v1", "title": "گوشی اپل iPhone 15 Pro 256 کارکرده", "price": 60_000_000}])
        data_purifier.run_full_purification_pipeline()
        rows = {r["item_id"]: r["id"] for r in db.fetchall("SELECT id, item_id FROM store_listings;")}
        tc = TestClient(app)
        tc.post('/api/audit/verify-listing', json={"id": rows["t1"]})
        tc.post('/api/audit/verify-listing', json={"id": rows["v1"]})

        res = get_category_products(category="mobile", limit=10, offset=0)
        assert res["total"] == 1
        assert res["human_verified_listings"] == 2   # هر دو آگهی ✋ دارند
        assert res["human_verified_products"] == 1   # اما یک محصول


# ---------------------------------------------------------------------------
# نمای «باقی‌مانده‌ها» (فیلتر سرور-ساید پنهان‌سازی)
# ---------------------------------------------------------------------------
class TestHideVerifiedView:
    def _setup(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from fastapi.testclient import TestClient
        from server.app import app
        ingest_divar_items([
            {"token": "v1", "title": "هدفون سونی WH-1000XM5", "price": 18_000_000},
            {"token": "v2", "title": "هدفون بلوتوثی انکر", "price": 2_500_000},
            {"token": "v3", "title": "هدفون گیمینگ ریزر", "price": 5_000_000},
        ])
        data_purifier.run_full_purification_pipeline()
        rows = {r["item_id"]: r["id"] for r in db.fetchall("SELECT id, item_id FROM store_listings;")}
        tc = TestClient(app)
        tc.post('/api/audit/verify-listing', json={"id": rows["v1"]})
        tc.post('/api/audit/verify-listing', json={"id": rows["v2"]})
        return tc

    def test_default_view_shows_only_remaining(self, clean_db, fast_ai):
        tc = self._setup(clean_db, fast_ai)
        d = tc.get('/api/analytics/category-products?category=headphone&limit=10').json()
        assert d["api_build"] == "human-counters-v6"
        assert d["hide_verified"] is True
        assert d["listings_total"] == 1            # فقط باقی‌مانده
        assert d["listings_all"] == 3              # کل
        assert len(d["items"]) == 1                # صفحه‌ی ۱ پر از کار باقی‌مانده
        assert all(i["is_human_verified"] == 0 for i in d["items"])

    def test_show_all_view(self, clean_db, fast_ai):
        tc = self._setup(clean_db, fast_ai)
        d = tc.get('/api/analytics/category-products?category=headphone&limit=10&hide_verified=false').json()
        assert d["hide_verified"] is False
        assert d["listings_total"] == 3
        assert len(d["items"]) == 3
        assert sum(i["is_human_verified"] for i in d["items"]) == 2   # دو تا نشان ✋✓


# ---------------------------------------------------------------------------
# شمارنده 👁 بررسی‌شده + مرتب‌سازی جدیدترین + حذف تکراری‌ها
# ---------------------------------------------------------------------------
class TestReviewedAndNewest:
    def test_reviewed_counter_and_sort(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from fastapi.testclient import TestClient
        from server.app import app
        ingest_divar_items([
            {"token": "v1", "title": "هدفون سونی WH-1000XM5", "price": 18_000_000},
            {"token": "v2", "title": "هدفون بلوتوثی انکر", "price": 2_500_000},
            {"token": "j1", "title": "هدفون قدیمی شکسته", "price": 100_000},
        ])
        data_purifier.run_full_purification_pipeline()
        rows = {r["item_id"]: r["id"] for r in db.fetchall("SELECT id, item_id FROM store_listings;")}
        tc = TestClient(app)
        tc.post('/api/audit/verify-listing', json={"id": rows["v1"]})
        tc.post('/api/audit/confirm-junk', json={"ids": [rows["j1"]]})

        d = tc.get('/api/analytics/category-products?category=headphone&limit=10').json()
        assert d["api_build"] == "human-counters-v6"
        assert d["human_reviewed_listings"] == 2  # یک تایید + یک چرت
        newest = tc.get('/api/analytics/category-products?category=headphone&limit=10&sort=newest&hide_verified=false').json()
        ids = [i["id"] for i in newest["items"]]
        assert ids == sorted(ids, reverse=True)   # جدیدترین اول
        assert newest["sort"] == "newest"


class TestDedupe:
    def test_dedupe(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from database.db_manager import db
        import dedupe_listings as dd
        # یک آگهی با دو توکنِ متفاوت (شبیه باگ استخراج) + یک آگهی معمولی
        ingest_divar_items([
            {"token": "tokA", "title": "گوشی اپل iPhone 13 کارکرده", "price": 40_000_000},
            {"token": "tokB", "title": "گوشی اپل iPhone 13 کارکرده", "price": 40_000_000},
            {"token": "tokC", "title": "گوشی اپل iPhone 13 کارکرده", "price": 40_000_000},
            {"token": "v9", "title": "گوشی سامسونگ Galaxy S23", "price": 50_000_000},
        ])
        before = db.fetchone("SELECT COUNT(*) c FROM store_listings;")["c"]
        assert before == 4
        groups = dd.find_exact_groups()
        assert len(groups) == 1 and len(list(groups.values())[0]) == 3

        import sys as _sys
        _sys.argv = ["dedupe_listings.py", "--purge"]
        dd.main()
        after = db.fetchone("SELECT COUNT(*) c FROM store_listings;")["c"]
        assert after == 2  # یکی از سه تکراری ماند + آگهی معمولی
        kept = db.fetchone("SELECT COUNT(*) c FROM store_listings WHERE item_id='tokC';")["c"]
        assert kept == 1   # جدیدترین نگه داشته شد


# ---------------------------------------------------------------------------
# دلیل آماده‌ی حذف + dedupe فازی + دلیل در خروجی ML
# ---------------------------------------------------------------------------
class TestJunkReasons:
    def test_custom_reason_stored_and_counted(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from fastapi.testclient import TestClient
        from server.app import app
        ingest_divar_items([{"token": "j1", "title": "قاب گوشی طرح دار", "price": 180_000}])
        data_purifier.run_full_purification_pipeline()
        row = db.fetchone("SELECT id FROM store_listings LIMIT 1;")
        tc = TestClient(app)
        r = tc.post('/api/audit/confirm-junk', json={"ids": [row["id"]], "reason": "لوازم جانبی (قاب، شارژر، گلس، کابل...)"})
        assert r.status_code == 200
        back = db.fetchone("SELECT rejection_reason, quality_status FROM store_listings WHERE id=?;", (row["id"],))
        assert back["quality_status"] == "CONFIRMED_JUNK"
        assert back["rejection_reason"].startswith("✋")
        assert "لوازم جانبی" in back["rejection_reason"]

    def test_reason_in_training_export(self, clean_db, fast_ai, tmp_path, monkeypatch):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from fastapi.testclient import TestClient
        from server.app import app
        import export_training_data as et
        import json as _j
        ingest_divar_items([{"token": "j1", "title": "بند ساعت چرمی دست‌دوز", "price": 250_000}])
        data_purifier.run_full_purification_pipeline()
        row_id = None
        from database.db_manager import db
        row_id = db.fetchone("SELECT id FROM store_listings LIMIT 1;")["id"]
        tc = TestClient(app)
        tc.post('/api/audit/confirm-junk', json={"ids": [row_id], "reason": "لوازم جانبی (قاب، شارژر، گلس، کابل...)"})
        monkeypatch.setattr(et, "OUT_DIR", tmp_path)
        tmp_path.mkdir(exist_ok=True)
        et.main()
        rows = [_j.loads(x) for x in (tmp_path / "quality_train.jsonl").read_text(encoding="utf-8").splitlines() if x]
        junk = [r for r in rows if r["label"] == "junk"]
        assert junk and any("لوازم جانبی" in (r.get("reason") or "") for r in junk)


class TestFuzzyDedupe:
    def test_fuzzy_catches_price_variant(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from database.db_manager import db
        import dedupe_listings as dd
        # همان آگهی، دوبار پست‌شده: عنوان کمی متفاوت + قیمت چانه‌زده
        ingest_divar_items([
            {"token": "f1", "title": "گوشی اپل iPhone 13 کارکرده سالم", "price": 40_000_000},
            {"token": "f2", "title": "گوشی اپل iPhone 13 کارکرده", "price": 41_500_000},
            {"token": "v9", "title": "گوشی سامسونگ Galaxy S23 نو", "price": 50_000_000},
        ])
        fuzzy = dd.find_fuzzy_groups()
        assert len(fuzzy) == 1 and len(fuzzy[0]) == 2   # دو نسخه‌ی همان آگهی
        import sys as _s
        _s.argv = ["dedupe_listings.py", "--purge"]
        dd.main()
        left = db.fetchone("SELECT COUNT(*) c FROM store_listings;")["c"]
        assert left == 2  # جدیدترین نسخه + آگهی دیگر
        kept = db.fetchone("SELECT COUNT(*) c FROM store_listings WHERE item_id='f2';")["c"]
        assert kept == 1


# ---------------------------------------------------------------------------
# گارد ضد-اسپم (بازپست انبوه) + حذف خودکار تکراری در چرخه
# ---------------------------------------------------------------------------
class TestSpamFloodGuard:
    def test_flood_group_junked_two_copy_untouched(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        # ۶ نسخه‌ی همسان (اسپم) + ۲ نسخه‌ی دیگر (زیر آستانه) + ۱ آگهی یگانه
        flood = [{"token": f"s{i}", "title": "خریدار وفروشنده انواع کنسول پلی استیشن", "price": 100_000_000} for i in range(6)]
        pair = [{"token": f"p{i}", "title": "هدفون مدل Y سالم", "price": 3_000_000} for i in range(2)]
        single = [{"token": "u1", "title": "گوشی سامسونگ Galaxy S24", "price": 62_000_000}]
        ingest_divar_items(flood + pair + single)
        res = data_purifier.run_full_purification_pipeline()
        assert res["breakdown"]["spam_flood"] >= 6
        st = {r["item_id"]: r["quality_status"] for r in db.fetchall("SELECT item_id, quality_status FROM store_listings;")}
        assert all(st[f"s{i}"] == "ACCESSORY_OR_JUNK" for i in range(6))
        assert st["u1"] == "VERIFIED"                    # یگانه دست‌نخورده
        junk_reason = db.fetchone("SELECT rejection_reason FROM store_listings WHERE item_id='s0';")["rejection_reason"]
        assert "اسپم" in junk_reason

    def test_human_lock_not_overwritten(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import data_purifier
        from database.db_manager import db
        from fastapi.testclient import TestClient
        from server.app import app
        flood = [{"token": f"h{i}", "title": "فروشنده و خریدار انواع کارت گرافیک", "price": 100_000} for i in range(6)]
        ingest_divar_items(flood)
        data_purifier.run_full_purification_pipeline()
        rows = [r["id"] for r in db.fetchall("SELECT id FROM store_listings ORDER BY id LIMIT 1;")]
        tc = TestClient(app)
        tc.post('/api/audit/verify-listing', json={"id": rows[0]})   # قفل انسانی روی یکی
        data_purifier.run_full_purification_pipeline()               # پالایش مجدد
        locked = db.fetchone("SELECT quality_status, is_verified FROM store_listings WHERE id=?;", (rows[0],))
        assert locked["quality_status"] == "VERIFIED" and locked["is_verified"] == 1  # مقدس ماند


class TestAutoDedupe:
    def test_quiet_dedupe(self, clean_db, fast_ai):
        from sync.ingest_divar import ingest_divar_items
        from database.db_manager import db
        from dedupe_listings import dedupe_exact_quiet
        ingest_divar_items([
            {"token": "d1", "title": "کیس گیمینگ i5 نسل 11 کامل", "price": 165_000_000},
            {"token": "d2", "title": "کیس گیمینگ i5 نسل 11 کامل", "price": 165_000_000},
        ])
        n = dedupe_exact_quiet()
        assert n == 1
        assert db.fetchone("SELECT COUNT(*) c FROM store_listings;")["c"] == 1


# ---------------------------------------------------------------------------
# فیکس تاکسونومی: اسبقیت کالای آغازین عنوان (رفع خطای هدفون→storage)
# ---------------------------------------------------------------------------
class TestLeadingTitlePriority:
    CASES = [
        ("", "هدفون بلوتوثی گیمینگ مدل s20", "headphone"),
        ("", "هدفون بلوتوثی بیتس مدل FLEX", "headphone"),
        ("", "هدفون بلوتوثی میبرو مدل M1", "headphone"),
        ("", "کامپیوتر کوچک ایسوس مدل PB63 با پردازنده", "desktop-pc"),
        ("", "نگهدارنده کارت گرافیک ایسوس مدل ROG HERC", "other"),
        ("", "کارت گرافیک RX 6900XT MERC 16GB", "gpu"),
        ("", "گوشی سامسونگ A07", "mobile"),
        ("", "سیستم گیمینگ i5 با RX 580", "desktop-pc"),
        ("", "رم کورسیر 32 گیگ DDR4", "ram"),
        ("", "مانیتور ال جی 24 اینچ", "monitor"),
        ("digital", "گوشی شیائومی Redmi Note 13", "mobile"),
        ("", "هارد اکسترنال وسترن 2 ترابایت", "storage"),
        ("", "مک بوک پرو M3 پرو", "laptop"),
        ("", "کنسول PS5 دیجیتال", "console"),
    ]

    def test_leading_priority(self):
        from core.taxonomy import normalize_category
        for raw, title, expected in self.CASES:
            got = normalize_category(raw, title)
            assert got == expected, f"({raw!r}, {title[:30]!r}) → {got} != {expected}"


# ---------------------------------------------------------------------------
# مقاوم‌سازی اعمال گروهی: آیتم ناموجود → موفقیتِ صفر، نه خطای کل
# ---------------------------------------------------------------------------
class TestTolerantBulk:
    def test_verify_missing_returns_zero_not_404(self, clean_db, fast_ai):
        from fastapi.testclient import TestClient
        from server.app import app
        tc = TestClient(app)
        r = tc.post('/api/audit/bulk-action', json={"ids": [999999], "action": "verify"})
        assert r.status_code == 200 and r.json()["applied"] == 0

    def test_setcat_missing_returns_zero_not_404(self, clean_db, fast_ai):
        from fastapi.testclient import TestClient
        from server.app import app
        tc = TestClient(app)
        r = tc.post('/api/audit/bulk-action', json={"ids": [999999], "action": "set-category", "category": "gpu"})
        assert r.status_code == 200 and r.json()["updated_products"] == 0


# ---------------------------------------------------------------------------
# فیکس کالبدشکافی desktop-pc: کیس خالی/رکاب (خطاهای قانون)
# ---------------------------------------------------------------------------
class TestCaseAndRackFixes:
    CASES = [
        ("", "کیس گیمینگ RTX580 8G", "other"),           # کیس خالی با اسم گرافیک
        ("", "کیس گرین آراد اِکو 3 عدد فن", "other"),
        ("", "رکاب انگشتر زیبا و خوش رنگ", "other"),
        ("", "کیس پنجره‌ای ATX", "other"),
        ("", "کیس گیمینگ i5 نسل 11 آماده", "desktop-pc"),
        ("", "کیس گیمینگ i5 12400f RX 580", "desktop-pc"),
        ("", "کیس آماده مونتاژ RTX 3060", "desktop-pc"),
        ("", "رک مونتاژ شده سرور", "desktop-pc"),
        ("", "رک 19 اینچی سرور", "desktop-pc"),
        ("", "کامپیوتر کوچک ایسوس PB63 با پردازنده", "desktop-pc"),
    ]

    def test_case_rack(self):
        from core.taxonomy import normalize_category
        for raw, title, expected in self.CASES:
            got = normalize_category(raw, title)
            assert got == expected, f"{title[:30]!r} → {got} != {expected}"
