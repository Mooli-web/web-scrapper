import time
import random
import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import requests

from matcher import calculate_similarity, normalize_text, NOISE_WORDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("local.torob_crawler")

TOROB_API_URL = "https://api.torob.com/v4/base-product/search/"
CACHE_FILE = Path(__file__).resolve().parent / "torob_cache.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

class DirectTorobCrawler:
    """
    Clean, Native HTTP Torob Crawler.
    Uses exact standard Torob Next.js query parameters without header conflicts.
    """
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8"
        })
        self.cache: Dict[str, Any] = self._load_cache()
        self.is_running = False
        self.stop_requested = False

        self.telemetry = {
            "status": "idle",
            "products_queried": 0,
            "matches_found": 0,
            "arbitrage_opportunities": 0,
            "errors": 0,
            "latest_log": "موتور مستقیم استعلام ترب آماده به کار است."
        }

    def _load_cache(self) -> Dict[str, Any]:
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")

    def clean_query_term(self, title: str, brand: str = "") -> str:
        """Extracts high-signal search terms from product title."""
        norm = normalize_text(title)
        words = [w for w in norm.split() if w not in NOISE_WORDS]
        # Top 3-4 strongest keywords
        selected = words[:4]
        return " ".join(selected)

    def query_torob_for_product(self, digi_product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Queries Torob API with standard parameters (&q=...&query=...&source=next_desktop).
        """
        pid = str(digi_product.get("product_id"))
        title = digi_product.get("title_fa", "")
        brand = digi_product.get("brand", "")

        # Check local cache first (valid 24 hours)
        cached_entry = self.cache.get(pid)
        if cached_entry and (time.time() - cached_entry.get("timestamp", 0)) < 86400:
            return cached_entry

        query = self.clean_query_term(title, brand)
        if not query:
            return None

        # Organic human pause (3.5s - 6.5s)
        time.sleep(round(random.uniform(3.5, 6.5), 2))

        params = {
            "page": 0,
            "size": 10,
            "sort": "popularity",
            "q": query,
            "query": query,
            "source": "next_desktop"
        }

        try:
            resp = self.session.get(
                TOROB_API_URL,
                params=params,
                timeout=20
            )
            self.telemetry["products_queried"] += 1

            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                
                best_match = None
                best_score = 0.0

                for item in results:
                    t_title = (item.get("name1") or item.get("name2") or "").strip()
                    t_price = int(item.get("price", 0) or 0)
                    
                    if t_price <= 0:
                        continue

                    # Filter used / fake
                    t_lower = t_title.lower()
                    if any(w in t_lower for w in ["کارکرده", "دست دوم", "استوک", "غیر اصل", "های کپی"]):
                        continue

                    is_match, score, reason = calculate_similarity(title, t_title)
                    if is_match and score > best_score:
                        best_score = score
                        best_match = {
                            "torob_title": t_title,
                            "torob_price_toman": t_price,
                            "num_shops": int(item.get("num_shops", 1) or 1),
                            "torob_url": f"https://torob.com{item.get('web_client_absolute_url', '')}",
                            "match_score": score,
                            "match_reason": reason,
                            "timestamp": time.time()
                        }

                if best_match:
                    self.cache[pid] = best_match
                    self._save_cache()
                    self.telemetry["matches_found"] += 1
                    return best_match
                return None

            elif resp.status_code in (490, 429):
                # Temporary rate pause (12s)
                time.sleep(12)
                self.telemetry["errors"] += 1
                return None
            else:
                self.telemetry["errors"] += 1
                return None

        except Exception as e:
            logger.error(f"Error querying Torob for '{query}': {e}")
            self.telemetry["errors"] += 1
            return None
