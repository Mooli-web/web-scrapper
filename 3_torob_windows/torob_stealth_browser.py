import time
import random
import logging
import json
import re
from urllib.parse import quote
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from matcher import calculate_similarity, normalize_text, NOISE_WORDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("local.stealth_browser")

CACHE_FILE = Path(__file__).resolve().parent / "torob_cache.json"

STEALTH_JS = """
// Overwrite navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Mock Chrome runtime
window.chrome = {
    app: { isInstalled: false },
    runtime: {
        OnInstalledReason: { INSTALL: "install" },
        PlatformArch: { X86_64: "x86-64" },
        PlatformNaclArch: { X86_64: "x86-64" },
        PlatformOs: { WIN: "win" },
        RequestUpdateCheckStatus: { NO_UPDATE: "no_update" }
    }
};

// Mock realistic languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['fa-IR', 'fa', 'en-US', 'en']
});
"""

def parse_persian_price(price_str: str) -> int:
    """Extracts integer toman price from Persian text."""
    if not price_str:
        return 0
    p_str = price_str.replace("،", "").replace(",", "")
    p_str = re.sub(r"[۰-۹]", lambda m: str("۰۱۲۳۴۵۶۷۸۹".index(m.group(0))), p_str)
    digits = re.findall(r"\d+", p_str)
    if digits:
        return int("".join(digits))
    return 0

class PlaywrightTorobScraper:
    """
    Playwright Stealth Browser configured to eliminate Windows NetworkServiceSandbox socket blocks.
    """
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.cache: Dict[str, Any] = self._load_cache()

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

    def start_browser(self):
        """Initializes browser with NetworkServiceSandbox disabled to solve ERR_NETWORK_ACCESS_DENIED."""
        if self.browser:
            return

        from playwright.sync_api import sync_playwright
        logger.info("Launching System Browser Engine (Microsoft Edge / Chrome)...")
        self.playwright = sync_playwright().start()

        # Flags that completely resolve Windows ERR_NETWORK_ACCESS_DENIED:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=NetworkServiceSandbox,IsolateOrigins,site-per-process",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--ignore-certificate-errors",
            "--no-default-browser-check",
            "--no-first-run",
            "--window-size=1366,768"
        ]

        launched = False
        for channel_name in ["msedge", "chrome", None]:
            try:
                if channel_name:
                    logger.info(f"Attempting launch with channel: {channel_name}")
                    self.browser = self.playwright.chromium.launch(
                        channel=channel_name,
                        headless=self.headless,
                        args=launch_args
                    )
                else:
                    logger.info("Attempting launch with bundled Chromium...")
                    self.browser = self.playwright.chromium.launch(
                        headless=self.headless,
                        args=launch_args
                    )
                launched = True
                logger.info(f"Successfully launched browser (channel: {channel_name or 'bundled'}).")
                break
            except Exception as ex:
                logger.warning(f"Could not launch with channel {channel_name}: {ex}")

        if not launched or not self.browser:
            raise RuntimeError("امکان راه‌اندازی مرورگر در ویندوز فراهم نشد.")

        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
            viewport={"width": 1366, "height": 768},
            locale="fa-IR",
            timezone_id="Asia/Tehran",
            ignore_https_errors=True,
            bypass_csp=True
        )
        self.context.add_init_script(STEALTH_JS)
        self.page = self.context.new_page()
        logger.info("Playwright Stealth Browser is active with Network Sandbox Bypass.")

    def close_browser(self):
        """Safely terminates browser instance."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    def clean_query_term(self, title: str) -> str:
        """Extracts concise clean search keywords from full Digikala title."""
        norm = normalize_text(title)
        words = [w for w in norm.split() if w not in NOISE_WORDS]
        return " ".join(words[:4])

    def search_torob_product(self, digi_product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Executes stealth search in real browser for target product.
        """
        pid = str(digi_product.get("product_id"))
        title = digi_product.get("title_fa", "")

        cached = self.cache.get(pid)
        if cached and (time.time() - cached.get("timestamp", 0)) < 86400:
            return cached

        self.start_browser()

        query = self.clean_query_term(title)
        if not query:
            return None

        # Organic human pause (2.5s - 4.5s)
        time.sleep(round(random.uniform(2.5, 4.5), 2))

        captured_api_results: List[Dict[str, Any]] = []

        def on_response(response):
            if "base-product/search" in response.url and response.status == 200:
                try:
                    data = response.json()
                    results = data.get("results", [])
                    if results:
                        captured_api_results.extend(results)
                except Exception:
                    pass

        self.page.on("response", on_response)

        try:
            search_url = f"https://torob.com/search/?query={quote(query)}"
            logger.info(f"Opening stealth page for: {query}")
            self.page.goto(search_url, wait_until="domcontentloaded", timeout=25000)

            time.sleep(round(random.uniform(2.0, 3.5), 2))

            extracted_items = []

            # 1. First priority: Check captured API data
            if captured_api_results:
                for item in captured_api_results:
                    t_title = (item.get("name1") or item.get("name2") or "").strip()
                    t_price = int(item.get("price", 0) or 0)
                    if t_price > 0:
                        extracted_items.append({
                            "title": t_title,
                            "price": t_price,
                            "shops": int(item.get("num_shops", 1) or 1),
                            "url": f"https://torob.com{item.get('web_client_absolute_url', '')}"
                        })

            # 2. Fallback: Extract from DOM directly
            if not extracted_items:
                cards = self.page.query_selector_all("div[class*='productCard'], div[class*='ProductCard'], a[class*='product']")
                for card in cards[:6]:
                    try:
                        card_title = card.inner_text().split("\n")[0].strip()
                        card_link = card.get_attribute("href") or ""
                        price_match = re.search(r"([\d,،۰-۹]+)\s*تومان", card.inner_text())
                        if price_match:
                            t_price = parse_persian_price(price_match.group(1))
                            if t_price > 0:
                                extracted_items.append({
                                    "title": card_title,
                                    "price": t_price,
                                    "shops": 1,
                                    "url": card_link if card_link.startswith("http") else f"https://torob.com{card_link}"
                                })
                    except Exception:
                        continue

            # 3. Match against Digikala Product
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
                return best_match

        except Exception as e:
            logger.error(f"Playwright error during search: {e}")
        finally:
            try:
                self.page.remove_listener("response", on_response)
            except Exception:
                pass

        return None
