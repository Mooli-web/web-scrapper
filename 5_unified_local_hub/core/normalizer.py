import re
import hashlib
from typing import Dict, Any, Tuple, Optional

PERSIAN_TO_ENGLISH_DIGITS = {
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
}

BRANDS_MAP = {
    'اپل': 'apple', 'apple': 'apple', 'iphone': 'apple', 'آیفون': 'apple', 'ایفون': 'apple', 'مک بوک': 'apple', 'macbook': 'apple', 'ipad': 'apple', 'ایپد': 'apple',
    'سامسونگ': 'samsung', 'samsung': 'samsung', 'galaxy': 'samsung', 'گلکسی': 'samsung',
    'شیائومی': 'xiaomi', 'xiaomi': 'xiaomi', 'redmi': 'xiaomi', 'ردمی': 'xiaomi', 'poco': 'xiaomi', 'پوکو': 'xiaomi',
    'سونی': 'sony', 'sony': 'sony', 'playstation': 'sony', 'ps5': 'sony', 'ps4': 'sony', 'پلی استیشن': 'sony', 'پلی‌استیشن': 'sony',
    'مایکروسافت': 'microsoft', 'microsoft': 'microsoft', 'xbox': 'microsoft', 'ایکس باکس': 'microsoft', 'surface': 'microsoft', 'سرفیس': 'microsoft',
    'ایسوس': 'asus', 'asus': 'asus', 'rog': 'asus', 'tuf': 'asus', 'vivobook': 'asus', 'zenbook': 'asus',
    'لنوو': 'lenovo', 'lenovo': 'lenovo', 'legion': 'lenovo', 'thinkpad': 'lenovo', 'ideapad': 'lenovo',
    'اچ پی': 'hp', 'hp': 'hp', 'victus': 'hp', 'omen': 'hp', 'pavilion': 'hp',
    'دل': 'dell', 'dell': 'dell', 'alienware': 'dell', 'vostro': 'dell', 'latitude': 'dell',
    'نینتندو': 'nintendo', 'nintendo': 'nintendo', 'switch': 'nintendo',
    'انویدیا': 'nvidia', 'nvidia': 'nvidia', 'geforce': 'nvidia', 'rtx': 'nvidia', 'gtx': 'nvidia',
    'اینتل': 'intel', 'intel': 'intel',
    'ای ام دی': 'amd', 'amd': 'amd', 'ryzen': 'amd', 'radeon': 'amd', 'rx': 'amd',
    'جی ال ایکس': 'glx', 'glx': 'glx',
    'لوجیتک': 'logitech', 'logitech': 'logitech',
    'ریزر': 'razer', 'razer': 'razer',
    'کانن': 'canon', 'canon': 'canon'
}

# Pre-compiled word-boundary brand patterns.
# (?<!\w)            -> token must not start in the middle of a word ('دل' in 'مدل' fails)
# (?![a-zA-Z\u0600-\u06FF]) -> token must not end inside a word ('دل' in 'دلار' fails),
#                              but a digit AFTER the token is allowed ('iphone13', 'rtx4060').
_BRAND_RES = [
    (
        re.compile(r'(?<!\w)' + re.escape(token) + r'(?![a-zA-Z\u0600-\u06FF])', re.IGNORECASE),
        standard_brand
    )
    for token, standard_brand in BRANDS_MAP.items()
]

BUNDLE_SPLITTERS = [
    r'\s+به\s*همراه\s+',
    r'\s+همراه\s*با\s+',
    r'\s*\+\s*',
    r'\s+به\s*انضمام\s+',
    r'\s+با\s+(?:۲|2|۳|3|دو|سه)?\s*عدد\s+',
    r'\s+دارای\s+پک\s+',
    r'\s+به\s*همراه\s+هدایا'
]

def split_merged_words(text: str) -> str:
    """Inserts space between merged Persian and English letters/digits (e.g. کیفPS4 -> کیف PS4, دستهps5 -> دسته ps5)."""
    if not text:
        return ""
    t = re.sub(r'([\u0600-\u06FF])([a-zA-Z0-9])', r'\1 \2', text)
    t = re.sub(r'([a-zA-Z0-9])([\u0600-\u06FF])', r'\1 \2', t)
    return t

def clean_persian_text(text: str) -> str:
    if not text:
        return ""
    t = split_merged_words(str(text)).strip()
    t = t.replace('ي', 'ی').replace('ك', 'ک').replace('‌', ' ').replace('\u200c', ' ')
    for p, e in PERSIAN_TO_ENGLISH_DIGITS.items():
        t = t.replace(p, e)
    t = re.sub(r'[\r\n\t]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def extract_primary_product_title(title: str) -> str:
    t = split_merged_words(title)
    for splitter in BUNDLE_SPLITTERS:
        parts = re.split(splitter, t, flags=re.IGNORECASE)
        if len(parts) > 1 and len(parts[0].strip()) > 5:
            return parts[0].strip()
    return t

def normalize_brand(raw_brand: str, fallback: str = 'other') -> str:
    """
    NEW: normalizes the brand string that comes from source APIs.
    FIX: Digikala/Divar sometimes send Persian brands ('سامسونگ', 'اپل') which
    leaked into the brand column — analytics then had BOTH 'samsung' AND
    'سامسونگ'. This maps any Persian/English brand to the standard key,
    and falls back to the detector (or 'other') for garbage/'متفرقه' values.
    """
    if not raw_brand:
        return fallback
    b = clean_persian_text(str(raw_brand)).lower().strip()
    if not b or b in ('متفرقه', ' miscellaneous', 'various', '-'):
        return fallback
    standard = extract_brand(b)
    return standard if standard != 'other' else fallback


def extract_brand(text: str) -> str:
    """
    Word-boundary brand extraction.
    FIX: 'دل' no longer matches inside 'مدل' (which made almost every generic
    product with the word "مدل" get brand=dell). English tokens are also
    protected (e.g. 'hp' inside 'touchpad' no longer matches).
    Digits right after a token are allowed (e.g. 'iphone13', 'rtx4060').
    """
    if not text:
        return "other"
    cleaned = clean_persian_text(text).lower()
    for pattern, standard_brand in _BRAND_RES:
        if pattern.search(cleaned):
            return standard_brand
    return "other"

def extract_storage_and_specs(text: str) -> Dict[str, str]:
    cleaned = text.lower()
    specs = {}

    # Storage
    tb_match = re.search(r'(\d+)\s*(?:ترابایت|ترا|tb)', cleaned)
    if tb_match:
        specs['storage'] = f"{tb_match.group(1)}tb"
    else:
        gb_match = re.search(r'(\b128|\b256|\b512|\b64|\b32)\s*(?:گیگابایت|گیگ|gb)?', cleaned)
        if gb_match:
            specs['storage'] = f"{gb_match.group(1)}gb"

    # RAM
    ram_match = re.search(r'(?:رم|ram)\s*(\d{1,2})|\b(\d{1,2})\s*gb\s*(?:ddr\d|ram)', cleaned)
    if ram_match:
        ram_val = ram_match.group(1) or ram_match.group(2)
        specs['ram'] = f"{ram_val}gb"

    # Customized
    if 'کاستوم' in cleaned or 'custom' in cleaned:
        specs['customized'] = 'custom'

    # Year
    year_match = re.search(r'\b(201[2-9]|202[0-6])\b', cleaned)
    if year_match:
        specs['year'] = year_match.group(1)

    # Apple Silicon Chip
    apple_chip = re.search(r'\b(m[1-4])\s*(pro|max|ultra)?\b', cleaned)
    if apple_chip:
        chip_name = apple_chip.group(1)
        if apple_chip.group(2):
            chip_name += f"_{apple_chip.group(2)}"
        specs['apple_chip'] = chip_name

    # Screen Size
    screen_match = re.search(r'(\b13|\b14|\b15|\b16)\s*(?:اینچ|inch|\")', cleaned)
    if screen_match:
        specs['screen'] = f"{screen_match.group(1)}inch"

    # GPU Model
    gpu_match = re.search(r'(rtx|gtx|rx)\s*(\d{3,4}(?:\s*ti|\s*super|\s*xt)?)', cleaned)
    if gpu_match:
        specs['gpu'] = f"{gpu_match.group(1)}_{gpu_match.group(2).replace(' ', '')}"

    return specs

def generate_canonical_key(title: str, category_hint: str = "") -> Tuple[str, str, str]:
    primary_title = extract_primary_product_title(title)
    cleaned = clean_persian_text(primary_title)
    norm = cleaned.lower()

    norm = re.sub(r'(?:آیفون|ایفون)\s*', 'iphone ', norm)
    norm = re.sub(r'(?:مک\s*بوک|مک‌بوک)\s*', 'macbook ', norm)
    norm = re.sub(r'(?:پلی\s*استیشن|پلی‌استیشن|playstation)\s*5', 'ps5', norm)
    norm = re.sub(r'(?:پلی\s*استیشن|پلی‌استیشن|playstation)\s*4', 'ps4', norm)
    norm = re.sub(r'(?:گلکسی|galaxy)\s*', 'galaxy ', norm)

    # FIX: Persian model suffixes must be normalized to their English forms,
    # otherwise "آیفون 13 پرو مکس" (Divar/Esam) and "iPhone 13 Pro Max"
    # (Digikala/Torob) produced DIFFERENT canonical keys and never matched.
    norm = re.sub(r'پرو\s*مکس', 'pro max', norm)
    norm = re.sub(r'(?<!\w)پرو(?!\w)', 'pro', norm)
    norm = re.sub(r'(?<!\w)پلاس(?!\w)', 'plus', norm)
    norm = re.sub(r'(?<!\w)مینی(?!\w)', 'mini', norm)
    norm = re.sub(r'(?<!\w)الترا(?!\w)', 'ultra', norm)
    norm = re.sub(r'(?<!\w)اس\s*(\d{2,3})(?!\w)', r's\1', norm)      # گلکسی اس ۲۴ -> galaxy s24
    norm = re.sub(r'(?<!\w)نوت(?!\w)', 'note', norm)                  # ردمی نوت ۱۲ -> redmi note 12
    norm = re.sub(r'(?<!\w)ردمی(?!\w)', 'redmi', norm)                # ردمی -> redmi (تطبیق دیوار با ترب)
    norm = re.sub(r'(?<!\w)پوکو(?!\w)', 'poco', norm)                 # پوکو -> poco

    brand = extract_brand(norm)
    specs = extract_storage_and_specs(norm)
    tokens = []

    # 1. MacBook
    if 'macbook' in norm:
        brand = 'apple'
        is_pro = 'pro' in norm or 'پرو' in norm
        is_air = 'air' in norm or 'ایر' in norm
        mb_type = 'macbook_pro' if is_pro else ('macbook_air' if is_air else 'macbook')
        tokens.append(mb_type)

        if specs.get('apple_chip'):
            tokens.append(specs['apple_chip'])
        elif 'intel' in norm or 'core i' in norm or 'i5' in norm or 'i7' in norm:
            tokens.append('intel')
            if specs.get('year'):
                tokens.append(specs['year'])
        elif specs.get('year'):
            tokens.append(specs['year'])

        if specs.get('screen'):
            tokens.append(specs['screen'])
        if specs.get('storage'):
            tokens.append(specs['storage'])

    # 2. iPhone
    elif 'iphone' in norm:
        brand = 'apple'
        iphone_m = re.search(r'iphone\s*(\d{1,2}(?:\s*pro\s*max|\s*pro|\s*plus|\s*mini)?|se\s*(?:2020|2022)?|xs\s*max|xs|xr|x|11|12|13|14|15|16)', norm)
        if iphone_m:
            tokens.append(f"iphone_{iphone_m.group(1).replace(' ', '_')}")
        else:
            tokens.append("iphone")
        if specs.get('storage'):
            tokens.append(specs['storage'])

    # 3. Samsung Galaxy
    elif 'galaxy' in norm or (brand == 'samsung' and re.search(r'\b(s\d{2}|a\d{2}|z\s*fold\d?|z\s*flip\d?)\b', norm)):
        brand = 'samsung'
        sam_m = re.search(r'(s\d{2}(?:\s*ultra|\s*plus|\s*fe)?|a\d{2}|z\s*fold\d?|z\s*flip\d?)', norm)
        if sam_m:
            tokens.append(f"galaxy_{sam_m.group(1).replace(' ', '_')}")
        else:
            tokens.append("galaxy")
        if specs.get('storage'):
            tokens.append(specs['storage'])

    # 4. Xiaomi Redmi / Poco
    elif 'redmi' in norm or 'poco' in norm or brand == 'xiaomi':
        brand = 'xiaomi'
        x_m = re.search(r'(redmi\s*note\s*\d{1,2}\s*(?:pro\s*plus|pro|s)?|redmi\s*\d{1,2}[a-z]?|poco\s*[fxm]\d\s*(?:pro|gt)?)', norm)
        if x_m:
            tokens.append(x_m.group(1).replace(' ', '_'))
        else:
            tokens.append('xiaomi')
        if specs.get('storage'):
            tokens.append(specs['storage'])

    # 5. Consoles
    elif 'ps5' in norm:
        brand = 'sony'
        tokens.append('ps5')
        if 'pro' in norm: tokens.append('pro')
        elif 'slim' in norm or 'اسلیم' in norm: tokens.append('slim')
        elif 'digital' in norm or 'دیجیتال' in norm: tokens.append('digital')
        elif 'fat' in norm or 'فت' in norm: tokens.append('fat')

    elif 'ps4' in norm:
        brand = 'sony'
        tokens.append('ps4')
        if 'pro' in norm or 'پرو' in norm: tokens.append('pro')
        elif 'slim' in norm or 'اسلیم' in norm: tokens.append('slim')

    elif 'xbox' in norm:
        brand = 'microsoft'
        if 'series x' in norm: tokens.append('xbox_series_x')
        elif 'series s' in norm: tokens.append('xbox_series_s')
        elif 'one x' in norm: tokens.append('xbox_one_x')
        elif 'one s' in norm: tokens.append('xbox_one_s')
        else: tokens.append('xbox')

    # 6. Laptops
    elif any(w in norm for w in ['vivobook', 'zenbook', 'tuf', 'rog', 'legion', 'thinkpad', 'ideapad', 'victus', 'omen']):
        model_m = re.search(r'(vivobook\s*(?:pro)?\s*\d{2}|zenbook\s*\d{2}|tuf\s*(?:gaming)?|rog\s*(?:strix|zephyrus)?|legion\s*\d?|thinkpad\s*[a-z]\d{2}|ideapad\s*\d?|victus\s*\d{2}|omen\s*\d{2})', norm)
        if model_m:
            tokens.append(model_m.group(1).replace(' ', '_'))
        if specs.get('customized'):
            tokens.append('custom')
        if specs.get('ram') and int(re.sub(r'\D', '', specs['ram']) or 0) >= 32:
            tokens.append(f"ram{specs['ram']}")
        if specs.get('storage'):
            tokens.append(specs['storage'])

    # 7. GPU
    elif specs.get('gpu'):
        tokens.append(specs['gpu'])
        if specs.get('ram'):
            tokens.append(specs['ram'])

    # 8. Fallback
    if not tokens:
        if specs.get('storage'):
            tokens.append(specs['storage'])
        words = [w for w in re.findall(r'[a-zA-Z0-9]+', norm) if len(w) >= 2 and w not in ['gb', 'tb', 'the', 'for', 'model', 'edition', 'inch', 'case']]
        if words:
            tokens.extend(words[:3])
        else:
            # FIX: hash() is randomized per process -> same product got a different
            # canonical_key on every sync run. md5 is deterministic and stable.
            stable_hash = hashlib.md5(title.strip().lower().encode('utf-8')).hexdigest()[:8]
            tokens.append(f"item_{stable_hash}")

    canonical_key = f"{brand}_{'_'.join(tokens)}"
    canonical_key = re.sub(r'[^a-zA-Z0-9_]', '', canonical_key).strip('_').lower()

    return canonical_key, brand, category_hint or "digital"
