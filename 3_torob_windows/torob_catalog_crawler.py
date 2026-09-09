import sys
import time
import random
import logging
import json
import re
import os
import platform
from urllib.parse import quote
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

# Python 3.12+ distutils compatibility shim for undetected_chromedriver
try:
    import distutils
except ImportError:
    try:
        import setuptools
        import setuptools._distutils as distutils
        sys.modules["distutils"] = distutils
        sys.modules["distutils.version"] = getattr(distutils, "version", None) or setuptools._distutils.version
    except Exception:
        pass

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("local.torob_catalog")

CACHE_FILE = Path(__file__).resolve().parent / "torob_catalog_db.json"

# Comprehensive 60+ Digital Market Categories & Hardware Matrix on Torob
TOROB_CATEGORIES = [
    # --- 1. MOBILES (گوشی موبایل) ---
    {"key": "mobile-apple-15-16", "name": "گوشی‌های اپل (iPhone 15 / 16)", "query": "آیفون 15 16 iphone"},
    {"key": "mobile-apple-13-14", "name": "گوشی‌های اپل (iPhone 13 / 14)", "query": "آیفون 13 14 iphone"},
    {"key": "mobile-apple-11-12", "name": "گوشی‌های اپل (iPhone 11 / 12 / SE)", "query": "آیفون 11 12 se iphone"},
    {"key": "mobile-samsung-s", "name": "گوشی‌های پرچمدار سامسونگ (S24 / S23 / Ultra)", "query": "سامسونگ s24 s23 ultra"},
    {"key": "mobile-samsung-a", "name": "گوشی‌های میان‌رده سامسونگ (A55 / A35 / A15)", "query": "سامسونگ a55 a35 a25 a15"},
    {"key": "mobile-samsung-fold", "name": "گوشی‌های تاشو سامسونگ (Z Fold / Z Flip)", "query": "سامسونگ z fold z flip"},
    {"key": "mobile-xiaomi-flagship", "name": "گوشی‌های پرچمدار شیائومی (Xiaomi 14 / 13)", "query": "شیائومی xiaomi 14 13t"},
    {"key": "mobile-xiaomi-poco", "name": "گوشی‌های پوکو (Poco X6 / F6 / M6)", "query": "پوکو poco x6 f6 m6"},
    {"key": "mobile-xiaomi-redmi", "name": "گوشی‌های ردمی نوت (Redmi Note 13 / 12)", "query": "ردمی نوت redmi note 13 12"},
    {"key": "mobile-honor", "name": "گوشی‌های آنر (Honor)", "query": "گوشی آنر honor"},
    {"key": "mobile-motorola", "name": "گوشی‌های موتورولا (Motorola)", "query": "گوشی موتورولا motorola"},
    {"key": "mobile-nothing", "name": "گوشی‌های ناتینگ (Nothing Phone)", "query": "ناتینگ فون nothing phone"},

    # --- 2. LAPTOPS & ULTRABOOKS (لپ‌تاپ) ---
    {"key": "laptop-macbook-pro", "name": "مک‌بوک پرو اپل (MacBook Pro M3 / M2)", "query": "مک بوک پرو macbook pro m3 m2"},
    {"key": "laptop-macbook-air", "name": "مک‌بوک ایر اپل (MacBook Air M3 / M2 / M1)", "query": "مک بوک ایر macbook air m3 m2 m1"},
    {"key": "laptop-asus-rog", "name": "لپ‌تاپ‌های گیمینگ ایسوس (ASUS ROG Strix / Zephyrus)", "query": "لپ تاپ ایسوس rog strix zephyrus"},
    {"key": "laptop-asus-tuf", "name": "لپ‌تاپ‌های گیمینگ ایسوس (ASUS TUF Gaming)", "query": "لپ تاپ ایسوس tuf gaming a15 f15"},
    {"key": "laptop-asus-zenbook", "name": "لپ‌تاپ‌های زن‌بوک و ویووبوک ایسوس (ZenBook / VivoBook)", "query": "لپ تاپ ایسوس zenbook vivobook"},
    {"key": "laptop-lenovo-legion", "name": "لپ‌تاپ‌های لنوو لیجن (Lenovo Legion 5 / 7 / Pro)", "query": "لپ تاپ لنوو legion 5 7 pro"},
    {"key": "laptop-lenovo-loq", "name": "لپ‌تاپ‌های لنوو لوک (Lenovo LOQ)", "query": "لپ تاپ لنوو loq"},
    {"key": "laptop-lenovo-ideapad", "name": "لپ‌تاپ‌های آیدیاپد لنوو (IdeaPad / ThinkPad)", "query": "لپ تاپ لنوو ideapad thinkpad"},
    {"key": "laptop-hp-victus", "name": "لپ‌تاپ‌های گیمینگ اچ‌پی (HP Victus / Omen)", "query": "لپ تاپ اچ پی victus omen"},
    {"key": "laptop-acer", "name": "لپ‌تاپ‌های ایسر (Acer Nitro / Predator / Aspire)", "query": "لپ تاپ ایسر nitro predator aspire"},
    {"key": "laptop-msi", "name": "لپ‌تاپ‌های ام‌اس‌آی (MSI Gaming / Katana / Cyborg)", "query": "لپ تاپ msi katana cyborg sword"},

    # --- 3. GRAPHICS CARDS (کارت گرافیک) ---
    {"key": "gpu-rtx-4090-4080", "name": "کارت گرافیک انویدیا (RTX 4090 / 4080 / Super)", "query": "کارت گرافیک rtx 4090 4080 super"},
    {"key": "gpu-rtx-4070", "name": "کارت گرافیک انویدیا (RTX 4070 Ti / 4070 Super)", "query": "کارت گرافیک rtx 4070 ti super"},
    {"key": "gpu-rtx-4060", "name": "کارت گرافیک انویدیا (RTX 4060 Ti / 4060)", "query": "کارت گرافیک rtx 4060 ti"},
    {"key": "gpu-rtx-3060", "name": "کارت گرافیک انویدیا (RTX 3060 / 3050)", "query": "کارت گرافیک rtx 3060 3050"},
    {"key": "gpu-amd-rx", "name": "کارت گرافیک ای‌ام‌دی (AMD Radeon RX 7800 / 7700 / 7600)", "query": "کارت گرافیک rx 7800 7700 7600 xt"},

    # --- 4. PROCESSORS & MOTHERBOARDS (پردازنده و مادربورد) ---
    {"key": "cpu-intel-i9-i7", "name": "پردازنده اینتل (Core i9 / i7 نسل 14 و 13)", "query": "پردازنده اینتل core i9 i7 14700k 13700k"},
    {"key": "cpu-intel-i5-i3", "name": "پردازنده اینتل (Core i5 / i3 نسل 14 و 13)", "query": "پردازنده اینتل core i5 i3 14400 13400"},
    {"key": "cpu-amd-ryzen", "name": "پردازنده ای‌ام‌دی (AMD Ryzen 9 / 7 / 5 سری 7000)", "query": "پردازنده amd ryzen 7800x3d 7700x 7600x"},
    {"key": "motherboard-asus", "name": "مادربرد ایسوس (ASUS Z790 / B760 / B650)", "query": "مادربرد ایسوس z790 b760 b650"},
    {"key": "motherboard-msi-giga", "name": "مادربرد ام‌اس‌آی و گیگابایت (MSI / Gigabyte)", "query": "مادربرد msi gigabyte z790 b760"},

    # --- 5. STORAGE & RAM (حافظه و رم) ---
    {"key": "ssd-samsung-990", "name": "حافظه اس‌اس‌دی سامسونگ (Samsung 990 Pro / 980 Pro)", "query": "اس اس دی سامسونگ 990 pro 980 pro"},
    {"key": "ssd-nvme-1tb-2tb", "name": "حافظه اس‌اس‌دی M.2 NVMe (Crucial / WD / Kingston)", "query": "حافظه ssd nvme m.2 1tb 2tb"},
    {"key": "ram-ddr5-ddr4", "name": "رم کامپیوتر و لپ‌تاپ (DDR5 / DDR4 16GB / 32GB)", "query": "رم ddr5 ddr4 16gb 32gb corsair fury"},
    {"key": "ssd-external", "name": "حافظه اس‌اس‌دی اکسترنال (Samsung T7 / T9 / SanDisk)", "query": "اس اس دی اکسترنال سامسونگ t7 t9"},

    # --- 6. MONITORS & ACCESSORIES (مانیتور و تجهیزات) ---
    {"key": "monitors-gaming-240hz", "name": "مانیتور گیمینگ ۲۴۰ هرتز و ۱۴۴ هرتز (ASUS / BenQ / LG)", "query": "مانیتور گیمینگ 240hz 144hz 165hz asus lg"},
    {"key": "monitors-2k-4k", "name": "مانیتور 4K و 2K (Samsung / Xiaomi / Dell)", "query": "مانیتور 4k 2k samsung xiaomi dell"},

    # --- 7. GAMING CONSOLES (کنسول‌های بازی) ---
    {"key": "ps5-slim-standard", "name": "پلی‌استیشن ۵ (PS5 Slim / Standard)", "query": "پلی استیشن 5 ps5 slim"},
    {"key": "xbox-series-x-s", "name": "ایکس‌باکس سری ایکس و اس (Xbox Series X / S)", "query": "ایکس باکس سری xbox series x s"},
    {"key": "nintendo-switch", "name": "نینتندو سوییچ (Nintendo Switch OLED)", "query": "نینتندو سوییچ nintendo switch oled"},
    {"key": "gamepads-dualsense", "name": "دسته بازی پلی‌استیشن و ایکس‌باکس (DualSense / Xbox)", "query": "دسته بازی dualsense ps5 xbox controller"},
    {"key": "vr-headsets", "name": "هدست واقعیت مجازی (Meta Quest 3 / PS VR2)", "query": "هدست واقعیت مجازی meta quest 3 ps vr2"},

    # --- 8. AUDIO & HEADPHONES (هدفون و هندزفری) ---
    {"key": "airpods-pro", "name": "ایرپادهای اپل (AirPods Pro 2 / AirPods 3)", "query": "ایرپاد اپل airpods pro 2 3"},
    {"key": "galaxy-buds", "name": "گلکسی بادز سامسونگ (Galaxy Buds 3 Pro / 2 Pro / FE)", "query": "گلکسی بادز galaxy buds 3 pro 2 fe"},
    {"key": "headphones-sony", "name": "هدفون و هندزفری سونی (Sony WH-1000XM5 / WF-1000XM5)", "query": "هدفون سونی wh-1000xm5 wf-1000xm5"},
    {"key": "headphones-anker", "name": "هندزفری انکر ساندکور (Anker Soundcore)", "query": "هندزفری انکر soundcore liberty space"},
    {"key": "headphones-qcy", "name": "هندزفری اقتصادی کیو‌سی‌وای (QCY)", "query": "هندزفری qcy t13 melobuds"},

    # --- 9. SMARTWATCHES (ساعت هوشمند) ---
    {"key": "apple-watch-ultra", "name": "اپل واچ اولترا و سری ۹ (Apple Watch Ultra 2 / Series 9)", "query": "اپل واچ apple watch ultra 2 series 9 se"},
    {"key": "galaxy-watch", "name": "گلکسی واچ سامسونگ (Galaxy Watch 7 / Ultra / 6)", "query": "گلکسی واچ galaxy watch 7 ultra 6"},
    {"key": "xiaomi-watch", "name": "ساعت و مچ‌بند شیائومی (Xiaomi Watch / Mi Band 8)", "query": "ساعت شیائومی mi band 8 amazfit"},

    # --- 10. TABLETS (تبلت و سرفیس) ---
    {"key": "ipad-pro-air", "name": "آیپد پرو و ایر اپل (iPad Pro M4 / iPad Air M2)", "query": "آیپد اپل ipad pro m4 air m2"},
    {"key": "ipad-10-mini", "name": "آیپد نسل ۱۰ و مینی (iPad 10th / iPad Mini)", "query": "آیپد ipad 10 mini 6"},
    {"key": "tablet-samsung-tab", "name": "تبلت سامسونگ (Galaxy Tab S9 / Tab A9)", "query": "تبلت سامسونگ galaxy tab s9 a9"},
    {"key": "microsoft-surface", "name": "مایکروسافت سرفیس (Surface Pro 11 / 9 / Laptop)", "query": "سرفیس مایکروسافت surface pro 11 9"},
]

def get_installed_chrome_version() -> Optional[int]:
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
                        return major
                    except Exception:
                        pass
    except Exception:
        pass
    return None

def parse_persian_price(price_str: str) -> int:
    if not price_str:
        return 0
    p_str = price_str.replace("،", "").replace(",", "")
    p_str = re.sub(r"[۰-۹]", lambda m: str("۰۱۲۳۴۵۶۷۸۹".index(m.group(0))), p_str)
    digits = re.findall(r"\d+", p_str)
    if digits:
        return int("".join(digits))
    return 0

class IndependentTorobCrawler:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.catalog: Dict[str, Dict[str, Any]] = self._load_catalog()
        self.is_running = False
        self.stop_requested = False

        self.telemetry = {
            "status": "idle",
            "active_category": None,
            "current_page": 0,
            "total_pages": 0,
            "products_scanned": len(self.catalog),
            "new_products_found": 0,
            "price_changes": 0,
            "latest_log": "موتور مستقل خزش ترب آماده است."
        }

    def _load_catalog(self) -> Dict[str, Dict[str, Any]]:
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_catalog(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.catalog, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error saving catalog: {e}")

    def start_driver(self):
        if self.driver:
            try:
                _ = self.driver.title
                return
            except Exception:
                self.driver = None

        logger.info("Starting Persistent Undetected Chrome Engine...")
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1280,800")
        options.add_argument("--lang=fa-IR,fa")

        profile_dir = Path(__file__).resolve().parent / "chrome_profile"
        profile_dir.mkdir(exist_ok=True)
        options.add_argument(f"--user-data-dir={str(profile_dir)}")

        ver = get_installed_chrome_version() or 151
        try:
            self.driver = uc.Chrome(options=options, version_main=ver)
            logger.info(f"Undetected Chrome active (version {ver}).")
        except Exception as ex:
            logger.warning(f"Fallback driver start: {ex}")
            try:
                self.driver = uc.Chrome(options=options)
            except Exception as e2:
                logger.error(f"Cannot start Chrome: {e2}")
                raise

    def close_driver(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None

    def crawl_category_pages(self, cat_dict: Dict[str, str], max_pages: int = 15, emit_log_fn=None):
        cat_key = cat_dict["key"]
        cat_name = cat_dict["name"]
        query = cat_dict["query"]

        self.telemetry["active_category"] = cat_name
        self.telemetry["total_pages"] = max_pages

        self.start_driver()

        for page_num in range(max_pages):
            if self.stop_requested:
                break

            self.telemetry["current_page"] = page_num + 1
            search_url = f"https://torob.com/search/?query={quote(query)}&page={page_num}"
            
            if emit_log_fn:
                emit_log_fn("INFO", f"🛒 [{cat_name}] صفحه {page_num + 1}/{max_pages}...")

            try:
                self.driver.get(search_url)
                time.sleep(round(random.uniform(3.0, 4.8), 2))

                page_source = self.driver.page_source
                if "درخواست‌های مشکوک" in page_source:
                    if emit_log_fn:
                        emit_log_fn("WARNING", "⚠️ چالش امنیتی ترب نمایش داده شد؛ ۵ ثانیه تامل...")
                    time.sleep(5)
                    page_source = self.driver.page_source

                items_on_page = []

                # 1. From window.__NEXT_DATA__
                try:
                    next_data = self.driver.execute_script("return window.__NEXT_DATA__")
                    if next_data and isinstance(next_data, dict):
                        results = next_data.get("props", {}).get("pageProps", {}).get("results", []) or next_data.get("props", {}).get("pageProps", {}).get("products", [])
                        for r in results:
                            t_name = (r.get("name1") or r.get("name2") or "").strip()
                            t_price = int(r.get("price", 0) or 0)
                            r_key = r.get("random_key") or str(t_name)
                            
                            if t_price <= 0:
                                continue

                            t_lower = t_name.lower()
                            if any(w in t_lower for w in ["کارکرده", "دست دوم", "استوک", "غیر اصل", "های کپی"]):
                                continue

                            img = r.get("image_url") or ""
                            url = f"https://torob.com{r.get('web_client_absolute_url', '')}"
                            shops = int(r.get("num_shops", 1) or 1)

                            items_on_page.append({
                                "key": r_key,
                                "title": t_name,
                                "price": t_price,
                                "num_shops": shops,
                                "image_url": img,
                                "url": url,
                                "category_key": cat_key,
                                "category_name": cat_name,
                                "last_seen_at": datetime.now().strftime("%H:%M:%S")
                            })
                except Exception:
                    pass

                # 2. From DOM elements fallback
                if not items_on_page:
                    cards = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='productCard'], div[class*='ProductCard'], a[class*='product']")
                    for card in cards:
                        try:
                            text = card.text.strip()
                            c_title = text.split("\n")[0].strip()
                            c_link = card.get_attribute("href") or ""
                            price_m = re.search(r"([\d,،۰-۹]+)\s*تومان", text)
                            if price_m:
                                pr = parse_persian_price(price_m.group(1))
                                if pr > 0:
                                    items_on_page.append({
                                        "key": c_link or c_title,
                                        "title": c_title,
                                        "price": pr,
                                        "num_shops": 1,
                                        "image_url": "",
                                        "url": c_link if c_link.startswith("http") else f"https://torob.com{c_link}",
                                        "category_key": cat_key,
                                        "category_name": cat_name,
                                        "last_seen_at": datetime.now().strftime("%H:%M:%S")
                                    })
                        except Exception:
                            continue

                if not items_on_page:
                    if emit_log_fn:
                        emit_log_fn("INFO", f"🏁 پایان نتایج شاخه {cat_name} در صفحه {page_num + 1}. ورود به شاخه بعدی...")
                    break

                page_new = 0
                page_updated = 0
                for item in items_on_page:
                    k = item["key"]
                    if k not in self.catalog:
                        page_new += 1
                        self.telemetry["new_products_found"] += 1
                    else:
                        if self.catalog[k]["price"] != item["price"]:
                            page_updated += 1
                            self.telemetry["price_changes"] += 1
                    
                    self.catalog[k] = item

                self._save_catalog()
                self.telemetry["products_scanned"] = len(self.catalog)

                if emit_log_fn:
                    emit_log_fn("INFO", f"📄 [{cat_name}] صفحه {page_num + 1}: دریافت {len(items_on_page)} کالا (+{page_new} جدید، {page_updated} تغییر قیمت). کل کاتالوگ: {len(self.catalog)} کالا")

            except Exception as e:
                logger.error(f"Error on page {page_num + 1} of {cat_name}: {e}")
                if emit_log_fn:
                    emit_log_fn("ERROR", f"⚠️ خطا در صفحه {page_num + 1}: {e}")
                time.sleep(3)

torob_catalog_engine = IndependentTorobCrawler(headless=False)
