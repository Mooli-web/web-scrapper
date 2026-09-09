# -*- coding: utf-8 -*-
"""
🗂️ Taxonomy — دسته‌بندی یکپارچه‌ی محصولات ۴ بازار
===================================================
هر بازار دسته‌بندی خودش را می‌فرستد (mobile-apple، laptops-apple،
gaming-playstation، auctions_ending، digital، ...)؛ این ماژول همه را به
یک تاکسونومی استاندارد نگاشت می‌کند و برای دسته‌های مبهم/عمومی از عنوان
کالا دسته را تشخیص می‌دهد.

محاسبه در لحظه است (بدون تغییر schema) — همیشه با داده‌ی تازه سازگار است.
"""

import re
from typing import Optional

from database.db_manager import db

# دسته‌های استاندارد + برچسب فارسی
STANDARD_CATEGORIES = {
    "mobile":       "گوشی موبایل",
    "laptop":       "لپ‌تاپ",
    "tablet":       "تبلت",
    "console":      "کنسول بازی",
    "gpu":          "کارت گرافیک",
    "cpu":          "پردازنده",
    "ram":          "حافظه رم",
    "storage":      "هارد و SSD",
    "motherboard":  "مادربرد",
    "desktop-pc":   "سیستم آماده",
    "monitor":      "مانیتور",
    "watch":        "ساعت هوشمند",
    "headphone":    "هدفون و ایرباد",
    # pc-parts = قطعه‌ی جداگانه‌ی کامپیوتر: کیس خالی، منبع تغذیه/پاور، خنک‌کننده
    #            و کولر، فن، کارت صدا/شبکه/کپچر. «سیستم/کیس آماده» همچنان
    #            desktop-pc است.
    "pc-parts":     "قطعات کامپیوتر",
    # other = متفرقه: روتر و تجهیزات شبکه، لوازم جانبی بی‌دسته و هر آنچه
    #         در دسته‌های بالا جا نمی‌شود.
    "other":        "متفرقه",
}

# ---- نگاشت دسته‌ی خام هر بازار (به ترتیب اولویت بررسی) ----
_RAW_CATEGORY_RULES = [
    ("desktop", "desktop-pc"), ("ready-pc", "desktop-pc"), ("system", "desktop-pc"),
    ("graphic", "gpu"), ("gpu", "gpu"),
    ("processor", "cpu"), ("cpu", "cpu"),
    ("smart-watch", "watch"), ("watch", "watch"), ("wearable", "watch"),
    ("apple-watch", "watch"),
    ("headphone", "headphone"), ("audio", "headphone"),
    ("power-supply", "pc-parts"), ("psu", "pc-parts"), ("case", "pc-parts"),
    ("cooling", "pc-parts"), ("cooler", "pc-parts"), ("fan", "pc-parts"),
    ("storage", "storage"), ("hard", "storage"), ("ssd", "storage"), ("flash", "storage"),
    ("monitor", "monitor"), ("screen", "monitor"),
    ("motherboard", "motherboard"), ("mainboard", "motherboard"),
    ("laptop", "laptop"), ("notebook", "laptop"), ("ultrabook", "laptop"), ("surface", "laptop"),
    ("tablet", "tablet"), ("ipad", "tablet"),
    ("console", "console"), ("playstation", "console"), ("xbox", "console"),
    ("gaming", "console"),
    ("mobile", "mobile"), ("phone", "mobile"),
    ("vintage", "mobile"),
]

# ---- تشخیص از روی عنوان (برای digital/general/auctions/خالی) ----
# ترتیب مهم است: «سیستم/کیس آماده» قبل از قطعات چک می‌شود چون عنوان سیستم
# معمولاً اسم قطعات (RX 580 ،i5 ...) را هم دارد.
_TITLE_RULES = [
    # FIX: سیستم/کیس آماده اول از همه چک می‌شود (حتی اگر اسم قطعه‌ای مثل RX 580
    # یا i5 در عنوانش باشد) — قبلاً این عنوان‌ها می‌رفتند دسته‌ی قطعه.
    (re.compile(r'سیستم\s*(?:گیم|رندر|حرفه|آماده|سرهم)|کیس\s*(?:گیم|آماده|سرهم|\+)|\bریگ\b|ماینر|pc\s*گیمینگ|کامل\s*(?:مونتاژ|سمبل)', re.I), "desktop-pc"),
    (re.compile(r'مادربرد|motherboard', re.I), "motherboard"),
    (re.compile(r'نگهدارنده\s*کارت\s*گرافیک|پایه\s*نگهدارنده\s*گرافیک', re.I), "other"),  # جانبی — قبل از gpu
    (re.compile(r'کارت\s*گرافیک|گرافیک\s|\brtx\b|\bgtx\b|\brx\s*\d{3,4}|رافیک|\bvga\b', re.I), "gpu"),
    (re.compile(r'پردازنده|سی\s*پی\s*یو|\bcpu\b|core\s*i\d|ryzen\s*\d', re.I), "cpu"),
    (re.compile(r'\bرم\b.{0,25}(?:گیگ|ddr|کانال)|ddr[345]|حافظه\s*رم|ram\s*\d{1,2}', re.I), "ram"),
    (re.compile(r'هارد|اس\s*اس\s*دی|\bssd\b|\bhdd\b|حافظه(?:\s*اکسترنال|\s*اینترنال)?|فلش\s*مموری', re.I), "storage"),
    (re.compile(r'ساعت\s*هوشمند|مچ\s*بند|اپل\s*واچ|apple\s*watch|galaxy\s*watch|\bband\s*\d', re.I), "watch"),
    (re.compile(r'هدفون|هدست|ایرباد|ایرپاد|هندزفری|headphone|earbuds|airpods', re.I), "headphone"),
    (re.compile(r'مانیتور|monitor', re.I), "monitor"),
    (re.compile(r'کنسول|پلی\s*استیشن|\bps[345]\b|xbox|ایکس\s*باکس|نینتندو|nintendo', re.I), "console"),
    (re.compile(r'لپ\s*تاپ|لپتاپ|لپ‌تاپ|مک\s*بوک|macbook|thinkpad|ideapad|legion|vivobook|zenbook', re.I), "laptop"),
    (re.compile(r'تبلت|آیپد|ipad|galaxy\s*tab', re.I), "tablet"),
    (re.compile(r'گوشی|موبایل|آیفون|ایفون|iphone|گلکسی\s*[sa]\d|redmi|poco|تلفن\s*همراه', re.I), "mobile"),
    # ── قطعات کامپیوتر (کیس خالی، منبع تغذیه، خنک‌کننده، کارت جانبی)
    #   عمداً «آخر» آمده تا عنوان کامل (سیستم/لپ‌تاپ/کیس گیمینگ) اول به دسته‌ی
    #   خودش برود و فقط قطعه‌ی جداگانه اینجا بیفتد.
    (re.compile(r'منبع\s*تغذیه|\bpsu\b|power\s*supply|پاور\s*(?:کامپیوتر|گیمینگ|ماژولار)|'
                r'\bsfx\b', re.I), "pc-parts"),
    (re.compile(r'خنک\s*کننده|کولر|واتر\s*کولر|کولینگ|هیت\s*سینک|هیتسینک|'
                r'فن\s*(?:کیس|پردازنده|cpu)|\bcpu\s*cooler\b|خمیر\s*سیلیکون', re.I), "pc-parts"),
    (re.compile(r'کیس(?:\s*کامپیوتر)?\s*(?:خالی|بدون\s*قطعه|mid\s*tower|full\s*tower)|'
                r'\bcomputer\s*case\b|\bchassis\b', re.I), "pc-parts"),
    (re.compile(r'کارت\s*(?:صدا|شبکه|توسعه|کپچر)|sound\s*card|network\s*card|'
                r'capture\s*card', re.I), "pc-parts"),
]


# FIX: کالای آغازینِ عنوان اسبقیت مطلق دارد — نشانه‌های کوتاه برند/مدل (s20، M1،
# PB، Buds، FLEX...) دیگر نباید دسته را بدزدند (خطای «هدفون → storage»).
_LEADING_TITLE_RULES = [
    (re.compile(r'^هدفون|^هدست|^ایرباد|^ایرپاد|^هندزفری|earbuds|airpods|headphone', re.I), "headphone"),
    (re.compile(r'^گوشی|^موبایل|^آیفون|^ایفون|^تلفن\s*همراه', re.I), "mobile"),
    (re.compile(r'^تبلت|^آیپد|^ipad', re.I), "tablet"),
    (re.compile(r'^لپ\s*تاپ|^لپتاپ|^نوت\s*بوک|^مک\s*بوک|^مکبوک|^macbook|thinkpad|ideapad|legion|vivobook|zenbook', re.I), "laptop"),
    (re.compile(r'^کنسول|^پلی\s*استیشن|^ایکس\s*باکس|\bps[345]\b|^xbox|^نینتندو', re.I), "console"),
    (re.compile(r'^ساعت\s*هوشمند|^مچ\s*بند|^اپل\s*واچ|apple\s*watch', re.I), "watch"),
    (re.compile(r'^مانیتور', re.I), "monitor"),
    (re.compile(r'^کامپیوتر\s*(کوچک|مینی)|مینی\s*پی\s*سی|mini\s*pc|^سرور|^رک[^ا]\S*\s*(?:مونتاژ|سرور|اینچی)|^رک\s+(?:مونتاژ|سرور)|^رک\s*\d', re.I), "desktop-pc"),
    # FIX: کیسِ همراه با قطعات (cpu/gpu/ram/نسل/آماده/مونتاژ) → سیستم؛ کیسِ خالی یا مبهم → other
    # (ترتیب مهم: اول آیا قطعه دارد؟ اگر نه → other؛ در نهایت سیستم/ریگ/ماینر)
    (re.compile(r'^کیس(?=.{0,45}(?:i[3579]\s*-?\d|ryzen|نسل|آماده|مونتاژ|سیستم\s*کامل|ddr))', re.I), "desktop-pc"),  # باید سیگنال cpu/آماده هم باشد — فقط gpu کافی نیست (کیس با فن RTX هم نام دارد)
    # کیسِ خالی/بدون قطعه → قطعه‌ی کامپیوتر؛ بقیه‌ی کیس‌های مبهم → متفرقه
    (re.compile(r'^کیس(?!\s*(?:کامپیوتر\s*)?(?:خالی|بدون\s*قطعه|mid\s*tower|full\s*tower))', re.I), "other"),
    (re.compile(r'^سیستم|^ریگ|^ماینر', re.I), "desktop-pc"),
    # خنک‌کننده/کولر در «آغاز» عنوان = قطعه‌ی جداگانه (وگرنه «پردازنده» در
    # «خنک کننده پردازنده» آن را به cpu می‌برد). قواعد بالاتر (سیستم/کیس) اول اجرا
    # می‌شوند، پس «سیستم با واتر کولر» همچنان desktop-pc می‌ماند.
    (re.compile(r'^خنک\s*کننده|^کولر|^واتر\s*کولر|^هیت\s*سینک|^هیتسینک|'
                r'^فن\s*(?:کیس|پردازنده|cpu)|^خمیر\s*سیلیکون', re.I), "pc-parts"),
    (re.compile(r'^کارت\s*گرافیک|^گرافیک|^رافیک', re.I), "gpu"),
    (re.compile(r'^مادربرد', re.I), "motherboard"),
    (re.compile(r'^پردازنده|^سی\s*پی\s*یو|^cpu|core\s*i\d|ryzen', re.I), "cpu"),
    (re.compile(r'^هارد|^اس\s*اس\s*دی|^حافظه|^فلش', re.I), "storage"),
    (re.compile(r'^رم\b|^رام\b|ddr[345]', re.I), "ram"),
]


def normalize_category(raw_category: Optional[str], title: str = "") -> str:
    """دسته‌ی استاندارد را برمی‌گرداند (کلید انگلیسی؛ برچسب با label)."""
    raw = (raw_category or "").strip().lower()
    t = (title or "").strip()

    # ۱) اسبقیت مطلق: کلمه‌ی آغازینِ عنوان خودش گونه‌ی کالاست (فارسی طبیعی فروشگاه‌ها)
    if t:
        for pat, std in _LEADING_TITLE_RULES:
            if pat.search(t):
                return std

    # ۲) دسته‌ی خام منبع
    if raw and raw not in ("digital", "general", "uncategorized"):
        for frag, std in _RAW_CATEGORY_RULES:
            if frag in raw:
                return std
    # ۳) الگوهای داخل عنوان
    if t:
        for pat, std in _TITLE_RULES:
            if pat.search(t):
                return std
    return "other"


def category_label(std_key: str) -> str:
    return STANDARD_CATEGORIES.get(std_key, STANDARD_CATEGORIES["other"])

def ensure_category_columns():
    """
    NEW: ستون‌های category_std / category_source روی canonical_products (برای
    دیتابیس‌های موجود — SQLite از ADD COLUMN IF NOT EXISTS پشتیبانی نمی‌کند).
    category_std  = دسته‌ی استاندارد (قاعده‌ای یا اصلاح‌شده توسط AI)
    category_source = 'rule' | 'ai'
    """
    try:
        cols = {r["name"] for r in db.fetchall("PRAGMA table_info(canonical_products);")}
        if "category_std" not in cols:
            db.execute("ALTER TABLE canonical_products ADD COLUMN category_std TEXT DEFAULT '';")
        if "category_source" not in cols:
            db.execute("ALTER TABLE canonical_products ADD COLUMN category_source TEXT DEFAULT '';")
        # NEW: تاریخچه‌ی تغییر دسته — گنج آموزش ML (مثال‌های «قبلاً غلط، الان درست»)
        db.execute("""
            CREATE TABLE IF NOT EXISTS category_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_key TEXT NOT NULL,
                old_category  TEXT DEFAULT '',
                old_source    TEXT DEFAULT '',
                new_category  TEXT NOT NULL,
                new_source    TEXT DEFAULT '',
                changed_by    TEXT DEFAULT 'human',
                note          TEXT DEFAULT '',
                is_uncertain  INTEGER DEFAULT 0,
                created_at    TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        hcols = {r["name"] for r in db.fetchall("PRAGMA table_info(category_history);")}
        if "note" not in hcols:
            db.execute("ALTER TABLE category_history ADD COLUMN note TEXT DEFAULT '';")
        if "is_uncertain" not in hcols:
            db.execute("ALTER TABLE category_history ADD COLUMN is_uncertain INTEGER DEFAULT 0;")
    except Exception as e:
        import logging
        logging.getLogger("hub.taxonomy").debug(f"category columns note: {e}")


def record_category_change(canonical_keys, new_category: str, new_source: str = "manual",
                           note: str = "", is_uncertain: bool = False):
    """NEW: ثبت append-only تغییر دسته (برای آموزش ML از اصلاحات انسانی).
    note = دلیل اختیاری انسانی؛ is_uncertain = نمونه‌ی سخت (Active Learning)."""
    import logging
    try:
        ensure_category_columns()
        rows = db.fetchall(
            f"""SELECT canonical_key, category_std, category_source FROM canonical_products
                WHERE canonical_key IN ({','.join('?' * len(canonical_keys))});""",
            tuple(canonical_keys))
        inserts = [(r["canonical_key"], r["category_std"] or "", r["category_source"] or "",
                    new_category, new_source, "human", (note or "")[:300],
                    1 if is_uncertain else 0) for r in rows]
        if inserts:
            db.executemany("""
                INSERT INTO category_history (canonical_key, old_category, old_source, new_category,
                                              new_source, changed_by, note, is_uncertain)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, inserts)
    except Exception as e:
        logging.getLogger("hub.taxonomy").debug(f"category history note: {e}")
