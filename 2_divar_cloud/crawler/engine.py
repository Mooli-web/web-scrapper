import time
import random
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Tuple, Set

from crawler.db import db
from crawler.divar_adapter import DivarAdapter

logger = logging.getLogger("divar.engine")

class ContinuousDivarCrawlerEngine:
    """
    Continuous, High-Throughput & Low-RU Divar Crawler Engine with Rich Live Logging.
    """
    def __init__(self):
        self.adapter = DivarAdapter()
        self.is_running = False
        self.stop_requested = False
        
        # In-Memory Cache: {token: (selling_price, condition)}
        self._cached_posts: Dict[str, Tuple[int, str]] = {}
        self._cache_initialized = False

        self.log_counter = 0
        self.log_history: List[Dict[str, Any]] = []

        self.telemetry = {
            "status": "idle",
            "active_category": None,
            "active_city": "تهران",
            "current_page": 0,
            "total_pages": 0,
            "posts_scanned": 0,
            "new_posts_found": 0,
            "price_changes_detected": 0,
            "errors_count": 0,
            "started_at": None,
            "last_active_at": None,
            "latest_log": "موتور مستقل خزش دیوار آماده به کار است."
        }

    def emit_log(self, level: str, message: str, broadcast_fn: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.log_counter += 1
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        entry = {
            "id": self.log_counter,
            "time": now_str,
            "level": level,
            "message": message,
            "category": self.telemetry["active_category"],
            "page": self.telemetry["current_page"]
        }
        self.log_history.append(entry)
        if len(self.log_history) > 300:
            self.log_history.pop(0)

        self.telemetry["latest_log"] = message
        self.telemetry["last_active_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[{level}] {message}")

        if broadcast_fn:
            broadcast_fn({
                "telemetry": self.telemetry,
                "new_log": entry,
                "log_history": self.log_history[-40:]
            })

    def stop(self):
        self.stop_requested = True
        self.telemetry["status"] = "stopped"
        self.emit_log("WARNING", "⏹️ دستور توقف خزش دیوار از طرف کاربر دریافت شد.")

    def _auto_migrate_schema(self):
        """Auto-widens column sizes in CockroachDB to prevent any VARCHAR(50) length overflows."""
        migrations = [
            "ALTER TABLE divar_posts ALTER COLUMN token TYPE VARCHAR(255);",
            "ALTER TABLE divar_posts ALTER COLUMN condition TYPE VARCHAR(100);",
            "ALTER TABLE divar_posts ALTER COLUMN brand TYPE VARCHAR(150);",
            "ALTER TABLE divar_posts ALTER COLUMN city TYPE VARCHAR(100);",
            "ALTER TABLE divar_posts ALTER COLUMN district TYPE TEXT;",
            "ALTER TABLE divar_price_observations ALTER COLUMN token TYPE VARCHAR(255);",
            "ALTER TABLE divar_price_events ALTER COLUMN token TYPE VARCHAR(255);"
        ]
        for sql in migrations:
            try:
                db.execute(sql)
            except Exception:
                pass

    def _init_in_memory_cache(self):
        if self._cache_initialized:
            return
        try:
            self._auto_migrate_schema()
            logger.info("Initializing in-memory cache for Divar from CockroachDB...")
            rows = db.fetchall("SELECT token, selling_price_toman, condition FROM divar_posts WHERE is_active IS TRUE;")
            for r in rows:
                self._cached_posts[r["token"]] = (int(r["selling_price_toman"]), str(r["condition"]))
            self._cache_initialized = True
            self.telemetry["posts_scanned"] = len(self._cached_posts)
            logger.info(f"Loaded {len(self._cached_posts)} Divar posts into memory cache.")
        except Exception as e:
            logger.warning(f"Cache init note: {e}")

    def run_continuous_loop(self, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.is_running = True
        self.stop_requested = False
        self.telemetry["status"] = "running"
        self.telemetry["started_at"] = datetime.now(timezone.utc).isoformat()

        self._init_in_memory_cache()
        # NEW: شهرهای خزش + مهاجرت ستون description
        self.cities = [c.strip() for c in os.getenv("DIVAR_CITIES", "tehran").split(",") if c.strip()]
        try:
            db.execute("ALTER TABLE divar_posts ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';")
        except Exception as _e:
            logger.debug(f"divar_posts description migration note: {_e}")
        self.emit_log("INFO", f"🚀 پایش پیوسته ۲۴/۷ آگهی‌های دیوار آغاز شد — شهرها: {', '.join(self.cities)}", progress_callback)

        while not self.stop_requested:
            try:
                cats = db.fetchall("SELECT * FROM divar_categories WHERE is_active IS TRUE ORDER BY category_key ASC;")
                if not cats:
                    self._seed_default_categories()
                    cats = db.fetchall("SELECT * FROM divar_categories WHERE is_active IS TRUE ORDER BY category_key ASC;")

                self.emit_log("INFO", f"📋 تعداد {len(cats)} شاخه فعال دیجیتال در دستور کار خزش قرار گرفت.", progress_callback)

                for idx, cat in enumerate(cats, 1):
                    if self.stop_requested:
                        break

                    cat_key = cat["category_key"]
                    cat_name = cat["title_fa"]
                    slug = cat["slug"]
                    query = cat["query_text"]

                    self.telemetry["active_category"] = cat_name
                    self.emit_log("INFO", f"📱 [{idx}/{len(cats)}] ورود به شاخه: {cat_name} (اسلاگ: {slug} | کوئری: '{query}')...", progress_callback)

                    self._crawl_category_branch(cat_key, cat_name, slug, query, progress_callback)

                    # Update category post count in CockroachDB
                    try:
                        db.execute(
                            """
                            UPDATE divar_categories 
                            SET post_count = (SELECT COUNT(*) FROM divar_posts WHERE category_key = %s),
                                last_crawled_at = CURRENT_TIMESTAMP
                            WHERE category_key = %s;
                            """,
                            (cat_key, cat_key)
                        )
                    except Exception:
                        pass

                    # Organic pause between branches (3.0s - 5.0s)
                    if not self.stop_requested:
                        pause_sec = round(random.uniform(3.0, 5.0), 2)
                        self.emit_log("INFO", f"☕ پایان شاخه {cat_name} | استراحت ایمن {pause_sec} ثانیه‌ای...", progress_callback)
                        time.sleep(pause_sec)

                if not self.stop_requested:
                    self.emit_log("INFO", "🔄 یک دور کامل از تمام شاخه‌های دیوار اسکن شد؛ آغاز دور جدید پایش ۲۴/۷...", progress_callback)
                    time.sleep(15)

            except Exception as e:
                logger.error(f"Error in continuous Divar loop: {e}")
                self.telemetry["errors_count"] += 1
                self.emit_log("ERROR", f"⚠️ خطای ارتباطی در حلقه خزش: {e}", progress_callback)
                time.sleep(10)

        self.is_running = False
        self.telemetry["status"] = "stopped"
        self.emit_log("WARNING", "⏹️ خزش دیوار متوقف شد.", progress_callback)

    def _crawl_category_branch(self, cat_key: str, cat_name: str, slug: str, query: str, progress_callback=None):
        max_pages = 8
        self.telemetry["total_pages"] = max_pages

        # NEW: خزش چند-شهری — لیست شهرها از env لیست DIVAR_CITIES (پیش‌فرض: تهران)
        from crawler.divar_adapter import CITY_NAMES_FA
        for city_slug in self.cities:
            if self.stop_requested:
                break
            city_fa = CITY_NAMES_FA.get(city_slug, city_slug)
            self.emit_log("INFO", f"🏙️ شهر {city_fa} — شاخه: {cat_name}", progress_callback)

            for page in range(1, max_pages + 1):
                if self.stop_requested:
                    break

                self.telemetry["current_page"] = page
                posts, telem = self.adapter.fetch_category_page(slug=slug, query=query, city_slug=city_slug, page=page)

                status_code = telem.get("status_code", 0)
                elapsed_ms = telem.get("response_time_ms", 0.0)
                jitter_sec = telem.get("jitter_sec", 1.8)

                if telem.get("error"):
                    self.telemetry["errors_count"] += 1
                    self.emit_log("ERROR", f"⚠️ خطا در صفحه {page} دیوار ({cat_name} | {city_fa}): {telem['error']}", progress_callback)
                    break

                if not posts:
                    self.emit_log("INFO", f"🏁 پایان آگهی‌های شاخه {cat_name} در {city_fa} — صفحه {page}.", progress_callback)
                    break

                self._process_page_batch(cat_key, cat_name, posts, page, len(posts), jitter_used=jitter_sec, progress_callback=progress_callback)

    def _process_page_batch(self, cat_key: str, cat_name: str, posts: List[Dict[str, Any]], page_num: int, raw_count: int, jitter_used: float, progress_callback=None):
        now_dt = datetime.now(timezone.utc)
        
        upsert_posts = []
        new_obs = []
        new_events = []
        page_new = 0
        page_changes = 0
        samples = []

        for p in posts:
            token = p["token"]
            title = p["title_fa"]
            brand = p["brand"]
            selling = p["selling_price_toman"]
            condition = p["condition"]
            city = p["city"]
            district = p["district"]
            desc = (p.get("description") or "")[:1200]  # NEW
            img_url = p["image_url"]
            post_url = p["post_url"]

            cached = self._cached_posts.get(token)
            if cached is None:
                page_new += 1
                self._cached_posts[token] = (selling, condition)
                upsert_posts.append((token, title, brand, cat_key, selling, condition, city, district, desc, img_url, post_url, now_dt, now_dt))
                new_obs.append((token, selling, now_dt))
                if len(samples) < 2:
                    price_display = f"{selling:,} ت" if selling > 0 else "توافقی"
                    samples.append(f"{title[:18]}... ({price_display} | {condition})")
            else:
                old_selling, old_cond = cached
                if old_selling != selling or old_cond != condition:
                    page_changes += 1
                    self._cached_posts[token] = (selling, condition)
                    upsert_posts.append((token, title, brand, cat_key, selling, condition, city, district, desc, img_url, post_url, now_dt, now_dt))
                    new_obs.append((token, selling, now_dt))
                    
                    if old_selling > 0 and selling < old_selling and selling > 0:
                        drop_pct = round(((old_selling - selling) / old_selling) * 100.0, 2)
                        severity = "high" if drop_pct >= 15.0 else "medium"
                        new_events.append((token, 'price_drop', old_selling, selling, drop_pct, severity, now_dt))
                    if len(samples) < 2:
                        samples.append(f"🔥 {title[:18]}... ({old_selling:,} -> {selling:,} ت)")

        # Batch write to CockroachDB
        db_write_success = False
        try:
            if upsert_posts:
                for row in upsert_posts:
                    db.execute(
                        """
                        INSERT INTO divar_posts 
                        (token, title_fa, brand, category_key, selling_price_toman, condition, city, district, description, image_url, post_url, first_seen_at, last_seen_at, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                        ON CONFLICT (token) DO UPDATE 
                        SET selling_price_toman = EXCLUDED.selling_price_toman,
                            condition = EXCLUDED.condition,
                            last_seen_at = EXCLUDED.last_seen_at;
                        """,
                        row
                    )

            if new_obs:
                for row in new_obs:
                    db.execute(
                        "INSERT INTO divar_price_observations (token, selling_price_toman, observed_at) VALUES (%s, %s, %s);",
                        row
                    )

            if new_events:
                for row in new_events:
                    db.execute(
                        "INSERT INTO divar_price_events (token, event_type, old_price_toman, new_price_toman, drop_percent, severity, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s);",
                        row
                    )
            db_write_success = True
        except Exception as ex:
            logger.error(f"[Divar] Batch write error to CockroachDB: {ex}")
            self.emit_log("ERROR", f"❌ خطا در ثبت دیتابیس CockroachDB: {ex}", progress_callback)

        self.telemetry["posts_scanned"] = len(self._cached_posts)
        self.telemetry["new_posts_found"] += page_new
        self.telemetry["price_changes_detected"] += page_changes

        sample_str = f" | نمونه: {' ، '.join(samples)}" if samples else ""
        db_tag = " [ذخیره در دیتابیس ✅]" if db_write_success and page_new > 0 else ""
        msg = f"📄 [{cat_name}] صفحه {page_num}: دریافت {len(posts)} آگهی ({page_new} جدید، {page_changes} تغییر){db_tag}{sample_str}"
        self.emit_log("INFO", msg, progress_callback)

    def _seed_default_categories(self):
        try:
            from crawler.cli import cmd_init_db
            cmd_init_db(seed=True)
        except Exception:
            pass

divar_crawler = ContinuousDivarCrawlerEngine()
