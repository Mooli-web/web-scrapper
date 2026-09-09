import time
import random
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from crawler.config import (
    USER_AGENT,
    CRAWLER_DELAY_SEC,
    CRAWLER_TIMEOUT_SEC,
    MAX_RETRIES
)

# NEW: شهرهای قابل خزش (اسلاگ دیوار → نام فارسی) — با env لیست DIVAR_CITIES قابل تغییر است
CITY_NAMES_FA = {
    "tehran": "تهران", "karaj": "کرج", "isfahan": "اصفهان", "mashhad": "مشهد",
    "shiraz": "شیراز", "tabriz": "تبریز", "ahvaz": "اهواز", "qom": "قم",
    "rasht": "رشت", "yazd": "یزد", "kerman": "کرمان", "kish": "کیش",
}


logger = logging.getLogger("divar.adapter")

DIVAR_WEB_BASE = "https://divar.ir/s"

def parse_persian_price(text: str) -> int:
    """Extracts integer Toman price from Persian text (e.g. '۴۲٬۵۰۰٬۰۰۰ تومان')."""
    if not text:
        return 0
    p_str = text.replace("،", "").replace(",", "").replace("٬", "")
    p_str = re.sub(r"[۰-۹]", lambda m: str("۰۱۲۳۴۵۶۷۸۹".index(m.group(0))), p_str)
    
    # Try finding price before تومان
    match = re.search(r"(\d+)\s*(?:تومان|ت)", p_str)
    if match:
        return int(match.group(1))
    
    digits_list = re.findall(r"\b\d{5,12}\b", p_str)
    if digits_list:
        return int(digits_list[0])
    
    return 0

def detect_condition(title: str, desc: str) -> str:
    t = f"{title} {desc}".lower()
    if any(w in t for w in ["آکبند", "نو نو", "پلمپ", "پلمب", "خشک", "استفاده نشده"]):
        return "نو (پلمپ/آکبند)"
    elif any(w in t for w in ["در حد نو", "در حد", "تمیز", "بدون خط", "درحد", "مشابه نو"]):
        return "در حد نو"
    elif any(w in t for w in ["استوک", "open box", "اوپن باکس"]):
        return "استوک گرید A"
    elif any(w in t for w in ["توافقی", "معاوضه"]):
        return "توافقی"
    else:
        return "کارکرده"

class DivarAdapter:
    """
    Direct, 100% Reliable Divar Web Scraper for Render.
    Parses live HTML post cards (.kt-post-card) directly from divar.ir/s/tehran/category.
    """
    def __init__(self, delay_sec: float = CRAWLER_DELAY_SEC):
        self.delay_sec = delay_sec
        self.session = requests.Session()
        
        retries = Retry(
            total=MAX_RETRIES,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8",
            "Referer": "https://divar.ir/"
        })

    def _wait_jitter(self) -> float:
        jitter = round(random.uniform(1.4, 2.8), 2)
        time.sleep(jitter)
        return jitter

    def probe_connection(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        try:
            url = f"{DIVAR_WEB_BASE}/tehran/mobile-phones"
            resp = self.session.get(url, timeout=8)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            if resp.status_code == 200:
                posts = self.parse_html_posts(resp.text)
                return {
                    "status": "connected",
                    "reachable": True,
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "items_found": len(posts),
                    "target_url": url
                }
            else:
                return {"status": "error", "reachable": False, "status_code": resp.status_code, "latency_ms": latency_ms, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {"status": "timeout_or_blocked", "reachable": False, "latency_ms": latency_ms, "error": str(e)}

    def fetch_category_page(
        self,
        slug: str,
        query: str = "",
        city_slug: str = "tehran",
        page: int = 1
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        jitter_used = self._wait_jitter()
        
        query_param = f"?q={quote(query.strip())}" if query and query.strip() else ""
        page_param = f"&page={page}" if query_param else f"?page={page}"
        url = f"{DIVAR_WEB_BASE}/{city_slug}/{slug}{query_param}{page_param}"

        t0 = time.perf_counter()
        telemetry = {
            "url": url,
            "page": page,
            "query": query,
            "slug": slug,
            "city": city_slug,
            "jitter_sec": jitter_used,
            "status_code": 0,
            "response_time_ms": 0.0,
            "total_items": 0,
            "error": None
        }

        try:
            resp = self.session.get(url, timeout=CRAWLER_TIMEOUT_SEC)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            telemetry["response_time_ms"] = elapsed_ms
            telemetry["status_code"] = resp.status_code

            if resp.status_code == 200:
                posts = self.parse_html_posts(resp.text, city_fa=CITY_NAMES_FA.get(city_slug, city_slug))
                telemetry["total_items"] = len(posts)
                return posts, telemetry
            elif resp.status_code == 404:
                fallback_url = f"{DIVAR_WEB_BASE}/{city_slug}/electronic-devices{query_param}{page_param}"
                resp_f = self.session.get(fallback_url, timeout=CRAWLER_TIMEOUT_SEC)
                if resp_f.status_code == 200:
                    posts = self.parse_html_posts(resp_f.text, city_fa=CITY_NAMES_FA.get(city_slug, city_slug))
                    telemetry["total_items"] = len(posts)
                    return posts, telemetry

            telemetry["error"] = f"HTTP {resp.status_code}"
            return [], telemetry

        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            telemetry["response_time_ms"] = elapsed_ms
            telemetry["error"] = str(e)
            return [], telemetry

    def parse_html_posts(self, html_text: str, city_fa: str = "تهران") -> List[Dict[str, Any]]:
        extracted = []
        seen_tokens = set()

        raw_cards = re.findall(r'<a[^>]*href=["\'](/v/[^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.DOTALL)
        if not raw_cards:
            raw_cards = re.findall(r'<article[^>]*>(.*?)</article>', html_text, re.DOTALL)

        for item in raw_cards:
            try:
                if isinstance(item, tuple):
                    href, card_html = item
                else:
                    card_html = item
                    href_match = re.search(r'href=["\'](/v/[^"\']+)["\']', card_html)
                    href = href_match.group(1) if href_match else ""

                if not href or "/v/" not in href:
                    continue

                # Clean token extraction: e.g. /v/گوشی-آیفون/gZ12345/ -> gZ12345
                parts = [p for p in href.strip("/").split("/") if p]
                token = parts[-1] if parts else ""
                token = token.strip()[:100]

                if not token or token in seen_tokens or len(token) < 4:
                    continue

                seen_tokens.add(token)

                title_match = re.search(r'<h2[^>]*>(.*?)</h2>', card_html, re.DOTALL)
                if not title_match:
                    title_match = re.search(r'class=["\'][^"\']*(?:title|kt-post-card__title)[^"\']*["\'][^>]*>(.*?)<', card_html, re.DOTALL)

                if title_match:
                    title_fa = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                else:
                    clean_all = re.sub(r'<[^>]+>', ' ', card_html)
                    clean_all = re.sub(r'\s+', ' ', clean_all).strip()
                    title_fa = clean_all.split('در')[0].strip() if clean_all else ""

                if not title_fa or title_fa == "نیاز به بروزرسانی":
                    continue

                desc_texts = re.findall(r'class=["\'][^"\']*(?:description|kt-post-card__description|kt-post-card__info|bottom)[^"\']*["\'][^>]*>(.*?)<', card_html, re.DOTALL)
                combined_desc = " ".join([re.sub(r'<[^>]+>', '', d).strip() for d in desc_texts])
                if not combined_desc:
                    combined_desc = re.sub(r'<[^>]+>', ' ', card_html)

                price_toman = parse_persian_price(combined_desc)
                condition = detect_condition(title_fa, combined_desc)[:80]

                # NEW: فیلتر هویتی آگهی‌های بی‌ارزش (پیش‌فرض: حالت سایه — فقط آمار)
                from crawler.junk_filter import filter_item
                if filter_item(title_fa, price_toman, "divar"):
                    continue

                img_match = re.search(r'<img[^>]*src=["\'](https?://[^"\']+)["\']', card_html)
                image_url = img_match.group(1) if img_match else ""

                loc_match = re.search(r'در\s+([^<|]+)', combined_desc)
                district = loc_match.group(1).strip() if loc_match else "تهران"

                brand = "متفرقه"
                for b_name in ["اپل", "سامسونگ", "شیائومی", "ایسوس", "لنوو", "سونی", "مایکروسافت", "اینتل", "ای ام دی", "انویدیا", "اچ پی", "ایسر"]:
                    if b_name in title_fa:
                        brand = b_name
                        break

                post_url = f"https://divar.ir{href}" if href.startswith("/") else href

                extracted.append({
                    "token": str(token),
                    "title_fa": title_fa,
                    "brand": str(brand)[:100],
                    "selling_price_toman": price_toman,
                    "condition": str(condition)[:80],
                    "description": combined_desc[:1200],  # NEW: توضیحات آگهی برای تحلیل/AI
                    "city": city_fa,  # NEW: شهر واقعی
                    "district": str(district)[:200],
                    "post_url": post_url,
                    "image_url": image_url
                })
            except Exception:
                continue

        return extracted
