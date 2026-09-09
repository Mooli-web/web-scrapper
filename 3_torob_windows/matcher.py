import re
from typing import Tuple, Set, Optional, Dict

def normalize_text(text: str) -> str:
    """Standardizes Persian & Arabic characters and cleans punctuation."""
    if not text:
        return ""
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه")
    text = re.sub(r"[۰-۹]", lambda m: str("۰۱۲۳۴۵۶۷۸۹".index(m.group(0))), text)
    text = re.sub(r"[^\w\s\d]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text

# Noise words to strip during fuzzy comparison
NOISE_WORDS = {
    "گوشی", "موبایل", "مدل", "ظرفیت", "گیگابایت", "گیگ", "رم", "پک", "اصلی", "گارانتی",
    "شرکتی", "رجیستر", "شده", "رنگ", "خاکستری", "مشکی", "سفید", "طلایی", "آبی", "سبز",
    "نسخه", "گلوبال", "چین", "ویتنام", "هند", "دو", "سیم", "کارت", "حافظه", "داخلی",
    "لپ", "تاپ", "اینچ", "کنسول", "بازی", "ساعت", "هوشمند"
}

def extract_structured_specs(text: str) -> Dict[str, Set[str]]:
    """
    Extracts structured technical specifications separated by category:
    - storage: {128gb, 256gb, 512gb, 1tb}
    - ram: {4gb, 8gb, 16gb, 32gb}
    - region: {ch, za, lla, th}
    - chip_gpu: {m1, m2, m3, rtx4060, i7}
    """
    t = text.lower()
    specs = {
        "storage": set(),
        "ram": set(),
        "region": set(),
        "chip_gpu": set()
    }

    # Storage (e.g. 64gb, 128gb, 256gb, 512gb, 1tb, 2tb)
    storages = re.findall(r"\b(64|128|256|512|1024)\s*(?:gb|گیگ|گیگابایت)\b", t)
    for s in storages:
        specs["storage"].add(f"{s}gb")

    tb_matches = re.findall(r"\b(1|2)\s*(?:tb|ترا|ترابایت)\b", t)
    for tb in tb_matches:
        specs["storage"].add(f"{tb}tb")

    # RAM (e.g. رم 4, رم 8, رم 16, 8gb ram)
    ram_matches = re.findall(r"(?:رم|ram)\s*(\d{1,2})\b|\b(\d{1,2})\s*(?:gb|گیگ)\s*رم\b", t)
    for r1, r2 in ram_matches:
        val = r1 or r2
        if val:
            specs["ram"].add(f"{val}gb")

    # Part numbers / Region codes (e.g., ch, za, lla, th)
    for code in ["ch/a", "ch", "za/a", "za", "lla", "th/a", "th"]:
        if re.search(rf"\b{code}\b", t):
            specs["region"].add(code.replace("/a", ""))

    # Chipset / GPU (e.g., m1, m2, m3, rtx 4060, rtx 4050, i7, i5)
    gpu_cpu = re.findall(r"\b(m[1-4]|rtx\s*\d{4}|gtx\s*\d{4}|core\s*i[3579]|ryzen\s*[3579])\b", t)
    for g in gpu_cpu:
        specs["chip_gpu"].add(re.sub(r"\s+", "", g))

    return specs

def calculate_similarity(digi_title: str, torob_title: str) -> Tuple[bool, float, str]:
    """
    Multi-stage canonical matcher:
    1. Strict Storage & Technical Spec Validation
    2. Token-level set overlap calculation
    Returns: (is_match, similarity_score_0_to_100, diagnostic_reason)
    """
    digi_norm = normalize_text(digi_title)
    torob_norm = normalize_text(torob_title)

    # 1. Structured Specs Verification
    d_specs = extract_structured_specs(digi_norm)
    t_specs = extract_structured_specs(torob_norm)

    # A. If both have explicit storage specs and they mismatch -> Reject!
    if d_specs["storage"] and t_specs["storage"] and not d_specs["storage"].intersection(t_specs["storage"]):
        return False, 0.0, f"تفاوت ظرفیت حافظه ({d_specs['storage']} در برابر {t_specs['storage']})"

    # B. If both have explicit RAM specs and they mismatch -> Reject!
    if d_specs["ram"] and t_specs["ram"] and not d_specs["ram"].intersection(t_specs["ram"]):
        return False, 0.0, f"تفاوت حافظه رم ({d_specs['ram']} در برابر {t_specs['ram']})"

    # 2. Token overlap analysis
    digi_tokens = set(digi_norm.split()) - NOISE_WORDS
    torob_tokens = set(torob_norm.split()) - NOISE_WORDS

    if not digi_tokens or not torob_tokens:
        return False, 0.0, "عناوین فاقد کلمات کلیدی مشخص هستند."

    intersection = digi_tokens.intersection(torob_tokens)
    union = digi_tokens.union(torob_tokens)

    # Jaccard + Overlap coefficient
    jaccard_score = (len(intersection) / len(union)) * 100.0
    overlap_score = (len(intersection) / min(len(digi_tokens), len(torob_tokens))) * 100.0
    final_score = round((jaccard_score * 0.4) + (overlap_score * 0.6), 1)

    if final_score >= 65.0:
        return True, final_score, f"تطبیق موفق با ضریب شباهت {final_score}٪"
    else:
        return False, final_score, f"ضریب شباهت ناکافی ({final_score}٪ < 65٪)"
