import time
import random
import logging
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote, urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from bs4 import BeautifulSoup

from crawler.config import (
    ESAM_BASE_URL,
    USER_AGENT,
    CRAWLER_DELAY_SEC,
    CRAWLER_TIMEOUT_SEC,
    MAX_RETRIES,
    HTTP_PROXY,
    HTTPS_PROXY
)

logger = logging.getLogger("esam.adapter")

def clean_persian_digits(text: str) -> str:
    if not text:
        return ""
    persian_to_en = {
        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
        '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }
    for p, e in persian_to_en.items():
        text = text.replace(p, e)
    return text

def parse_persian_price(text: str) -> int:
    """
    Extracts integer Toman price from Persian text (e.g. '۴۲٬۵۰۰٬۰۰۰ تومان' or '1168200000 IRR').
    """
    if not text:
        return 0
    cleaned = clean_persian_digits(str(text))
    cleaned = cleaned.replace("،", "").replace(",", "").replace("٬", "").strip()

    # Check for IRR in Schema.org JSON-LD
    if "IRR" in cleaned or "ریال" in text:
        digits = re.findall(r"\d+", cleaned)
        if digits:
            rial_val = int(digits[0])
            return rial_val // 10  # Convert to Toman

    # Check for تومان
    match = re.search(r"(\d+)\s*(?:تومان|ت|Toman)", cleaned, re.IGNORECASE)
    if match:
        return int(match.group(1))

    digits_list = re.findall(r"\b\d{4,12}\b", cleaned)
    if digits_list:
        return int(digits_list[0])

    return 0

def detect_esam_condition(title: str, desc: str = "") -> str:
    t = f"{title} {desc}".lower()
    if any(w in t for w in ["معیوب", "خراب", "جهت قطعات", "برای قطعات", "روشن نمیشود", "خاموش", "اوراقی"]):
        return "معیوب / جهت قطعات"
    elif any(w in t for w in ["آکبند", "پلمپ", "پلمب", "کاملا نو", "خشک", "استفاده نشده", "جعبه باز نشده"]):
        return "نو (پلمپ/آکبند)"
    elif any(w in t for w in ["در حد نو", "درحد نو", "تمیز", "بدون خط", "بسیار تمیز", "مشابه نو", "کارکرد کم"]):
        return "در حد نو"
    elif any(w in t for w in ["استوک", "گرید a", "اوپن باکس", "open box"]):
        return "استوک گرید A"
    elif any(w in t for w in ["نو"]):
        return "نو"
    else:
        return "دست دوم"

def extract_item_id_from_url(url: str) -> str:
    """Extracts numeric item ID from Esam URL (e.g. /item/24910283/title -> esam_24910283)"""
    if not url:
        return f"esam_rand_{random.randint(1000000, 9999999)}"
    match = re.search(r"/item/(\d+)", url)
    if match:
        return f"esam_{match.group(1)}"
    match2 = re.search(r"/items?/(\d+)", url)
    if match2:
        return f"esam_{match2.group(1)}"
    match3 = re.search(r"\b(\d{7,9})\b", url)
    if match3:
        return f"esam_{match3.group(1)}"
    # Fallback to hash of URL
    return f"esam_{abs(hash(url)) % 100000000}"

class EsamAdapter:
    """
    Dedicated, High-Reliability Scraper for Esam.ir.
    Extracts both Live Auctions (مزایدات لحظه‌ای) and Fixed-Price / Stock Items.
    """
    def __init__(self, delay_sec: float = CRAWLER_DELAY_SEC):
        self.delay_sec = delay_sec
        self.session = requests.Session()
        
        # Setup retries
        retries = Retry(
            total=MAX_RETRIES,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Setup proxy if provided
        proxies = {}
        if HTTP_PROXY:
            proxies["http"] = HTTP_PROXY
        if HTTPS_PROXY:
            proxies["https"] = HTTPS_PROXY
        if proxies:
            self.session.proxies = proxies

        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://esam.ir/",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        })

    def _get_page_html(self, url: str) -> Tuple[int, str]:
        t0 = time.perf_counter()
        try:
            resp = self.session.get(url, timeout=CRAWLER_TIMEOUT_SEC)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            if resp.status_code == 200:
                return 200, resp.text
            else:
                logger.warning(f"Esam returned HTTP {resp.status_code} for {url} ({latency_ms}ms)")
                return resp.status_code, ""
        except Exception as e:
            logger.error(f"Esam fetch failed for {url}: {e}")
            return 0, ""

    def parse_items_from_html(self, html: str, category_key: str = "general", category_name: str = "") -> List[Dict[str, Any]]:
        """
        Extracts item listings from Esam HTML page:
        1. JSON-LD schema (Schema.org / Product / ItemList)
        2. HTML product/auction cards
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items: List[Dict[str, Any]] = []
        seen_ids = set()

        # Method 1: Check JSON-LD embedded data
        try:
            for script in soup.find_all("script", type="application/ld+json"):
                if not script.string:
                    continue
                try:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        entries = data
                    else:
                        entries = [data]

                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        
                        # Check Schema.org Product
                        item_type = entry.get("@type", "")
                        if item_type == "Product" or "offers" in entry or "web_info" in entry:
                            title = entry.get("name") or entry.get("title") or ""
                            if not title:
                                continue
                            
                            url = entry.get("url") or ""
                            if url and not url.startswith("http"):
                                url = urljoin(ESAM_BASE_URL, url)

                            item_id = extract_item_id_from_url(url)
                            if item_id in seen_ids:
                                continue

                            offers = entry.get("offers", {})
                            price_val = 0
                            if isinstance(offers, dict):
                                raw_p = offers.get("price", 0)
                                curr = offers.get("priceCurrency", "IRR")
                                if curr == "IRR":
                                    price_val = int(raw_p) // 10
                                else:
                                    price_val = parse_persian_price(str(raw_p))

                            condition_schema = ""
                            if isinstance(offers, dict) and "itemCondition" in offers:
                                cond_url = str(offers.get("itemCondition", ""))
                                if "NewCondition" in cond_url:
                                    condition_schema = "نو"
                                elif "UsedCondition" in cond_url:
                                    condition_schema = "دست دوم"

                            condition = condition_schema or detect_esam_condition(title, entry.get("description", ""))
                            img = entry.get("image", "")

                            # NEW: فیلتر هویتی آگهی‌های بی‌ارزش (پیش‌فرض: حالت سایه — فقط آمار)
                            from crawler.junk_filter import filter_item
                            if filter_item(title, price_val, "esam"):
                                continue

                            items.append({
                                "item_id": item_id,
                                "description": str(entry.get("description") or "")[:1500],  # NEW: توضیحات برای تحلیل/AI
                                "title_fa": title.strip(),
                                "category_key": category_key,
                                "category_name_fa": category_name or entry.get("category", "کالای دیجیتال"),
                                "brand": entry.get("brand", {}).get("name", "") if isinstance(entry.get("brand"), dict) else "",
                                "condition": condition,
                                "is_auction": False,
                                "selling_price_toman": price_val,
                                "base_price_toman": price_val,
                                "buy_now_price_toman": price_val,
                                "bids_count": 0,
                                "time_remaining": None,
                                "seller_name": "فروشنده ایسام",
                                "seller_score": "100%",
                                "seller_city": "ایران",
                                "url": url or f"{ESAM_BASE_URL}/search",
                                "image_url": img,
                                "last_updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                            })
                            seen_ids.add(item_id)
                except Exception:
                    pass
        except Exception:
            pass

        # Method 2: Parse HTML Card Elements (.item-card, .card, a[href*="/item/"])
        card_selectors = [
            'div[class*="item-card"]',
            'div[class*="product-card"]',
            'div[class*="auction-card"]',
            'div[class*="item_card"]',
            'article',
            'div[data-item-id]',
            'a[href*="/item/"]'
        ]

        found_cards = []
        for selector in card_selectors:
            cards = soup.select(selector)
            if cards and len(cards) >= 3:
                found_cards = cards
                break

        # Fallback if no specific container: find all links to /item/
        if not found_cards:
            found_cards = soup.find_all("a", href=re.compile(r"/item/\d+"))

        for card in found_cards:
            try:
                # 1. URL & Item ID
                url = ""
                if card.name == "a" and card.get("href"):
                    url = card.get("href")
                else:
                    a_tag = card.find("a", href=re.compile(r"/item/\d+")) or card.find("a", href=True)
                    if a_tag:
                        url = a_tag.get("href", "")

                if not url or "/item/" not in url:
                    continue

                if not url.startswith("http"):
                    url = urljoin(ESAM_BASE_URL, url)

                item_id = extract_item_id_from_url(url)
                if item_id in seen_ids:
                    continue

                # 2. Title
                title = ""
                title_elem = card.find(["h2", "h3", "h4", "span", "p"], class_=re.compile(r"title|name|subject", re.I))
                if title_elem:
                    title = title_elem.get_text(strip=True)
                else:
                    # Look for alt text on img or text in link
                    img_tag = card.find("img")
                    if img_tag and img_tag.get("alt"):
                        title = img_tag.get("alt", "").strip()
                    elif card.name == "a":
                        title = card.get_text(strip=True)

                if not title or len(title) < 3 or "ایسام" == title:
                    continue

                # 3. Price & Bids & Auction Detection
                card_text = card.get_text(" ", strip=True)
                
                is_auction = any(w in card_text for w in ["مزایده", "پیشنهاد", "پایان", "بالاترین پیشنهاد", "قیمت پایه"])
                
                # Prices
                highest_bid = 0
                base_price = 0
                selling_price = 0

                # Match "بالاترین پیشنهاد: ۲۵٬۰۰۰ تومان"
                bid_match = re.search(r"بالاترین پیشنهاد:?\s*([\d۰-۹٬,]+)\s*(?:تومان|ت)", card_text)
                if bid_match:
                    highest_bid = parse_persian_price(bid_match.group(1))

                # Match "قیمت پایه: ۱٬۶۰۰٬۰۰۰ تومان"
                base_match = re.search(r"قیمت پایه:?\s*([\d۰-۹٬,]+)\s*(?:تومان|ت)", card_text)
                if base_match:
                    base_price = parse_persian_price(base_match.group(1))

                # Regular price
                selling_price = highest_bid or parse_persian_price(card_text) or base_price

                # 4. Bids Count
                bids_count = 0
                bids_match = re.search(r"پیشنهاد\s*(\d+|[۰-۹]+)", card_text)
                if bids_match:
                    try:
                        bids_count = int(clean_persian_digits(bids_match.group(1)))
                    except ValueError:
                        bids_count = 1
                elif "پیشنهاد" in card_text and is_auction:
                    bids_count = 1

                # 5. Time Remaining / Countdown
                time_remaining = None
                time_match = re.search(r"(\d{2}:\s*\d{2}:\s*\d{2}(?::\s*\d{2})?)", clean_persian_digits(card_text))
                if time_match:
                    time_remaining = time_match.group(1).replace(" ", "")
                elif any(w in card_text for w in ["ساعت", "روز", "دقیقه"]):
                    time_phrase = re.search(r"(\d+\s*(?:روز|ساعت|دقیقه)(?:\s*و\s*\d+\s*(?:ساعت|دقیقه))?)", clean_persian_digits(card_text))
                    if time_phrase:
                        time_remaining = time_phrase.group(1)

                # 6. Condition
                condition = detect_esam_condition(title, card_text)

                # 7. Image
                img_url = ""
                img_tag = card.find("img")
                if img_tag:
                    img_url = img_tag.get("data-src") or img_tag.get("src") or ""
                    if img_url and not img_url.startswith("http"):
                        img_url = urljoin(ESAM_BASE_URL, img_url)

                # 8. Seller Name / Score
                seller_name = "فروشنده معتبر ایسام"
                seller_elem = card.find(class_=re.compile(r"seller|user|shop", re.I))
                if seller_elem:
                    seller_name = seller_elem.get_text(strip=True)

                items.append({
                    "item_id": item_id,
                    "title_fa": title,
                    "category_key": category_key,
                    "category_name_fa": category_name or "کالای دیجیتال",
                    "brand": "",
                    "condition": condition,
                    "is_auction": is_auction,
                    "selling_price_toman": selling_price,
                    "base_price_toman": base_price or selling_price,
                    "buy_now_price_toman": selling_price if not is_auction else 0,
                    "bids_count": bids_count,
                    "time_remaining": time_remaining,
                    "seller_name": seller_name,
                    "seller_score": "100%",
                    "seller_city": "ایران",
                    "url": url,
                    "image_url": img_url,
                    "last_updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                seen_ids.add(item_id)
            except Exception as e:
                logger.debug(f"Card parse skipped: {e}")

        return items

    def fetch_category_items(self, query_slug: str, page: int = 1, category_key: str = "general", category_name: str = "") -> List[Dict[str, Any]]:
        """
        Fetches items from a category or search query with pagination.
        Handles both search paths: e.g. search/laptop?cc=40100&p=1 or auctions?activeTab=TowardTheEnd&p=1
        """
        separator = "&" if "?" in query_slug else "?"
        url = f"{ESAM_BASE_URL}/{query_slug}{separator}p={page}"
        
        status, html = self._get_page_html(url)
        if status == 200 and html:
            items = self.parse_items_from_html(html, category_key=category_key, category_name=category_name)
            logger.info(f"Esam [{category_name or category_key}] Page {page}: Parsed {len(items)} genuine items.")
            return items
        return []

    def fetch_hot_auctions(self, page: int = 1) -> List[Dict[str, Any]]:
        """Fetches auctions ending soon and with active bids."""
        return self.fetch_category_items(
            query_slug="auctions?activeTab=TowardTheEnd",
            page=page,
            category_key="auctions_ending",
            category_name="مزایدات داغ رو به اتمام"
        )
