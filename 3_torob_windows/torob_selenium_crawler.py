import time
import random
import logging
import json
import re
import os
import shutil
import platform
from urllib.parse import quote
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

from matcher import calculate_similarity, normalize_text, NOISE_WORDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("local.selenium_crawler")

CACHE_FILE = Path(__file__).resolve().parent / "torob_cache.json"

def get_installed_chrome_version() -> Optional[int]:
    """Detects installed Chrome major version from Windows Registry to prevent driver mismatch."""
    try:
        if platform.system() == "Windows":
            import winreg
            keys = [
                r"Software\Google\Chrome\BLBeacon",
                r"Software\Wow6432Node\Google\Chrome\BLBeacon",
                r"Software\Microsoft\Edge\BLBeacon"
            ]
            for root in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                for key_path in keys:
                    try:
                        k = winreg.OpenKey(root, key_path)
                        v_str, _ = winreg.QueryValueEx(k, "version")
                        major = int(v_str.split(".")[0])
                        logger.info(f"Detected installed Chrome version from registry: {major} ({v_str})")
                        return major
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Note detecting Chrome version: {e}")
    return None

def parse_persian_price(price_str: str) -> int:
    """Extracts integer toman price from Persian text (e.g. 'از ۴۲,۵۰۰,۰۰۰ تومان')."""
    if not price_str:
        return 0
    p_str = price_str.replace("،", "").replace(",", "")
    p_str = re.sub(r"[۰-۹]", lambda m: str("۰۱۲۳۴۵۶۷۸۹".index(m.group(0))), p_str)
    digits = re.findall(r"\d+", p_str)
    if digits:
        return int("".join(digits))
    return 0

class SeleniumTorobCrawler:
    """
    Self-Healing Undetected Selenium Chrome Crawler for Torob.
    Automatically detects and synchronizes Chrome & ChromeDriver versions.
    """
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.cache: Dict[str, Any] = self._load_cache()
        self.is_running = False
        self.stop_requested = False

        self.telemetry = {
            "status": "idle",
            "products_queried": 0,
            "matches_found": 0,
            "arbitrage_opportunities": 0,
            "errors": 0,
            "latest_log": "موتور سلنیوم ضدتشخیص (Undetected Selenium) آماده به کار است."
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

    def _clean_uc_cached_driver(self):
        """Removes cached mismatched chromedriver in AppData/Roaming if needed."""
        try:
            appdata = os.environ.get("APPDATA")
            if appdata:
                uc_dir = Path(appdata) / "undetected_chromedriver"
                if uc_dir.exists():
                    shutil.rmtree(uc_dir, ignore_errors=True)
                    logger.info("Cleaned cached undetected_chromedriver binary.")
        except Exception:
            pass

    def start_driver(self):
        """Initializes Chrome with automatic version detection and self-healing recovery."""
        if self.driver:
            return

        logger.info("Launching Undetected Chrome Driver with automatic version sync...")
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--lang=fa-IR,fa")

        profile_dir = Path(__file__).resolve().parent / "chrome_profile"
        profile_dir.mkdir(exist_ok=True)
        options.add_argument(f"--user-data-dir={str(profile_dir)}")

        detected_ver = get_installed_chrome_version()

        # Attempt 1: Launch with detected version or default
        try:
            if detected_ver:
                logger.info(f"Starting uc.Chrome with version_main={detected_ver}")
                self.driver = uc.Chrome(options=options, version_main=detected_ver)
            else:
                self.driver = uc.Chrome(options=options)
            logger.info("Undetected Chrome successfully launched and connected.")
            return
        except Exception as ex:
            err_str = str(ex)
            logger.warning(f"Initial Chrome launch note: {err_str}")

            # Self-Healing: Extract exact version number from error message (e.g. 'Current browser version is 151...')
            match = re.search(r"Current browser version is (\d+)", err_str)
            target_version = int(match.group(1)) if match else (detected_ver or 151)

            logger.info(f"🔄 Self-Healing triggered: Re-downloading ChromeDriver for exact version {target_version}...")
            self._clean_uc_cached_driver()
            
            try:
                self.driver = uc.Chrome(options=options, version_main=target_version)
                logger.info(f"✅ Undetected Chrome successfully started with synchronized version {target_version}!")
                return
            except Exception as e2:
                logger.error(f"Failed to launch Chrome after self-healing: {e2}")
                raise

    def close_driver(self):
        """Safely quits Chrome."""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None

    def clean_query_term(self, title: str) -> str:
        """Extracts concise clean search keywords from full Digikala title."""
        norm = normalize_text(title)
        words = [w for w in norm.split() if w not in NOISE_WORDS]
        return " ".join(words[:4])

    def query_torob_for_product(self, digi_product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Navigates Chrome directly to Torob search page and extracts product results.
        """
        pid = str(digi_product.get("product_id"))
        title = digi_product.get("title_fa", "")

        # Check local cache (cached within 24h)
        cached_entry = self.cache.get(pid)
        if cached_entry and (time.time() - cached_entry.get("timestamp", 0)) < 86400:
            return cached_entry

        query = self.clean_query_term(title)
        if not query:
            return None

        self.start_driver()

        # Human-like organic pause (3.0s - 6.0s)
        time.sleep(round(random.uniform(3.0, 6.0), 2))

        search_url = f"https://torob.com/search/?query={quote(query)}"
        logger.info(f"Opening Torob search in Chrome: {query}")

        try:
            self.driver.get(search_url)
            self.telemetry["products_queried"] += 1

            time.sleep(round(random.uniform(3.0, 4.5), 2))

            page_source = self.driver.page_source

            if "درخواست‌های مشکوک" in page_source or "کد امنیتی" in page_source:
                logger.warning("Torob Cloudflare/Captcha challenge page detected! Waiting 8s for user/automatic solve...")
                self.telemetry["latest_log"] = "⚠️ چالش امنیتی ترب در پنجره مرورگر نمایش داده شد..."
                time.sleep(8)
                page_source = self.driver.page_source

            extracted_items = []

            # 1. Try extracting from window.__NEXT_DATA__
            try:
                next_data = self.driver.execute_script("return window.__NEXT_DATA__")
                if next_data and isinstance(next_data, dict):
                    page_props = next_data.get("props", {}).get("pageProps", {})
                    results = page_props.get("results", []) or page_props.get("products", [])
                    for item in results:
                        t_title = (item.get("name1") or item.get("name2") or "").strip()
                        t_price = int(item.get("price", 0) or 0)
                        if t_price > 0:
                            extracted_items.append({
                                "title": t_title,
                                "price": t_price,
                                "shops": int(item.get("num_shops", 1) or 1),
                                "url": f"https://torob.com{item.get('web_client_absolute_url', '')}"
                            })
            except Exception:
                pass

            # 2. Fallback: Extract from DOM elements directly
            if not extracted_items:
                product_cards = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='productCard'], div[class*='ProductCard'], a[class*='product']")
                for card in product_cards[:6]:
                    try:
                        text = card.text.strip()
                        card_title = text.split("\n")[0].strip()
                        card_link = card.get_attribute("href") or ""
                        price_match = re.search(r"([\d,،۰-۹]+)\s*تومان", text)
                        if price_match:
                            t_price = parse_persian_price(price_match.group(1))
                            if t_price > 0:
                                extracted_items.append({
                                    "title": card_title,
                                    "price": t_price,
                                    "shops": 1,
                                    "url": card_link
                                })
                    except Exception:
                        continue

            # 3. Match with Digikala product identity
            best_match = None
            best_score = 0.0

            for item in extracted_items:
                t_title = item["title"]
                t_price = item["price"]

                t_lower = t_title.lower()
                if any(w in t_lower for w in ["کارکرده", "دست دوم", "استوک", "غیر اصل", "های کپی"]):
                    continue

                is_match, score, reason = calculate_similarity(title, t_title)
                if is_match and score > best_score:
                    best_score = score
                    best_match = {
                        "torob_title": t_title,
                        "torob_price_toman": t_price,
                        "num_shops": item.get("shops", 1),
                        "torob_url": item.get("url", ""),
                        "match_score": score,
                        "match_reason": reason,
                        "timestamp": time.time()
                    }

            if best_match:
                self.cache[pid] = best_match
                self._save_cache()
                self.telemetry["matches_found"] += 1
                return best_match

        except Exception as e:
            logger.error(f"Selenium error during search for '{query}': {e}")
            self.telemetry["errors"] += 1

        return None
