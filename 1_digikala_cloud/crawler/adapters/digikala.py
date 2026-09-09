import time
import random
import logging
from typing import Dict, Any, List, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from crawler.config import (
    DIGIKALA_API_BASE,
    USER_AGENT,
    CRAWLER_DELAY_SEC,
    CRAWLER_TIMEOUT_SEC,
    MAX_RETRIES
)

logger = logging.getLogger("crawler.adapters.digikala")

# Official Digikala API Category Slugs and Filter Keywords
DIGIKALA_CATEGORY_MAP = {
    "electronic-devices": ("electronic-devices", None),
    "mobile-phone": ("mobile-phone", None),
    "mobile-apple": ("mobile-phone", "iphone"),
    "mobile-samsung": ("mobile-phone", "samsung"),
    "mobile-xiaomi": ("mobile-phone", "xiaomi"),
    "laptops": ("notebook-netbook-ultrabook", None),
    "laptop-asus": ("notebook-netbook-ultrabook", "asus"),
    "laptop-apple": ("notebook-netbook-ultrabook", "macbook"),
    "laptop-lenovo": ("notebook-netbook-ultrabook", "lenovo"),
    "gaming-consoles": ("station-gaming-consoles", None),
    "gaming-playstation": ("station-gaming-consoles", "ps5"),
    "gaming-xbox": ("station-gaming-consoles", "xbox"),
    "smart-watches": ("wearable-gadget", None),
    "headphones": ("headphone", None),
    "storage-devices": ("data-storage", None),
    "computer-components": ("computer-parts", None),
    "graphic-cards": ("computer-parts", "کارت گرافیک"),
    "processors": ("computer-parts", "پردازنده"),
    "tablets": ("tablet-ebook-reader", None),
}

class DigikalaAdapter:
    """
    Direct, Production-Grade Adapter for Digikala.
    Features exact mathematical discount calculation and anti-bot jitter.
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
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8",
            "Referer": "https://www.digikala.com/",
            "Origin": "https://www.digikala.com"
        })

    def _wait_jitter(self) -> float:
        """Adds randomized organic jitter delay between requests (1.4s to 2.8s)."""
        jitter = round(random.uniform(1.4, 2.8), 2)
        time.sleep(jitter)
        return jitter

    def probe_connection(self) -> Dict[str, Any]:
        """Runs a live test against Digikala API to verify reachability."""
        t0 = time.perf_counter()
        try:
            url = f"{DIGIKALA_API_BASE}/search/?q=samsung&has_selling_stock=1&page=1"
            resp = self.session.get(url, timeout=4)
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("data", {}).get("products", [])
                return {
                    "status": "connected",
                    "reachable": True,
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "items_found": len(products),
                    "target_url": url
                }
            else:
                return {
                    "status": "error",
                    "reachable": False,
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "error": f"HTTP {resp.status_code}"
                }
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "status": "timeout_or_blocked",
                "reachable": False,
                "latency_ms": latency_ms,
                "error": str(e),
                "hint": "سرورهای دیجی‌کالا ممکن است دسترسی آی‌پی‌های خارجی را مسدود کرده باشند."
            }

    def fetch_category_page(self, category_key: str, page: int = 1, sort: int = 21) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        jitter_used = self._wait_jitter()
        slug, keyword = DIGIKALA_CATEGORY_MAP.get(category_key, (category_key, None))

        params = {
            "has_selling_stock": 1,
            "sort": sort,
            "page": page
        }
        if keyword:
            params["q"] = keyword

        url = f"{DIGIKALA_API_BASE}/categories/{slug}/search/"
        t0 = time.perf_counter()
        telemetry = {
            "url": url,
            "page": page,
            "category": category_key,
            "jitter_sec": jitter_used,
            "status_code": 0,
            "response_time_ms": 0.0,
            "total_pages": 1,
            "total_items": 0,
            "error": None
        }

        try:
            resp = self.session.get(url, params=params, timeout=CRAWLER_TIMEOUT_SEC)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            telemetry["response_time_ms"] = elapsed_ms
            telemetry["status_code"] = resp.status_code

            if resp.status_code == 200:
                data = resp.json()
                pager = data.get("data", {}).get("pager", {})
                telemetry["total_pages"] = int(pager.get("total_pages", 1) or 1)
                telemetry["total_items"] = int(pager.get("total_items", 0) or 0)
                
                products = self.parse_products(data, category_key)
                return products, telemetry

            elif resp.status_code == 404:
                search_url = f"{DIGIKALA_API_BASE}/search/"
                search_params = {"q": keyword or category_key, "has_selling_stock": 1, "sort": sort, "page": page}
                resp_s = self.session.get(search_url, params=search_params, timeout=CRAWLER_TIMEOUT_SEC)
                if resp_s.status_code == 200:
                    data = resp_s.json()
                    pager = data.get("data", {}).get("pager", {})
                    telemetry["total_pages"] = int(pager.get("total_pages", 1) or 1)
                    telemetry["total_items"] = int(pager.get("total_items", 0) or 0)
                    products = self.parse_products(data, category_key)
                    return products, telemetry

            telemetry["error"] = f"HTTP {resp.status_code}"
            return [], telemetry

        except Exception as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            telemetry["response_time_ms"] = elapsed_ms
            telemetry["error"] = str(e)
            return [], telemetry

    def parse_products(self, response_json: Dict[str, Any], category_key: Optional[str] = None) -> List[Dict[str, Any]]:
        extracted = []
        raw_products = []

        if isinstance(response_json, dict):
            if "data" in response_json and isinstance(response_json["data"], dict):
                raw_products = response_json["data"].get("products", [])
            elif "products" in response_json and isinstance(response_json["products"], list):
                raw_products = response_json["products"]

        for item in raw_products:
            try:
                product_id = int(item.get("id"))
                title_fa = (item.get("title_fa") or "").strip()
                if not title_fa:
                    continue

                # Filter out used / refurbished
                title_lower = title_fa.lower()
                if any(tag in title_lower for tag in ("کارکرده", "دست دوم", "استوک", "refurbished", "اوپن باکس")):
                    continue

                # Filter out fake / replica
                if any(tag in title_lower for tag in ("غیر اصل", "های کپی", "طرح اصلی")):
                    continue

                brand_info = item.get("brand") or {}
                if isinstance(brand_info, dict):
                    brand = brand_info.get("title_fa") or brand_info.get("title_en") or "متفرقه"
                else:
                    brand = str(brand_info) or "متفرقه"

                url_str = f"https://www.digikala.com/product/dkp-{product_id}/"

                images_dict = item.get("images", {})
                image_url = ""
                if isinstance(images_dict, dict):
                    main_img = images_dict.get("main", {})
                    if isinstance(main_img, dict) and "url" in main_img:
                        urls = main_img["url"]
                        image_url = urls[0] if isinstance(urls, list) and urls else str(urls)

                variant = item.get("default_variant") or {}
                price_info = variant.get("price") or {}

                # Price conversion: Rials -> Tomans (// 10)
                selling_price_rials = int(price_info.get("selling_price", 0) or 0)
                rrp_price_rials = int(price_info.get("rrp_price", 0) or selling_price_rials)
                
                selling_price_toman = selling_price_rials // 10
                rrp_price_toman = rrp_price_rials // 10

                if selling_price_toman <= 0:
                    continue

                # Calculate true mathematical discount percentage
                discount_percent = float(price_info.get("discount_percent", 0.0) or 0.0)
                if rrp_price_toman > selling_price_toman:
                    calc_disc = round(((rrp_price_toman - selling_price_toman) / rrp_price_toman) * 100.0, 1)
                    discount_percent = max(discount_percent, calc_disc)

                seller_info = variant.get("seller") or {}
                seller_title = seller_info.get("title", "دیجی‌کالا") if isinstance(seller_info, dict) else "دیجی‌کالا"

                is_buyable = variant.get("is_buyable", True)
                available = bool(is_buyable and selling_price_toman > 0)

                extracted.append({
                    "store_key": "digikala",
                    "product_id": product_id,
                    "store_product_id": str(product_id),
                    "title_fa": title_fa,
                    "brand": brand,
                    "url": url_str,
                    "image_url": image_url,
                    "selling_price_toman": selling_price_toman,
                    "rrp_price_toman": rrp_price_toman,
                    "discount_percent": max(0.0, min(95.0, discount_percent)),
                    "seller_name": seller_title,
                    "available": available,
                    "category_key": category_key
                })
            except Exception:
                continue

        return extracted
