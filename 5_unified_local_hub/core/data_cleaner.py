import os
import re
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
from database.db_manager import db
from core.normalizer import extract_primary_product_title, clean_persian_text
from core.taxonomy import normalize_category, ensure_category_columns

logger = logging.getLogger("hub.data_cleaner")

EXPORTS_DIR = Path(__file__).resolve().parent.parent / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
AGENT_AUDIT_FILE = EXPORTS_DIR / "audit_review_for_agent.json"

# Strict, Clear Keyword Patterns for Accessories, Junk, and Defective Parts
JUNK_KEYWORDS = [
    # NEW: آگهی‌های «خرید/معاوضه» درخواست خرید هستند، نه فروش کالا — قیمت‌شان
    # ساختگی است (مثل ۱ میلیارد تومان) و آمار را مسموم می‌کند.
    # «قابل معاوضه» (فروش با امکان معاوضه) استثنا شده است.
    (r'^(?:خرید|خریدار|معاوضه)\b|(?<!قابل )معاوضه|پرداخت\s*آنی|\(\s*خرید\s*\)', 'آگهی خرید/معاوضه است — درخواست خرید، نه فروش کالا'),
    (r'فقط\s*(?:کارتن|جعبه|پوکه)', 'جعبه یا کارتن خالی به جای کالا'),
    (r'کارتن\s*(?:خالی|اصلی|فابریک|گوشی|کنسول)', 'جعبه یا کارتن خالی به جای کالا'),
    (r'جعبه\s*(?:خالی|گوشی|کنسول|لپ\s*تاپ)', 'جعبه یا کارتن خالی به جای کالا'),
    (r'پوکه\s*(?:گوشی|کنسول)', 'پوکه یا بدنه خالی به جای دستگاه'),
    (r'برد\s*(?:سوخته|اوراقی|داغی|معیوب)', 'برد سوخته یا قطعه اوراقی'),
    (r'ال\s*سی\s*دی\s*(?:شکسته|سوخته|تعویضی)', 'صفحه نمایش شکسته یا معیوب'),
    (r'روشن\s*نمی\s*شود', 'دستگاه خاموش و غیرقابل استفاده'),
    (r'\bخاموش\b', 'دستگاه خاموش یا نیازمند تعمیر'),
    (r'جهت\s*قطعات|برای\s*قطعات|اوراقی', 'دستگاه معیوب صرفاً جهت استفاده از قطعات'),
    (r'آیکلود\s*قفل|قفل\s*آیکلود|بای\s*پس', 'دستگاه قفل شده / بدون کارایی عادی'),
    (r'قاب\s*و\s*گلس|گلس\s*(?:محافظ|سرامیکی)', 'قاب، محافظ صفحه یا گلس به جای دستگاه'),
    (r'کاور\s*(?:ژله\s*ای|سیلیکونی|طرح|مگنتی|دسته|کنسول)', 'کاور یا قاب محافظ به جای کالا'),
    (r'روکش\s*(?:دسته|کنسول|سیلیکونی|چرمی)', 'روکش دسته یا برچسب به جای دستگاه'),
    # FIX: the old pattern بند\s*(سیلیکونی|فلزی|...) matched the phrase
    # "با بند سیلیکونی/فلزی" inside REAL smartwatch titles and killed them
    # (even a 25M toman Apple Watch). Now a listing is flagged only when the
    # strap IS the product: title starts with 'بند ...' or says 'فقط بند'.
    (r'^(?:فقط\s*)?بند\s*(?:ساعت|سیلیکونی|فلزی|چرمی|استیل|نایلونی|مگنتی|مغناطیسی)', 'بند ساعت به جای خود ساعت'),
    (r'فقط\s*بند|بند\s*(?:جدا|اضافی|یدکی)', 'بند جداگانه به جای خود دستگاه'),
    (r'شارژر\s*(?:خالی|اصلی|دیواری|فست)|کابل\s*(?:شارژ|تبدیل|hdmi)', 'شارژر یا کابل جانبی به جای دستگاه'),
    (r'پایه\s*(?:شارژ|نگهدارنده|استند|خنک\s*کننده|فن)', 'پایه، استند یا خنک‌کننده به جای دستگاه'),
    (r'کیف\s*(?:لپ\s*تاپ|کنسول|هندزفری|دسته|ps[45]|xbox)', 'کیف محافظ به جای خود دستگاه'),
    (r'باکس\s*(?:کنسول|دسته|هارد|بازی)', 'باکس یا جعبه به جای دستگاه'),
    (r'فقط\s*دسته|دسته\s*(?:اضافی|یدکی|فیک)', 'فقط کنترلر یا دسته بازی به جای کنسول'),
    (r'استیکر|اسکین|پوسته\s*کنسول', 'برچسب یا اسکین به جای دستگاه'),
    (r'سی\s*دی\s*بازی|دیسک\s*بازی|اکانت\s*(?:قانونی|ظرفیتی|بازی)', 'دیسک یا اکانت بازی به جای کنسول'),
    # NEW: گیفت‌کارت/توکن/اشتراک — کالای مجازی، نه دستگاه
    (r'گیفت\s*(?:کارت|کد)|اشتراک\s*\S+|کیف\s*پول|تیم\s*پاور', 'گیفت کارت / اشتراک / کالای مجازی به جای دستگاه'),
    (r'نصب\s*(?:بازی|ویندوز|برنامه|انواع\s*بازی)|کپی\s*خور|دیتای\s*بازی', 'خدمات نرم‌افزاری یا نصب بازی به جای دستگاه')
]

BLATANT_FAKE_PRICES = [
    (r'^(1{4,}|2{4,}|3{4,}|4{4,}|5{5,}|6{5,}|7{5,}|8{5,}|9{4,})$', 'قیمت تکراری صوری (مانند ۱۱۱۱، ۲۲۲۲، ۹۹۹۹)'),
    (r'^(1234|12345|123456|1234567|12345678|123456789)$', 'قیمت ترتیبی صوری (۱۲۳۴۵۶)'),
    (r'^(987654|654321)$', 'قیمت معکوس صوری')
]

CATEGORY_MIN_REALISTIC_PRICE = {
    'mobile': 1_200_000,
    'laptop': 4_000_000,
    'console': 3_000_000,
    'gpu': 1_500_000,
    'smart-watches': 300_000,
    'headphones': 150_000,
    'storage-devices': 200_000
}

# ============================================================================
# NEW LAYER 1a — Leading-Noun Detection (اسم اول محصول)
# در فروشگاه‌های ایرانی (مثل دیجی‌کالا) عنوان همیشه با «نوع کالا» شروع می‌شود:
# «گوشی موبایل...»، «قاب گوشی...»، «شارژر لپ تاپ...». اگر اسم اول، کالای جانبی
# باشد، کل آگهی جانبی است — بدون توجه به اینکه اسم چه گوشی/لپ‌تاپی در ادامه آمده.
# ============================================================================
LEADING_JUNK_NOUNS = {
    'قاب', 'گلس', 'کاور', 'بند', 'کیف', 'کابل', 'شارژر', 'پایه', 'استند', 'هولدر',
    'رینگ', 'فیش', 'باتری', 'باطری', 'روکش', 'استیکر', 'برچسب', 'مبدل', 'هاب',
    'کارتخوان', 'ماوس', 'موس', 'کیبورد', 'صفحه', 'دسته', 'قلم', 'محافظ',
    'گارد', 'شیشه', 'پاوربانک', 'اسپیکر', 'تریپاد', 'لنز', 'میکروفون', 'پوسته',
    'کلاهک', 'رادیو', 'تلفن', 'گیرنده', 'عینک', 'لیزر', 'چراغ', 'فن', 'کولر',
    'ماشین', 'کارت', 'توکن', 'گیفت', 'اکانت', 'اشتراک', 'شارژ', 'فوم',
    # NEW: کابل‌ها/مبدل‌های جانبی (نمونه‌ی واقعی: «اسپلیتر 1 به 2 پورت VGA...»
    # قبلاً با دلیل نامرتبطِ کف قیمت laptop حذف می‌شد)
    'اسپلیتر', 'تبدیل'
}
# استثناها: عنوان‌هایی که با این اسم‌ها شروع می‌شوند ولی دستگاه اصلی‌اند
LEADING_JUNK_EXCEPTIONS = re.compile(
    r'^(?:کارت\s*گرافیک|کارت\s*صدا|کارت\s*ورد)', re.I
)
# نکته: «کارت گرافیک» و «کارت صدا» دستگاه/قطعه‌ی اصلی‌اند؛ بقیه‌ی عنوان‌های
# شروع‌شونده با «کارت» (کارت حافظه، کارت خوان...) جانبی محسوب می‌شوند.

# NEW: اسم‌های آغازینِ «کالای در اسکوپ» — قطعی و بدون نیاز به AI.
# ریشه‌ی خطای باقی‌مانده‌ی گروک: روی «هارد/SSD اکسترنال» نوسان داشت
# (توشیبا را تایید و اپیسر را رد می‌کرد!). اینجا قطعی‌اش می‌کنیم.
DEVICE_LEADING_NOUNS = {'هارد', 'مادربرد', 'رم', 'پردازنده'}
SSD_LEADING_RE = re.compile(r'^(?:حافظه\s+)?(?:اس\s*اس\s*دی|ssd|hdd)(?:\s|$)', re.I)

# ============================================================================
# NEW LAYER 1b — Device Evidence (نشانه‌ی کالای اصلی)
# اگر عنوان نه واژه‌ی «دستگاه» داشته باشد و نه مدل شناخته‌شده‌ای، دیگر به‌صورت
# کورکورانه VERIFIED نمی‌شود؛ به وضعیت NEEDS_AI_REVIEW می‌رود تا لایه‌ی AI تصمیم بگیرد.
# ============================================================================
DEVICE_EVIDENCE_WORDS = {
    'گوشی', 'موبایل', 'آیفون', 'ایفون', 'تابلت', 'لپ تاپ', 'لپتاپ', 'نوت بوک',
    'مک بوک', 'کنسول', 'پلی استیشن', 'پلی‌استیشن', 'ایکس باکس', 'نینتندو',
    'کارت گرافیک', 'گرافیک', 'پردازنده', 'سی پی یو', 'ساعت هوشمند', 'مچ بند',
    'هدفون', 'هدست', 'ایرباد', 'هندزفری', 'ایرپاد', 'مانیتور', 'کامپیوتر',
    'دسکتاپ', 'All-in-One', 'سرفیس', 'بازی',
    # NEW (از نمونه‌های حذف‌شده به غلط): کتابخوان/کیندل، رافیک (گرافیک محاوره‌ای)، ریگ ماینر
    'کیندل', 'کتاب خوان', 'کتابخوان', 'رافیک', 'ریگ',
    # FIX: تبلت/آیپد از لیست جا مانده بود — همه‌ی تبلت‌ها بی‌خودی به صف AI می‌رفتند
    'تبلت', 'آیپد', 'ipad',
}
DEVICE_MODEL_PATTERNS = [
    re.compile(r'\b(?:iphone|ipad|galaxy|redmi|poco|note\s*\d{2})\b', re.I),
    re.compile(r'\b(?:ps[2345]|playstation|xbox|nintendo|switch)\b', re.I),
    re.compile(r'\b(?:rtx|gtx|rx)\s*\d{3,4}', re.I),
    re.compile(r'\b(?:macbook|thinkpad|ideapad|legion|vivobook|zenbook|tuf|rog|victus|omen|aspire|predator|nitro|surface)\b', re.I),
    re.compile(r'\b(?:apple\s*watch|gear|band\s*\d{1,2})\b', re.I),
    re.compile(r'\b(?:ryzen|core\s*i[3579]|i[3579][- ]\d{4,5})\b', re.I),
]

# ============================================================================
# NEW: Learned Junk Signals — الگوهای آموخته‌شده از تأیید کاربر
# کاربر آگهی چرت را تیک می‌زند → کلمه‌ی آغازین عنوان به‌عنوان «الگوی چرت»
# ذخیره می‌شود → از آن پس هر عنوانی که با آن شروع شود، رایگان حذف می‌شود.
# ============================================================================
_LEARNED_SIGNALS: Dict[str, tuple] = {}   # signal -> (example_title, exact_title)
_LEARNED_LOADED_AT: float = 0.0

# واژه‌هایی که هرگز به‌عنوان الگوی چرت یاد گرفته نمی‌شوند (ایمنی: یک تیک
# اشتباه نباید کل دسته‌ی سالم را حذف کند — مثلاً تیک روی «گوشی خراب» هرگز
# الگوی «گوشی» نمی‌سازد)
PROTECTED_SIGNAL_WORDS = set(w.lower() for w in DEVICE_EVIDENCE_WORDS) | {
    'گوشی', 'موبایل', 'لپ', 'لپتاپ', 'نوت', 'مک', 'کنسول', 'کارت', 'ساعت',
    'هدفون', 'هدست', 'تبلت', 'مانیتور', 'سیستم', 'رایانه', 'کامپیوتر', 'نو',
    'آیفون', 'ایفون', 'گلکسی', 'پلی', 'ایکس', 'ورد', 'ایرپاد', 'هارد',
    'اس', 'ssd', 'hdd', 'cpu', 'gpu', 'psu', 'pc', 'laptop', 'phone', 'watch',
}


def _ensure_learned_table():
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS learned_junk_signals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                signal       TEXT UNIQUE NOT NULL,
                example_title TEXT DEFAULT '',
                exact_title  TEXT DEFAULT '',
                created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                times_hit    INTEGER DEFAULT 0
            );
        """)
        cols = {r["name"] for r in db.fetchall("PRAGMA table_info(learned_junk_signals);")}
        if "exact_title" not in cols:
            db.execute("ALTER TABLE learned_junk_signals ADD COLUMN exact_title TEXT DEFAULT '';")
    except Exception as e:
        logger.warning(f"learned_junk_signals init note: {e}")


def load_learned_signals(force: bool = False):
    """Learned junk signals loader (60s cache)."""
    import time as _time
    global _LEARNED_SIGNALS, _LEARNED_LOADED_AT
    now = _time.time()
    if not force and _LEARNED_SIGNALS and (now - _LEARNED_LOADED_AT) < 60:
        return
    try:
        rows = db.fetchall("SELECT signal, example_title, exact_title FROM learned_junk_signals;")
        _LEARNED_SIGNALS = {r['signal']: (r['example_title'] or '', r['exact_title'] or '') for r in rows}
        _LEARNED_LOADED_AT = now
    except Exception as e:
        logger.debug(f"learned signals load note: {e}")


def extract_junk_signal(title: str) -> Optional[str]:
    """کلمه‌ی آغازین عنوانِ پاک‌شده را به‌عنوان الگو برمی‌گرداند (اگر ایمن باشد)."""
    cleaned = clean_persian_text(extract_primary_product_title(title or ''))
    words = cleaned.split()
    if not words:
        return None
    first = words[0].strip('.,،؛:!?()[]').lower()
    if len(first) < 2 or len(first) > 20:
        return None
    if first in PROTECTED_SIGNAL_WORDS:
        return None
    return first

class StandardDataPurifier:
    """
    Standardized, Ultra-Transparent 2-Status Data Purification Engine.
    Evaluates listings, generates agent audit review batches, and applies verified decisions.
    """
    def __init__(self):
        _ensure_learned_table()

    def evaluate_single_listing(self, title: str, price: int, category: str, store_key: str, ref_price: int = 0) -> Tuple[bool, str, str, float]:
        # FIX: clean_persian_text (instead of raw split_merged_words) normalizes
        # ZWNJ (نیم‌فاصله), Arabic ي/ك and Persian digits first, so patterns like
        # 'روشن‌نمی‌شود' are no longer able to bypass the defective-item filters.
        cleaned_title = clean_persian_text(title)
        primary_title = extract_primary_product_title(cleaned_title)
        t_clean = primary_title.lower()

        # ---- NEW: Learned Junk Signals (الگوهای آموخته‌شده از تأیید کاربر) ----
        if _LEARNED_SIGNALS:
            first_word = t_clean.split(' ', 1)[0] if t_clean else ''
            hit = _LEARNED_SIGNALS.get(first_word)
            # FIX: الگو فقط وقتی می‌گیرد که «کل» عنوان با مثال تأییدشده یکسان باشد —
            # قبلاً هر عنوانی با همان کلمه‌ی آغازین حذف می‌شد (مادربرد سوخته ← همه‌ی
            # مادربردها!). کالاهای دیگرِ همان کلمه به قوانین عادی برمی‌گردند.
            if hit and hit[1] and t_clean == hit[1]:
                return False, 'ACCESSORY_OR_JUNK', (
                    'عنوان دقیقاً همان آگهی چرتِ تأییدشده‌ی شماست'
                    + (f' («{first_word}...»)' if first_word else '')
                ), 30.0

        if price < 50_000:
            return False, 'FAKE_PRICE', 'قیمت زیر ۵۰ هزار تومان (غیرواقعی برای کالای اصلی)', 0.0

        p_str = str(price)
        for pattern, reason in BLATANT_FAKE_PRICES:
            if re.match(pattern, p_str):
                return False, 'FAKE_PRICE', reason, 0.0

        # FIX: removed the generic word 'کنسول' from this list — it killed cheap
        # kids/handheld consoles (کنسول کیدز، رترو و...) which are real products.
        # Only true gaming-console brand names trigger the price floor now.
        if price < 3_000_000 and any(w in t_clean for w in ['ps4', 'ps5', 'xbox', 'پلی استیشن', 'ایکس باکس']):
            return False, 'ACCESSORY_OR_JUNK', 'قیمت کمتر از ۳ میلیون تومان برای کنسول (روکش/کیف/بازی)', 10.0

        for pattern, reason in JUNK_KEYWORDS:
            if re.search(pattern, t_clean):
                # FIX: 'روشن' and 'نمی' added — a device that "روشن نمی شود" is
                # DEFECTIVE_PARTS, not an accessory (was mislabeled before).
                status = 'DEFECTIVE_PARTS' if any(w in pattern for w in ['سوخته', 'شکسته', 'اوراقی', 'خاموش', 'قطعات', 'قفل', 'روشن', 'نمی شود']) else 'ACCESSORY_OR_JUNK'
                return False, status, reason, 15.0

        cat_lower = str(category).lower()
        for cat_name, min_price in CATEGORY_MIN_REALISTIC_PRICE.items():
            if cat_name in cat_lower and price < min_price:
                if cat_name == 'mobile' and any(w in t_clean for w in ['glx', 'جی ال ایکس', 'nokia', 'نوکیا', 'ساده', 'دکمه ای']) and price >= 400_000:
                    continue
                # FIX: cheap kids/retro/handheld consoles are real products, not junk.
                if cat_name == 'console' and any(w in t_clean for w in ['کیدز', 'کودک', 'رترو', 'آتاری', 'سگا', 'پرتابل', 'retro', 'atari', 'sega', 'handheld']):
                    continue
                return False, 'ACCESSORY_OR_JUNK', f'قیمت کمتر از حداقل معقول برای {cat_name} (احتمال لوازم جانبی)', 20.0

        is_official = store_key in ['digikala', 'torob']
        if not is_official and ref_price > 0:
            ratio = price / ref_price
            # FIX: انحراف قیمتی دیگر حذفِ قطعی نیست — مرجع (کف بازار) خودش ممکن
            # است توسط یک آگهی ارزانِ اشتباه مسموم شده باشد (نمونه‌ی واقعی:
            # RX 580 واقعی ۱۲M در برابر مرجع مسموم ۱.۹۸M!). هر دو جهتِ انحراف
            # به صف بازبینی AI می‌روند تا با زمینه قضاوت شوند.
            if ratio < 0.15:
                return False, 'NEEDS_AI_REVIEW', f'قیمت بسیار پایین‌تر از مرجع ({ref_price:,} ت) — یا آگهی جانبی است یا مرجع خطا دارد؛ نیازمند قضاوت AI', 0.0
            elif ratio > 3.0:
                return False, 'NEEDS_AI_REVIEW', f'قیمت بیش از ۳ برابر مرجع ({ref_price:,} ت) — یا گران‌فروشی است یا مرجع مسموم/اشتباه است؛ نیازمند قضاوت AI', 0.0

        # ---- NEW LAYER 1a: Leading-Noun Detection -------------------------
        # عنوان با اسم کالای جانبی شروع می‌شود؟ (مثل «قاب گوشی»، «شارژر لپ تاپ»)
        first_word = t_clean.split(' ', 1)[0] if t_clean else ''
        if first_word in LEADING_JUNK_NOUNS and not LEADING_JUNK_EXCEPTIONS.match(t_clean):
            return False, 'ACCESSORY_OR_JUNK', f'عنوان با «{first_word}» شروع می‌شود (کالای جانبی/قطعه، نه دستگاه اصلی)', 22.0

        # ---- NEW LAYER 1b: Device Evidence -------------------------------
        # اگر هیچ نشانه‌ای از «دستگاه اصلی» در عنوان نیست، دیگر به‌صورت کور
        # VERIFIED نمی‌شود؛ به صف بازبینی هوشمند (Groq) می‌رود.
        # NEW: اسم‌های آغازین قطعی (هارد/SSD/مادربرد/رم/پردازنده) هم نشانه‌ی
        # کالای در اسکوپ هستند — بدون ارجاع به AI.
        has_device_evidence = (
            any(w in t_clean for w in DEVICE_EVIDENCE_WORDS) or
            any(p.search(t_clean) for p in DEVICE_MODEL_PATTERNS) or
            first_word in DEVICE_LEADING_NOUNS or
            bool(SSD_LEADING_RE.match(t_clean))
        )
        if not has_device_evidence:
            return False, 'NEEDS_AI_REVIEW', 'عنوان فاقد نشانه‌ی کالای اصلی است — در صف بازبینی هوشمند (AI)', 0.0

        # FIX: Torob is a price aggregator (mixed third-party shops), not an
        # official retailer like Digikala — it now gets a slightly lower trust score.
        if store_key == 'digikala':
            confidence = 99.0
        elif store_key == 'torob':
            confidence = 96.0
        else:
            confidence = 94.0
        return True, 'VERIFIED', 'تاییدشده - کالا و قیمت منطبق با استانداردهای بازار', confidence

    def run_full_purification_pipeline(self) -> Dict[str, Any]:
        load_learned_signals()  # NEW: الگوهای آموخته‌شده قبل از پالایش تازه شوند
        ensure_category_columns()  # NEW: ستون‌های دسته (خارج از تراکنش — ALTER نیاز به قفل ندارد)
        learned_hit_counts: Dict[str, int] = {}
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    l.id, l.canonical_key, l.store_key, l.item_id, l.title_fa,
                    l.price_toman, l.condition, c.category_key,
                    COALESCE(NULLIF(c.torob_min_price_toman, 0), c.digikala_price_toman, 0) as ref_price
                FROM store_listings l
                JOIN canonical_products c ON l.canonical_key = c.canonical_key
                WHERE NOT (
                    l.quality_status IN ('CONFIRMED_JUNK', 'REJECTED_BY_AGENT', 'AI_REJECTED')
                    OR l.rejection_reason LIKE '🤖%'
                    OR l.rejection_reason LIKE '%Agent%'
                    OR l.rejection_reason LIKE '✋%'
                );
            """)
            all_listings = cursor.fetchall()

            # FIX: تصمیم‌های لایه‌های بالاتر (تأیید کاربر، ایجنت، AI) با اجرای
            # مجدد قوانین بازنویسی نمی‌شوند — تصمیم انسانی/هوشمند قفل است.
            locked_row = db.fetchone("""
                SELECT COUNT(*) AS c FROM store_listings
                WHERE quality_status IN ('CONFIRMED_JUNK', 'REJECTED_BY_AGENT', 'AI_REJECTED')
                   OR rejection_reason LIKE '🤖%'
                   OR rejection_reason LIKE '%Agent%'
                   OR rejection_reason LIKE '✋%';
            """)
            locked_count = locked_row['c'] if locked_row else 0

            clean_count = 0
            junk_count = 0
            defective_count = 0
            fake_price_count = 0
            outlier_count = 0
            needs_ai_count = 0
            spam_flood_count = 0

            updates = []
            flagged_for_agent = []

            for r in all_listings:
                is_ver, status, reason, score = self.evaluate_single_listing(
                    title=r['title_fa'],
                    price=r['price_toman'],
                    category=r['category_key'] or 'digital',
                    store_key=r['store_key'],
                    ref_price=r['ref_price']
                )

                if is_ver:
                    clean_count += 1
                else:
                    if status == 'ACCESSORY_OR_JUNK' and reason.startswith('الگوی آموخته'):
                        sig = reason.split('«')[1].split('»')[0] if '«' in reason else '?'
                        learned_hit_counts[sig] = learned_hit_counts.get(sig, 0) + 1
                    if status == 'ACCESSORY_OR_JUNK': junk_count += 1
                    elif status == 'DEFECTIVE_PARTS': defective_count += 1
                    elif status == 'FAKE_PRICE': fake_price_count += 1
                    elif status == 'STATISTICAL_OUTLIER': outlier_count += 1
                    elif status == 'NEEDS_AI_REVIEW': needs_ai_count += 1

                    if len(flagged_for_agent) < 200:
                        flagged_for_agent.append({
                            "id": r['id'],
                            "canonical_key": r['canonical_key'],
                            "title": r['title_fa'],
                            "price_toman": r['price_toman'],
                            "market_ref_price": r['ref_price'],
                            "store": r['store_key'],
                            "current_status": status,
                            "reason": reason
                        })

                updates.append((1 if is_ver else 0, status, reason, score, r['id']))

            cursor.executemany("""
                UPDATE store_listings SET
                    is_verified = ?,
                    quality_status = ?,
                    rejection_reason = ?,
                    confidence_score = ?
                WHERE id = ?;
            """, updates)

            # NEW: گارد ضد-اسپم — گروه‌های انبوه (همان فروشگاه+عنوان+قیمت، ≥۵ نسخه)
            # پست‌های بازپست‌شده‌ی انبوه در دیوار هستند؛ هر سینک دوباره می‌آیند.
            # اینجا در هر پالایش، همه‌ی نسخه‌ها (به‌جز تصمیم‌های انسانی قفل‌شده) چرت
            # flags می‌شوند تا به AI/آمار راه پیدا نکنند.
            from collections import Counter as _C
            _rows = cursor.execute("""
                SELECT id, store_key, title_fa, price_toman, rejection_reason, quality_status
                FROM store_listings
                WHERE NOT (rejection_reason LIKE '✋%' OR quality_status IN ('CONFIRMED_JUNK','AI_REJECTED','REJECTED_BY_AGENT'));
            """).fetchall()
            _grp = _C()
            _by_key = {}
            for _r in _rows:
                _k = (_r[1], clean_persian_text(_r[2] or "").lower(), _r[3] or 0)
                _grp[_k] += 1
                _by_key.setdefault(_k, []).append(_r[0])
            _spam_ids = []
            for _k, _n in _grp.items():
                if _n >= 5:
                    _spam_ids.extend(_by_key[_k])
            if _spam_ids:
                cursor.executemany("""
                    UPDATE store_listings SET is_verified=0,
                           quality_status='ACCESSORY_OR_JUNK',
                           rejection_reason='🚫 پست تکراری/اسپم انبوه (نسخه‌های همسان)',
                           confidence_score=35
                    WHERE id = ?;
                """, [(i,) for i in _spam_ids])
                spam_flood_count = len(_spam_ids)
            else:
                spam_flood_count = 0

            # Re-calculate clean statistical prices
            # FIX: مرجع مقاوم — قبلاً MIN(CASE...) بود و یک آگهی ارزانِ اشتباه
            # کف بازار را مسموم می‌کرد (RX 580 با مرجع ۱.۹۸M!). الان میانه‌ی
            # مقاوم قیمت‌های تاییدشده‌ی هر فروشگاه محاسبه می‌شود.
            cursor.execute("""
                SELECT l.canonical_key, l.store_key, l.price_toman
                FROM store_listings l
                WHERE l.is_verified = 1 AND l.price_toman > 0;
            """)
            price_rows = cursor.fetchall()

            per_key: Dict[str, Dict[str, List[int]]] = {}
            for pr in price_rows:
                bucket = per_key.setdefault(pr['canonical_key'], {'digikala': [], 'torob': [], 'divar': [], 'esam': []})
                if pr['store_key'] in bucket:
                    bucket[pr['store_key']].append(pr['price_toman'])

            canon_updates = []
            for c_key, bucket in per_key.items():
                digi_ref = robust_reference(bucket['digikala'])
                torob_ref = robust_reference(bucket['torob'])
                new_ref = torob_ref or digi_ref or 0
                used_prices = [p for p in [_mean(bucket['divar']), _mean(bucket['esam'])] if p > 0]
                dep_pct = 0.0
                if new_ref > 0 and used_prices:
                    avg_used = sum(used_prices) / len(used_prices)
                    dep_pct = round(((new_ref - avg_used) / new_ref) * 100.0, 1)

                canon_updates.append((
                    digi_ref,
                    torob_ref,
                    int(_mean(bucket['divar'])),
                    min(bucket['divar']) if bucket['divar'] else 0,
                    int(_mean(bucket['esam'])),
                    min(bucket['esam']) if bucket['esam'] else 0,
                    dep_pct,
                    c_key
                ))

            cursor.executemany("""
                UPDATE canonical_products SET
                    digikala_price_toman = ?,
                    torob_min_price_toman = ?,
                    divar_avg_price_toman = ?,
                    divar_min_price_toman = ?,
                    esam_avg_price_toman = ?,
                    esam_min_price_toman = ?,
                    depreciation_percent = ?
                WHERE canonical_key = ?;
            """, canon_updates)

            # NEW: دسته‌بندی استاندارد — پرکردن قاعده‌ای برای محصولات بدون دسته
            # (AI بعداً در بازبینی/ممیزی، در صورت مغایرت اصلاح می‌کند: category_source='ai')
            cursor.execute("""
                SELECT canonical_key, title_fa, category_key FROM canonical_products
                WHERE category_std IS NULL OR category_std = '';
            """)
            no_cat = cursor.fetchall()
            if no_cat:
                cursor.executemany("""
                    UPDATE canonical_products SET category_std = ?, category_source = 'rule'
                    WHERE canonical_key = ?;
                """, [(normalize_category(r["category_key"], r["title_fa"] or ""), r["canonical_key"]) for r in no_cat])

            conn.commit()

        # Save flagged batch for Agent review
        with open(AGENT_AUDIT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": db.fetchone("SELECT CURRENT_TIMESTAMP as now;")['now'],
                "total_flagged": len(flagged_for_agent),
                "items": flagged_for_agent
            }, f, ensure_ascii=False, indent=2)

        total = len(all_listings)
        clean_pct = round((clean_count / total) * 100.0, 1) if total > 0 else 100.0

        logger.info(f"Purification Completed: {clean_count}/{total} ({clean_pct}%) verified clean records.")

        return {
            "total_raw_records": total,
            "locked_by_higher_layer": locked_count,
            "verified_clean_records": clean_count,
            "clean_percentage": clean_pct,
            "discarded_count": total - clean_count,
            "flagged_for_agent_file": str(AGENT_AUDIT_FILE),
            "breakdown": {
                "verified_clean": clean_count,
                "accessory_or_junk": junk_count,
                "defective_parts": defective_count,
                "fake_clickbait_prices": fake_price_count,
                "statistical_outliers": outlier_count,
                "needs_ai_review": needs_ai_count,
                "spam_flood": spam_flood_count,
                "learned_pattern_junk": sum(learned_hit_counts.values())
            }
        }

    def confirm_junk(self, ids: List[int], reason: str = "") -> Dict[str, Any]:
        """
        NEW: تأیید انسانی «این آگهی چرت است» + یادگیری الگو برای آینده.
        - خود آگهی‌ها: وضعیت CONFIRMED_JUNK با اطمینان ۱۰۰
        - از عنوان هرکدام، کلمه‌ی آغازینِ ایمن به‌عنوان الگوی چرت ذخیره می‌شود
        - الگوها بلافاصله فعال می‌شوند (پالایش بعدی، مشابه‌ها را رایگان می‌گیرد)
        """
        valid_ids = [i for i in ids if isinstance(i, int) and not isinstance(i, bool)]
        if not valid_ids:
            return {"confirmed": 0, "learned_signals": [], "skipped_unsafe": 0}

        rows = db.fetchall(
            "SELECT id, title_fa FROM store_listings WHERE id IN ({seq});".format(
                seq=",".join("?" * len(valid_ids))
            ),
            tuple(valid_ids),
        )

        confirmed = 0
        learned: List[str] = []
        skipped_unsafe = 0
        updates = []
        for r in rows:
            confirmed += 1
            updates.append(r["id"])
            sig = extract_junk_signal(r["title_fa"] or "")
            if sig is None:
                # واژه‌ی آغازین protect است (مثل «گوشی خراب») — یادگیری رد شد
                if (r["title_fa"] or "").strip():
                    skipped_unsafe += 1
                continue
            if sig not in learned:
                learned.append(sig)
            try:
                from core.normalizer import clean_persian_text as _cpt
                from core.normalizer import extract_primary_product_title as _eppt
                exact = _cpt(_eppt(r["title_fa"] or "")).lower()
                db.execute("""
                    INSERT INTO learned_junk_signals (signal, example_title, exact_title)
                    VALUES (?, ?, ?)
                    ON CONFLICT(signal) DO UPDATE SET example_title = excluded.example_title,
                                                       exact_title = excluded.exact_title;
                """, (sig, r["title_fa"], exact))
            except Exception as e:
                logger.debug(f"learned signal insert note: {e}")

        # NEW: دلیل دلخواه/آماده‌ی انسانی — داده‌ی آموزشی غنی‌تر برای ML
        human_reason = (f"✋ {reason.strip()}" if reason and reason.strip()
                        else '✋ تأیید شما: کالای چرت/غیرمرتبط')
        if updates:
            db.executemany("""
                UPDATE store_listings SET
                    is_verified = 0,
                    quality_status = 'CONFIRMED_JUNK',
                    rejection_reason = ?,
                    confidence_score = 100.0
                WHERE id = ?;
            """, [(human_reason, uid) for uid in updates])

        load_learned_signals(force=True)
        logger.info(f"User confirmed {confirmed} junk items; learned {len(learned)} new signals: {learned}")
        return {"confirmed": confirmed, "learned_signals": learned, "skipped_unsafe": skipped_unsafe}

    def list_learned_signals(self) -> List[Dict[str, Any]]:
        """NEW: فهرست الگوهای آموخته‌شده (برای مدیریت در داشبورد)."""
        try:
            return db.fetchall(
                "SELECT id, signal, example_title, created_at, times_hit FROM learned_junk_signals ORDER BY id DESC;"
            )
        except Exception:
            return []

    def remove_learned_signal(self, signal_id: int) -> bool:
        """NEW: حذف یک الگوی آموخته‌شده (اگر اشتباه یاد گرفته شده باشد)."""
        removed = db.execute("DELETE FROM learned_junk_signals WHERE id = ?;", (signal_id,))
        load_learned_signals(force=True)
        return bool(removed)

    def apply_agent_decisions(self, decisions: List[Dict[str, Any]]) -> int:
        """
        Applies verified decisions returned by the Agent into SQLite master database.
        Each decision item: {"id": int, "decision": "VERIFIED" | "REJECTED", "reason": str, "confidence": float}
        """
        if not decisions:
            return 0

        updates = []
        for d in decisions:
            if not isinstance(d, dict):
                continue
            item_id = d.get("id")
            # FIX: skip invalid entries (missing/None/non-int id) — before, an id
            # of None silently executed "UPDATE ... WHERE id = NULL" no-ops.
            if not isinstance(item_id, int) or isinstance(item_id, bool):
                continue
            dec = str(d.get("decision", "VERIFIED")).upper()
            is_ver = 1 if dec == "VERIFIED" else 0
            reason = d.get("reason") or ("تاییدشده توسط بررسی وب Agent" if is_ver else "ردشده توسط Agent")
            try:
                score = min(100.0, max(0.0, float(d.get("confidence", 98.0))))
            except (TypeError, ValueError):
                score = 98.0
            status = "VERIFIED" if is_ver else d.get("status", "REJECTED_BY_AGENT")

            updates.append((is_ver, status, reason, score, item_id))

        if not updates:
            return 0

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                UPDATE store_listings SET
                    is_verified = ?,
                    quality_status = ?,
                    rejection_reason = ?,
                    confidence_score = ?
                WHERE id = ?;
            """, updates)
            # FIX: return the number of rows actually matched/updated (an id that
            # does not exist in the table contributes 0 instead of being counted).
            applied = cursor.rowcount
            conn.commit()

        logger.info(f"Applied {applied} Agent verification decisions into database ({len(updates)} received).")
        return applied

# ============================================================================
# NEW: مرجع قیمت مقاوم در برابر مسمومیت (Robust Reference Price)
# ریشه‌ی حذفِ غلطِ RX 580 ها: مرجع = MIN قیمت‌های تاییدشده بود؛ یک آگهی
# ارزانِ اشتباه (۱.۹۸M) کف بازار را «مسموم» می‌کرد و کالاهای واقعی ۸-۱۲M
# «بیش از ۳ برابر سقف» حذف می‌شدند. الان: میانه‌ی قیمت‌های تاییدشده،
# با حذف قیمت‌های زیر کفِ ۳۰۰K (سطح لوازم جانبی).
# ============================================================================
MIN_DEVICE_REFERENCE_FLOOR = 300_000


def robust_reference(prices: List[int]) -> int:
    """میانه‌ی مقاوم قیمت‌ها برای مرجع بازار (نو)."""
    ps = sorted(p for p in prices if p and p >= MIN_DEVICE_REFERENCE_FLOOR)
    if not ps:
        return 0
    n = len(ps)
    mid = n // 2
    if n % 2:
        return ps[mid]
    return int((ps[mid - 1] + ps[mid]) / 2)


def _mean(prices: List[int]) -> float:
    ps = [p for p in prices if p and p > 0]
    return sum(ps) / len(ps) if ps else 0.0


data_purifier = StandardDataPurifier()
