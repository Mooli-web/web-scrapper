# -*- coding: utf-8 -*-
"""تست قوانین پالایش و نرمال‌ساز — اجرای درست بودن رفتار اصلی سیستم."""


# ---------------------------------------------------------------------------
# نرمال‌ساز
# ---------------------------------------------------------------------------
class TestNormalizeBrands:
    def test_fake_dell_fixed(self):
        from core.normalizer import extract_brand
        assert extract_brand("ساعت هوشمند ریولینک مدل RL-2 pro") == "other"
        assert extract_brand("هدفون بلوتوثی مدل XT-500") == "other"
        assert extract_brand("دلار آمریکا خرید و فروش") == "other"
        assert extract_brand("کیبورد لمسی touchpad مدل X") == "other"

    def test_real_brands_kept(self):
        from core.normalizer import extract_brand
        assert extract_brand("لپ تاپ دل ایسپایرو 3520") == "dell"
        assert extract_brand("لپ تاپ Dell3520") == "dell"
        assert extract_brand("گوشی موبایل اپل مدل iPhone 13") == "apple"
        assert extract_brand("کارت گرافیک rtx4060") == "nvidia"
        assert extract_brand("پلی‌استیشن 5 اسلیم") == "sony"
        assert extract_brand("ایفون13") == "apple"

    def test_normalize_brand_persian_leak(self):
        from core.normalizer import normalize_brand
        assert normalize_brand("سامسونگ", "other") == "samsung"
        assert normalize_brand("اپل") == "apple"
        assert normalize_brand("متفرقه", "detected_x") == "detected_x"
        assert normalize_brand("", "other") == "other"


class TestCanonicalKeys:
    def test_stable_across_calls(self):
        from core.normalizer import generate_canonical_key
        assert generate_canonical_key("مایکروفون خازنی حرفه‌ای")[0] == \
               generate_canonical_key("مایکروفون خازنی حرفه‌ای")[0]

    def test_persian_english_match(self):
        from core.normalizer import generate_canonical_key
        assert generate_canonical_key("آیفون 13 پرو مکس 256")[0] == \
               generate_canonical_key("iPhone 13 Pro Max 256GB")[0]
        assert generate_canonical_key("گوشی شیاومی ردمی نوت 13 پرو")[0] == \
               generate_canonical_key("Xiaomi Redmi Note 13 Pro")[0]


# ---------------------------------------------------------------------------
# پالاینده — حذف‌ها
# ---------------------------------------------------------------------------
JUNK_CASES = [
    ("فقط کارتن خالی آیفون 13", 2_000_000, "mobile", "divar"),
    ("بند ساعت هوشمند اپل واچ سیلیکونی اورجینال", 850_000, "smart-watches", "digikala"),
    ("فقط بند فلزی ساعت سامسونگ", 400_000, "smart-watches", "digikala"),
    ("قاب گوشی سامسونگ Galaxy S24 طرح دار", 180_000, "mobile-samsung", "digikala"),
    ("شارژر لپ تاپ لنوو 65 وات اورجینال", 850_000, "laptop-lenovo", "digikala"),
    ("ماوس گیمینگ ریزر", 2_200_000, "gaming", "digikala"),
    ("توکن و گیفت کارت پلی استیشن 50 دلاری", 4_500_000, "gaming", "digikala"),
    ("اشتراک یک ماهه گیم پس", 900_000, "gaming", "digikala"),
    ("ماشین حساب علمی کاسیو", 1_200_000, "digital", "digikala"),
    ("اسپلیتر 1 به 2 پورت VGA", 450_000, "digital", "digikala"),
    ("خریدار ( خرید ) کارت گرافیک ریگ فروش", 8_000_000, "gpu", "divar"),
    ("معاوضه رایانه اپل با پرداخت آنی", 1_000_000_000, "digital", "divar"),
]

KEEP_CASES = [
    ("گوشی موبایل سامسونگ Galaxy A55", 21_000_000, "mobile", "digikala"),
    ("ساعت هوشمند اپل واچ با بند فلزی", 25_000_000, "smart-watches", "digikala"),
    ("مچ بند هوشمند شیائومی Band 10 با بند سیلیکونی", 9_998_000, "watch", "digikala"),
    ("کارت گرافیک Sapphire RX 580 8GB", 12_000_000, "gpu", "divar"),
    ("رافیک XFX RX580 استوک ماین نشده", 9_950_000, "gpu", "divar"),
    ("حافظه SSD اکسترنال اپیسر 512 گیگابایت", 23_400_000, "storage", "digikala"),
    ("رم کورسیر VENGEANCE 32 گیگابایت", 98_100_000, "parts", "torob"),
    ("مادربرد گیگابایت B860M", 53_500_000, "parts", "digikala"),
    ("پک Xbox Series S با دو دسته", 28_000_000, "console", "digikala"),
    ("کتاب خوان آمازون Kindle 2024", 33_900_000, "tablet", "digikala"),
    ("کنسول رومیزی کیدز پرو handheld", 2_000_000, "console", "digikala"),
    ("هدست گیمینگ هایپرایکس Cloud III", 6_500_000, "headphone", "digikala"),
]

AI_REVIEW_CASES = [
    ("دوچرخه کوهستان اورلورد", 18_000_000, "digital", "digikala"),
    ("گجست ناشناخته مدل X7 پرو", 3_500_000, "digital", "digikala"),
]


class TestPurifierRules:
    def test_junk_rejected(self):
        from core.data_cleaner import StandardDataPurifier
        p = StandardDataPurifier()
        for title, price, cat, store in JUNK_CASES:
            ok, status, reason, _ = p.evaluate_single_listing(title, price, cat, store)
            assert not ok, f"باید حذف شود: {title} → {status} ({reason})"

    def test_real_devices_verified(self):
        from core.data_cleaner import StandardDataPurifier
        p = StandardDataPurifier()
        for title, price, cat, store in KEEP_CASES:
            ok, status, reason, _ = p.evaluate_single_listing(title, price, cat, store)
            assert ok, f"باید تایید شود: {title} → {status} ({reason})"

    def test_ambiguous_goes_to_ai_queue(self):
        from core.data_cleaner import StandardDataPurifier
        p = StandardDataPurifier()
        for title, price, cat, store in AI_REVIEW_CASES:
            ok, status, _, _ = p.evaluate_single_listing(title, price, cat, store)
            assert (not ok) and status == "NEEDS_AI_REVIEW", f"{title} → {status}"

    def test_zwnj_defective(self):
        from core.data_cleaner import StandardDataPurifier
        p = StandardDataPurifier()
        for title in ("پلی‌استیشن 5 روشن‌نمی‌شود", "پلی استیشن 5 روشن نمی شود"):
            ok, status, _, _ = p.evaluate_single_listing(title, 15_000_000, "console", "divar")
            assert (not ok) and status == "DEFECTIVE_PARTS", f"{title!r} → {status}"

    def test_fake_prices(self):
        from core.data_cleaner import StandardDataPurifier
        p = StandardDataPurifier()
        for price in (9999, 11111, 123456, 30_000):
            ok, status, _, _ = p.evaluate_single_listing("گوشی فرضی مدل X", price, "mobile", "divar")
            assert (not ok) and status == "FAKE_PRICE", f"price={price} → {status}"

    def test_price_deviation_goes_to_ai_not_delete(self):
        """انحراف قیمتی حذف قطعی نیست — مرجع ممکن است مسموم باشد (رفع RX580)."""
        from core.data_cleaner import StandardDataPurifier
        p = StandardDataPurifier()
        ok, status, _, _ = p.evaluate_single_listing(
            "رافیک XFX RX580", 12_000_000, "gpu", "divar", ref_price=1_980_000)
        assert (not ok) and status == "NEEDS_AI_REVIEW", status


class TestRobustReference:
    def test_median_resists_poison(self):
        from core.data_cleaner import robust_reference
        assert robust_reference([1_980_000, 11_000_000, 12_000_000, 12_500_000]) == 11_500_000

    def test_ignores_accessory_level_prices(self):
        from core.data_cleaner import robust_reference
        assert robust_reference([100_000, 150_000, 10_000_000, 12_000_000]) == 11_000_000


class TestLearnedSignals:
    def test_learn_and_auto_reject(self, clean_db):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import StandardDataPurifier, load_learned_signals
        ingest_divar_items([{"token": "j1", "title": "آویز 4 گرمی دو رو کلاسیک حراج", "price": 99_250}])
        from database.db_manager import db
        row = db.fetchone("SELECT id FROM store_listings LIMIT 1;")
        p = StandardDataPurifier()
        res = p.confirm_junk([row["id"]])
        assert res["learned_signals"] == ["آویز"]
        load_learned_signals(force=True)
        # FIX جدید: فقط عنوانِ دقیقاً یکسان حذف می‌شود؛ مشابه‌ها به صف AI می‌روند
        ok, status, reason, _ = p.evaluate_single_listing("آویز 4 گرمی دو رو کلاسیک حراج", 99_250, "digital", "divar")
        assert (not ok) and "تأییدشده" in reason
        ok2, status2, _, _ = p.evaluate_single_listing("آویز طلا 6 گرمی", 45_000_000, "digital", "divar")
        assert (not ok2) and status2 == "NEEDS_AI_REVIEW"

    def test_protected_words_never_learned(self, clean_db):
        from sync.ingest_divar import ingest_divar_items
        from core.data_cleaner import StandardDataPurifier
        ingest_divar_items([{"token": "g1", "title": "گوشی سامسونگ صفحه شکسته", "price": 8_000_000}])
        from database.db_manager import db
        row = db.fetchone("SELECT id FROM store_listings LIMIT 1;")
        p = StandardDataPurifier()
        res = p.confirm_junk([row["id"]])
        assert res["learned_signals"] == [] and res["skipped_unsafe"] == 1
