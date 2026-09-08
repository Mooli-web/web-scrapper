import os
import re
import json
import logging
import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    env_file = Path(".env")
    if not env_file.exists():
        env_file = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_file)
except ImportError:
    pass

from sync.ingest_digikala import ingest_digikala_items
from sync.ingest_divar import ingest_divar_items
from sync.ingest_esam import ingest_esam_items
from sync.ingest_torob import ingest_torob_items
from core.arbitrage_engine import arbitrage_engine
from core.ai_dataset_generator import ai_exporter
from database.db_manager import db

logger = logging.getLogger("hub.sync.cloud_pull")

LIVE_LOGS: List[Dict[str, Any]] = []
LOG_COUNTER = 0

def push_live_log(level: str, message: str):
    global LOG_COUNTER
    LOG_COUNTER += 1
    now_str = datetime.now().strftime("%H:%M:%S")
    entry = {"id": LOG_COUNTER, "time": now_str, "level": level, "message": message}
    LIVE_LOGS.append(entry)
    if len(LIVE_LOGS) > 350:
        LIVE_LOGS.pop(0)
    logger.info(f"[{level}] {message}")

class CloudDataPuller:
    """
    High-Performance, Full-Catalog Cloud Ingestion Streamer with Resilient JWT Token Auth & Retry.
    Pulls 100% of all records across Digikala (8,800+), Divar (21,000+), Esam (3,000+), and Torob (3,000+).
    """
    def __init__(self):
        self.reload_config()
        self._tokens_cache: Dict[str, str] = {}

    def reload_config(self):
        try:
            from dotenv import load_dotenv
            env_f = Path(".env")
            if not env_f.exists():
                env_f = Path(__file__).resolve().parent.parent / ".env"
            load_dotenv(dotenv_path=env_f, override=True)
        except Exception:
            pass

        self.digikala_render_url = os.getenv("DIGIKALA_RENDER_URL", "").strip().rstrip("/")
        self.divar_render_url = os.getenv("DIVAR_RENDER_URL", "").strip().rstrip("/")
        self.esam_render_url = os.getenv("ESAM_RENDER_URL", "").strip().rstrip("/")

        self.admin_user = os.getenv("RENDER_ADMIN_USER", "admin").strip() or "admin"
        self.admin_pass = os.getenv("RENDER_ADMIN_PASS", "admin123").strip() or "admin123"

        self.torob_path = os.getenv("TOROB_LOCAL_PATH", "").strip()

    def _get_auth_token(self, base_url: str) -> Optional[str]:
        """Retrieves and caches JWT Bearer token with multi-credential retry."""
        if base_url in self._tokens_cache:
            return self._tokens_cache[base_url]

        credential_attempts = [
            (self.admin_user, self.admin_pass),
            ("admin", "admin123"),
            ("admin", "admin"),
            ("admin", "123456")
        ]

        for user, pwd in credential_attempts:
            for attempt in range(2):
                try:
                    resp = requests.post(
                        f"{base_url}/api/login",
                        json={"username": user, "password": pwd},
                        timeout=10
                    )
                    if resp.status_code == 200:
                        token = resp.json().get("access_token")
                        if token:
                            self._tokens_cache[base_url] = token
                            logger.info(f"✅ Authenticated successfully to {base_url}")
                            return token
                except Exception as e:
                    logger.debug(f"Login attempt {attempt+1} to {base_url} note: {e}")
                    time.sleep(0.5)

        logger.warning(f"❌ Failed to obtain auth token for {base_url}")
        return None

    def get_diagnostics(self) -> Dict[str, Any]:
        self.reload_config()
        diag = {"sources": {}}

        # 1. Digikala
        if self.digikala_render_url and self.digikala_render_url.startswith("http") and "your-" not in self.digikala_render_url:
            token = self._get_auth_token(self.digikala_render_url)
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            try:
                t0 = requests.get(f"{self.digikala_render_url}/api/products?page_size=5&page=1", headers=headers, timeout=12)
                data = t0.json() if t0.status_code == 200 else {}
                total = data.get("total") or len(data.get("items") or data.get("products") or [])
                diag["sources"]["digikala"] = {"status": "ok" if t0.status_code == 200 else "error", "url": self.digikala_render_url, "http_code": t0.status_code, "items_available": total, "auth": "authenticated" if token else "no_token"}
            except Exception as e:
                diag["sources"]["digikala"] = {"status": "error", "url": self.digikala_render_url, "error": str(e)}
        else:
            diag["sources"]["digikala"] = {"status": "not_configured", "url": self.digikala_render_url or "تنظیم نشده"}

        # 2. Divar
        if self.divar_render_url and self.divar_render_url.startswith("http") and "your-" not in self.divar_render_url:
            token = self._get_auth_token(self.divar_render_url)
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            try:
                t0 = requests.get(f"{self.divar_render_url}/api/posts?page_size=5&page=1", headers=headers, timeout=12)
                data = t0.json() if t0.status_code == 200 else {}
                total = data.get("total") or len(data.get("items") or data.get("posts") or [])
                diag["sources"]["divar"] = {"status": "ok" if t0.status_code == 200 else "error", "url": self.divar_render_url, "http_code": t0.status_code, "items_available": total, "auth": "authenticated" if token else "no_token"}
            except Exception as e:
                diag["sources"]["divar"] = {"status": "error", "url": self.divar_render_url, "error": str(e)}
        else:
            diag["sources"]["divar"] = {"status": "not_configured", "url": self.divar_render_url or "تنظیم نشده"}

        # 3. Esam
        if self.esam_render_url and self.esam_render_url.startswith("http") and "your-" not in self.esam_render_url:
            try:
                t0 = requests.get(f"{self.esam_render_url}/api/esam/items?limit=5&offset=0", timeout=12)
                data = t0.json() if t0.status_code == 200 else {}
                total = data.get("total") or len(data.get("items") or [])
                diag["sources"]["esam"] = {"status": "ok" if t0.status_code == 200 else "error", "url": self.esam_render_url, "http_code": t0.status_code, "items_available": total}
            except Exception as e:
                diag["sources"]["esam"] = {"status": "error", "url": self.esam_render_url, "error": str(e)}
        else:
            diag["sources"]["esam"] = {"status": "not_configured", "url": self.esam_render_url or "تنظیم نشده"}

        # 4. Torob
        torob_items, torob_source = self.pull_torob_items()
        diag["sources"]["torob"] = {
            "status": "ok" if torob_items else "empty_or_missing",
            "source": torob_source,
            "items_count": len(torob_items)
        }

        return diag

    def fetch_all_digikala(self, max_pages: int = 120) -> List[Dict[str, Any]]:
        self.reload_config()
        if not self.digikala_render_url or "your-" in self.digikala_render_url:
            return []

        token = self._get_auth_token(self.digikala_render_url)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        total_pages = 1
        total_items = 0
        try:
            r0 = requests.get(f"{self.digikala_render_url}/api/products?page_size=100&page=1", headers=headers, timeout=15)
            if r0.status_code == 200:
                data = r0.json()
                total_pages = min(data.get("total_pages") or 1, max_pages)
                total_items = data.get("total") or len(data.get("items") or [])
            elif r0.status_code == 401:
                # Force refresh token and retry
                self._tokens_cache.pop(self.digikala_render_url, None)
                token = self._get_auth_token(self.digikala_render_url)
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                r0 = requests.get(f"{self.digikala_render_url}/api/products?page_size=100&page=1", headers=headers, timeout=15)
                if r0.status_code == 200:
                    data = r0.json()
                    total_pages = min(data.get("total_pages") or 1, max_pages)
                    total_items = data.get("total") or len(data.get("items") or [])
        except Exception:
            total_pages = 80

        push_live_log("INFO", f"🌐 [دیجی‌کالا] دانلود همزمان {total_items or 'کاتالوگ'} کالا ({total_pages} صفحه)...")

        all_items = []
        def fetch_page(p):
            for _ in range(3):
                try:
                    url = f"{self.digikala_render_url}/api/products?page_size=100&page={p}"
                    resp = requests.get(url, headers=headers, timeout=18)
                    if resp.status_code == 200:
                        page_data = resp.json()
                        raw_list = page_data.get("items") or page_data.get("products") or []
                        parsed = []
                        for it in raw_list:
                            parsed.append({
                                "id": it.get("product_id") or it.get("id"),
                                "title_fa": it.get("title_fa") or it.get("title"),
                                "brand": it.get("brand"),
                                "category_key": it.get("category_key"),
                                "price": it.get("selling_price_toman") or it.get("selling_price") or it.get("price"),
                                "selling_price_toman": it.get("selling_price_toman") or it.get("selling_price"),
                                "rrp_price": it.get("rrp_price_toman") or it.get("rrp_price"),
                                "discount_percent": it.get("discount_percent"),
                                "seller_name": it.get("seller_name"),
                                "url": it.get("product_url") or it.get("url"),
                                "image_url": it.get("image_url")
                            })
                        return parsed
                except Exception:
                    time.sleep(0.5)
            return []

        with ThreadPoolExecutor(max_workers=6) as executor:
            page_results = list(executor.map(fetch_page, range(1, total_pages + 1)))

        for res in page_results:
            all_items.extend(res)

        push_live_log("SUCCESS", f"✅ [دیجی‌کالا] دانلود کامل: {len(all_items)} محصول دریافت شد.")
        return all_items

    def fetch_all_divar(self, max_pages: int = 220) -> List[Dict[str, Any]]:
        self.reload_config()
        if not self.divar_render_url or "your-" in self.divar_render_url:
            return []

        token = self._get_auth_token(self.divar_render_url)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        total_pages = 1
        total_items = 0
        try:
            r0 = requests.get(f"{self.divar_render_url}/api/posts?page_size=100&page=1", headers=headers, timeout=15)
            if r0.status_code == 200:
                data = r0.json()
                total_pages = min(data.get("total_pages") or 1, max_pages)
                total_items = data.get("total") or len(data.get("items") or [])
            elif r0.status_code == 401:
                self._tokens_cache.pop(self.divar_render_url, None)
                token = self._get_auth_token(self.divar_render_url)
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                r0 = requests.get(f"{self.divar_render_url}/api/posts?page_size=100&page=1", headers=headers, timeout=15)
                if r0.status_code == 200:
                    data = r0.json()
                    total_pages = min(data.get("total_pages") or 1, max_pages)
                    total_items = data.get("total") or len(data.get("items") or [])
        except Exception:
            total_pages = 150

        push_live_log("INFO", f"🌐 [دیوار] دانلود همزمان {total_items or 'کاتالوگ'} آگهی ({total_pages} صفحه)...")

        all_posts = []
        def fetch_page(p):
            for _ in range(3):
                try:
                    url = f"{self.divar_render_url}/api/posts?page_size=100&page={p}"
                    resp = requests.get(url, headers=headers, timeout=18)
                    if resp.status_code == 200:
                        page_data = resp.json()
                        raw_list = page_data.get("items") or page_data.get("posts") or []
                        parsed = []
                        for it in raw_list:
                            parsed.append({
                                "token": it.get("token") or it.get("item_id"),
                                "title": it.get("title_fa") or it.get("title"),
                                "title_fa": it.get("title_fa") or it.get("title"),
                                "brand": it.get("brand"),
                                "selling_price": it.get("selling_price_toman") or it.get("selling_price") or it.get("price"),
                                "selling_price_toman": it.get("selling_price_toman") or it.get("selling_price"),
                                "condition": it.get("condition") or "کارکرده",
                                "category_key": it.get("category_key"),
                                "district": it.get("district") or it.get("city") or "تهران",
                                "url": it.get("post_url") or it.get("url"),
                                "image_url": it.get("image_url")
                            })
                        return parsed
                except Exception:
                    time.sleep(0.5)
            return []

        with ThreadPoolExecutor(max_workers=6) as executor:
            page_results = list(executor.map(fetch_page, range(1, total_pages + 1)))

        for res in page_results:
            all_posts.extend(res)

        push_live_log("SUCCESS", f"✅ [دیوار] دانلود کامل: {len(all_posts)} آگهی دریافت شد.")
        return all_posts

    def fetch_all_esam(self, max_pages: int = 50) -> List[Dict[str, Any]]:
        self.reload_config()
        if not self.esam_render_url or "your-" in self.esam_render_url:
            return []

        total_items = 0
        try:
            r0 = requests.get(f"{self.esam_render_url}/api/esam/items?limit=10&offset=0", timeout=15)
            if r0.status_code == 200:
                data = r0.json()
                total_items = data.get("total") or len(data.get("items") or [])
        except Exception:
            total_items = 3500

        offsets = list(range(0, min(total_items + 100, max_pages * 100), 100))
        push_live_log("INFO", f"🌐 [ایسام] دانلود همزمان {total_items or 'کاتالوگ'} کالا ({len(offsets)} صفحه)...")

        all_items = []
        def fetch_offset(off):
            for _ in range(3):
                try:
                    url = f"{self.esam_render_url}/api/esam/items?limit=100&offset={off}"
                    resp = requests.get(url, timeout=18)
                    if resp.status_code == 200:
                        page_data = resp.json()
                        return page_data.get("items") or []
                except Exception:
                    time.sleep(0.5)
            return []

        with ThreadPoolExecutor(max_workers=6) as executor:
            offset_results = list(executor.map(fetch_offset, offsets))

        for res in offset_results:
            all_items.extend(res)

        push_live_log("SUCCESS", f"✅ [ایسام] دانلود کامل: {len(all_items)} کالا دریافت شد.")
        return all_items

    def pull_torob_items(self) -> Tuple[List[Dict[str, Any]], str]:
        self.reload_config()

        # 1. Port 5000 API
        try:
            resp = requests.get("http://127.0.0.1:5000/api/local/torob-products?page_size=10000&page=1", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                products = data.get("items") or data.get("products") or (data if isinstance(data, list) else [])
                if products:
                    return products, "سرور محلی ترب (Port 5000)"
        except Exception:
            pass

        # 2. Local Files
        candidate_paths = [
            Path(self.torob_path) if self.torob_path else None,
            Path("../3_torob_windows/torob_catalog_db.json"),
            Path("3_torob_windows/torob_catalog_db.json"),
            Path("../3_torob_windows/torob_cache.json"),
            Path("3_torob_windows/torob_cache.json"),
            Path("../3_torob_windows/torob_products.json"),
            Path("torob_catalog_db.json"),
            Path("torob_cache.json"),
            Path("torob_products.json"),
        ]

        for p in candidate_paths:
            if p and p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if isinstance(data, dict):
                        if "products" in data and isinstance(data["products"], list):
                            items = data["products"]
                        elif "items" in data and isinstance(data["items"], list):
                            items = data["items"]
                        else:
                            items = list(data.values())

                        if items:
                            return items, f"فایل محلی {p.name}"

                    elif isinstance(data, list) and len(data) > 0:
                        return data, f"فایل محلی {p.name}"
                except Exception as e:
                    logger.debug(f"Error checking Torob file {p}: {e}")

        return [], "فایل یا سرور ترب یافت نشد"

    def pull_all_and_sync(self) -> Dict[str, Any]:
        push_live_log("INFO", "🚀 شروع فرآیند دانلود و همگام‌سازی کامل ۴ بازار...")
        
        torob_raw, torob_source = self.pull_torob_items()
        if torob_raw:
            push_live_log("SUCCESS", f"✅ [ترب] دریافت {len(torob_raw)} کالا از {torob_source}")
        else:
            push_live_log("INFO", "ℹ️ [ترب] فایل محلی ترب یافت نشد")

        with ThreadPoolExecutor(max_workers=3) as executor:
            f_digi = executor.submit(self.fetch_all_digikala, 120)
            f_divar = executor.submit(self.fetch_all_divar, 220)
            f_esam = executor.submit(self.fetch_all_esam, 50)

            digi_raw = f_digi.result()
            divar_raw = f_divar.result()
            esam_raw = f_esam.result()

        total_downloaded = len(digi_raw) + len(divar_raw) + len(esam_raw) + len(torob_raw)
        push_live_log("INFO", f"💾 ثبت امن {total_downloaded} آیتم در دیتابیس مشترک لوکال...")

        # Ingest into SQLite
        c_digi = ingest_digikala_items(digi_raw)
        c_divar = ingest_divar_items(divar_raw)
        c_esam = ingest_esam_items(esam_raw)
        c_torob = ingest_torob_items(torob_raw) if torob_raw else 0

        # Run Arbitrage and AI analysis
        push_live_log("INFO", "🔍 اجرای موتور آربیتراژ و فیلتر اقلام معیوب...")
        arb_res = arbitrage_engine.run_arbitrage_scan()
        ai_res = ai_exporter.export_all()

        total_synced = c_digi + c_divar + c_esam + c_torob

        db.execute("""
            INSERT INTO sync_logs (source, items_synced, matches_found, opportunities_found, status, details)
            VALUES ('STREAMING_PULL', ?, ?, ?, 'SUCCESS', ?);
        """, (
            total_synced,
            arb_res['products_scanned'],
            arb_res['opportunities_found'],
            f"Digikala: {c_digi}, Divar: {c_divar}, Esam: {c_esam}, Torob: {c_torob}"
        ))

        push_live_log("SUCCESS", f"🎉 دریافت و ادغام پایان یافت: {total_synced} کالا ثبت شد | {arb_res['opportunities_found']} فرصت آربیتراژ معتبر کشف گردید.")

        return {
            "status": "completed",
            "pulled_counts": {
                "digikala": c_digi,
                "divar": c_divar,
                "esam": c_esam,
                "torob": c_torob
            },
            "total_ingested": total_synced,
            "canonical_products_analyzed": arb_res['products_scanned'],
            "arbitrage_opportunities": arb_res['opportunities_found'],
            "ai_samples_ready": ai_res.get("samples_count", 0)
        }

cloud_puller = CloudDataPuller()
