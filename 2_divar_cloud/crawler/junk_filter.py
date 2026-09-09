# -*- coding: utf-8 -*-
"""
🧹 Junk Filter — فیلتر هویتی آگهی‌های بی‌ارزش در لحظه‌ی کشف (سمت خزنده)
=========================================================================
قانون طلایی: این فیلتر «فقط» قوانین هویتیِ با خطای نزدیک به صفر دارد —
قوانین قیمتی/آماری (کف قیمت دسته، انحراف از مرجع) عمداً اینجا نیستند چون به
زمینه‌ی بازار نیاز دارند و در هاب مرکزی اجرا می‌شوند.

سه تور ایمندی:
  ۱. اولویت واژه‌ی دستگاه: اگر عنوان با «گوشی/لپ‌تاپ/کنسول/...» شروع شود
     هرگز حذف نمی‌شود — حتی اگر قیمتش عجیب باشد.
  ۲. حالت سایه (پیش‌فرض): JUNK_FILTER_MODE=shadow → فقط آمار و لاگ می‌گیرد،
     چیزی حذف نمی‌کند تا اول با چشم خودت نمونه‌اش را ببینی. برای فعال‌سازی:
     JUNK_FILTER_MODE=active   (در Environment سرویس Render) و برای خاموشی: off
  ۳. لاگ حذف: هر حذف/کاندیدا با عنوان و دلیل ثبت می‌شود و از
     GET /api/junk-filter/stats قابل بازبینی است — حذفِ نامرئی ممنوع.
"""

import os
import re
import threading
from collections import deque
from typing import Optional, Dict, Any, List

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# واژه‌های آغازینِ دستگاه — اگر عنوان با این‌ها شروع شود، هرگز حذف نکن
DEVICE_FIRST_WORDS = {
    'گوشی', 'موبایل', 'آیفون', 'ایفون', 'تابلت', 'آیپد', 'لپ', 'لپتاپ', 'نوت',
    'مک', 'کنسول', 'پلی', 'ایکس', 'نینتندو', 'کارت', 'ساعت', 'مچ', 'هدفون',
    'هدست', 'ایرباد', 'ایرپاد', 'هندزفری', 'مانیتور', 'سیستم', 'رایانه',
    'کامپیوتر', 'دسکتاپ', 'سرفیس', 'هارد', 'مادربرد', 'رم', 'پردازنده',
    'حافظه', 'رافیک', 'ریگ', 'کیندل', 'کتاب',
}

# واژه‌های آغازینِ کالای جانبی/بی‌ارزش (هویتی)
LEADING_JUNK_NOUNS = {
    'قاب', 'گلس', 'کاور', 'بند', 'کیف', 'کابل', 'شارژر', 'پایه', 'استند', 'هولدر',
    'رینگ', 'فیش', 'باتری', 'باطری', 'روکش', 'استیکر', 'برچسب', 'مبدل', 'هاب',
    'کارتخوان', 'ماوس', 'موس', 'کیبورد', 'صفحه', 'دسته', 'قلم', 'محافظ', 'گارد',
    'شیشه', 'پاوربانک', 'اسپلیتر', 'تبدیل', 'تریپاد', 'لنز', 'میکروفون', 'پوسته',
    'کلاهک', 'عینک', 'سنجاق', 'آویز', 'گردنبند', 'انگشتر', 'دستبند', 'پاکت',
    'اسکناس', 'سکه', 'تمبر', 'شیت', 'سایز', 'خرد', 'فیلم', 'گلدان', 'تابلو',
    'فرش', 'قالی', 'ماشین', 'لوازم', 'قطعه', 'فن', 'کولر', 'پمپ', 'دستگاه',
}
# استثناها: شروع‌های جانبی‌نما ولی دستگاه اصلی
LEADING_EXCEPTIONS = re.compile(
    r'^(?:کارت\s*گرافیک|کارت\s*صدا|کارت\s*ورد|دستگاه\s*(?:پخش|حاصل|کافی|باریستا))', re.I
)

# کلیدواژه‌های هویتیِ قطعی (داخل عنوان)
JUNK_IDENTITY_PATTERNS = [
    (re.compile(r'فقط\s*(?:کارتن|جعبه|پوکه)|کارتن\s*خالی|جعبه\s*خالی|پوکه\s*\S*'), 'جعبه/کارتن خالی'),
    (re.compile(r'^(?:خرید|خریدار|معاوضه)\b|(?<!قابل\s)معاوضه\s|\(\s*خرید\s*\)|پرداخت\s*آنی'), 'آگهی خرید/معاوضه'),
    (re.compile(r'گیفت\s*(?:کارت|کد)|اشتراک\s*\S+|اکانت\s*(?:قانونی|ظرفیتی)|کیف\s*پول'), 'کالای مجازی/اشتراک'),
    (re.compile(r'جهت\s*قطعات|برای\s*قطعات|اوراقی|برد\s*سوخته|روشن\s*نمی'), 'قطعه/معیوب'),
]

# قیمت‌های صوریِ قطعی
FAKE_PRICE_PATTERNS = [
    re.compile(r'^(1{4,}|2{4,}|3{4,}|4{4,}|5{5,}|6{5,}|7{5,}|8{5,}|9{4,})$'),
    re.compile(r'^(1234|12345|123456|1234567|12345678|123456789)$'),
    re.compile(r'^(987654|654321)$'),
]
MIN_REAL_PRICE = 50_000  # هیچ کالای اصلی‌ای زیر ۵۰ هزار تومان نیست


def _normalize(title: str) -> str:
    t = str(title or "").translate(_PERSIAN_DIGITS)
    t = t.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    t = re.sub(r"([\u0600-\u06FF])([a-zA-Z0-9])", r"\1 \2", t)
    t = re.sub(r"([a-zA-Z0-9])([\u0600-\u06FF])", r"\1 \2", t)
    return re.sub(r"\s+", " ", t).strip().lower()


# FIX: نشانه‌های «سیستم کامل» — اگر در عنوان باشد، حتی با کلمه‌ی آغازینِ قطعه
# (کارت/رم/پردازنده...) هرگز حذف نمی‌شود و به دسته‌بندی هاب سپرده می‌شود.
COMPLETE_SYSTEM_RE = re.compile(
    r"سیستم\s*(گیم|رندر|حرفه|آماده|سرهم)|کیس\s*(گیم|آماده|سرهم|\+)|\bریگ\b|ماینر|کامل\s*(مونتاژ|سمبل)", re.I)


def should_drop(title: str, price: int) -> Optional[str]:
    """اگر آگهی «بی‌ارزشِ قطعی» باشد دلیلش را برمی‌گرداند، وگرنه None."""
    t = _normalize(title)
    if not t or len(t) < 3:
        return None
    # ۱) الگوهای هویتیِ قطعی حتی برای سیستم‌ها هم جواب می‌دهند:
    # آگهی خرید/معاوضه یا کارتنِ خالیِ سیستم هم چرت است.
    for pat, reason in JUNK_IDENTITY_PATTERNS:
        if pat.search(t):
            return reason
    # ۲) سیستم کامل فروشی — هرگز حذف نشود (به دسته‌بندی هاب سپرده می‌شود)
    if COMPLETE_SYSTEM_RE.search(t):
        return None
    first = t.split(" ", 1)[0]

    # تور ایمنی ۱: اولویت واژه‌ی دستگاه — هرگز حذف نکن
    if first in DEVICE_FIRST_WORDS:
        return None
    # استثناهای دستگاه اصلی
    if LEADING_EXCEPTIONS.match(t):
        return None

    # قیمت صوریِ قطعی
    try:
        p = int(price or 0)
    except (TypeError, ValueError):
        p = 0
    if 0 < p < MIN_REAL_PRICE:
        return f"قیمت زیر {MIN_REAL_PRICE:,} تومان"
    p_str = str(p)
    if any(pat.match(p_str) for pat in FAKE_PRICE_PATTERNS):
        return "قیمت صوری (الگوی تکراری/ترتیبی)"

    # اسم آغازین جانبی
    if first in LEADING_JUNK_NOUNS:
        return f"شروع با «{first}» (کالای جانبی/غیرمرتبط)"

    return None


# ---------------------------------------------------------------------------
# لاگ و آمار (در حافظه — سرویس رایگان Render دیسک پایدار ندارد)
# ---------------------------------------------------------------------------
class JunkFilterStats:
    def __init__(self, capacity: int = 400):
        self._lock = threading.Lock()
        self.mode = (os.getenv("JUNK_FILTER_MODE", "shadow").strip().lower() or "shadow")
        if self.mode not in ("shadow", "active", "off"):
            self.mode = "shadow"
        self.dropped = deque(maxlen=capacity)
        self.counters = {"candidates": 0, "dropped": 0, "passed": 0}

    def is_active(self) -> bool:
        return self.mode == "active"

    def record(self, title: str, price: int, reason: str, source: str) -> bool:
        """True یعنی در حالت active واقعاً حذف شود."""
        with self._lock:
            if self.mode == "off":
                self.counters["passed"] += 1
                return False
            self.counters["candidates"] += 1
            self.dropped.append({
                "title": str(title)[:120], "price_toman": int(price or 0),
                "reason": reason, "source": source,
            })
            if self.mode == "active":
                self.counters["dropped"] += 1
                return True
            self.counters["passed"] += 1
            return False

    def set_mode(self, mode: str) -> bool:
        mode = (mode or "").strip().lower()
        if mode not in ("shadow", "active", "off"):
            return False
        with self._lock:
            self.mode = mode
        return True

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            recent = list(self.dropped)[-30:][::-1]
            reasons: Dict[str, int] = {}
            for d in self.dropped:
                reasons[d["reason"]] = reasons.get(d["reason"], 0) + 1
            top_reasons = sorted(reasons.items(), key=lambda x: -x[1])[:10]
            return {
                "mode": self.mode,
                "counters": dict(self.counters),
                "top_reasons": [{"reason": r, "count": c} for r, c in top_reasons],
                "recent_candidates": recent,
                "note": "shadow = فقط آمار (چیزی حذف نمی‌شود) | active = حذف واقعی در لحظه‌ی کشف",
            }


junk_filter = JunkFilterStats()


def filter_item(title: str, price: int, source: str) -> bool:
    """
    تابع اصلی برای آداپترها: True = این آیتم را ذخیره نکن.
    در حالت shadow فقط لاگ می‌گیرد و False برمی‌گرداند.
    """
    reason = should_drop(title, price)
    if reason is None:
        return False
    return junk_filter.record(title, price, reason, source)
