import time
import random
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Tuple, Set

from crawler.db import db
from crawler.esam_adapter import EsamAdapter

logger = logging.getLogger("esam.engine")

DEFAULT_CATEGORIES = [
    {"key": "auctions_ending", "name": "مزایدات رو به اتمام", "slug": "auctions?activeTab=TowardTheEnd", "is_auction": True},
    {"key": "auctions_hot", "name": "مزایدات دارای پیشنهاد داغ", "slug": "auctions?activeTab=HasBid", "is_auction": True},
    {"key": "laptop", "name": "لپ‌تاپ و نوت‌بوک", "slug": "search/laptop?cc=40100", "is_auction": False},
    {"key": "gpu", "name": "کارت گرافیک (GPU)", "slug": "search/graphic-card?cc=40201", "is_auction": False},
    {"key": "cpu", "name": "پردازنده کامپیوتر (CPU)", "slug": "search/cpu?cc=40202", "is_auction": False},
    {"key": "ram", "name": "حافظه رم (RAM)", "slug": "search/ram?cc=40203", "is_auction": False},
    {"key": "motherboard", "name": "مادربرد", "slug": "search/motherboard?cc=40204", "is_auction": False},
    {"key": "ssd_hdd", "name": "هارد و حافظه SSD", "slug": "search/storage?cc=40206", "is_auction": False},
    {"key": "monitor", "name": "مانیتور و نمایشگر", "slug": "search/monitor?cc=40300", "is_auction": False},
    {"key": "mobile_apple", "name": "گوشی موبایل اپل (آیفون)", "slug": "search/apple-iphone?cc=30101", "is_auction": False},
    {"key": "mobile_samsung", "name": "گوشی موبایل سامسونگ", "slug": "search/samsung-mobile?cc=30102", "is_auction": False},
    {"key": "mobile_xiaomi", "name": "گوشی موبایل شیائومی", "slug": "search/xiaomi-mobile?cc=30103", "is_auction": False},
    {"key": "console_ps5_ps4", "name": "کنسول پلی‌استیشن (PS5/PS4)", "slug": "search/playstation?cc=50100", "is_auction": False},
    {"key": "console_xbox", "name": "کنسول ایکس‌باکس (Xbox)", "slug": "search/xbox?cc=50200", "is_auction": False},
    {"key": "vintage_mobile", "name": "گوشی‌های عتیقه و کلکسیونی", "slug": "search/vintage-mobile?cc=93401", "is_auction": False}
]

class ContinuousEsamCrawlerEngine:
    """
    Continuous, High-Throughput & Low-RU Esam Crawler Engine with Rich Live Telemetry.
    """
    def __init__(self):
        self.adapter = EsamAdapter()
        self.is_running = False
        self.stop_requested = False
        
        # In-Memory Cache: {item_id: (selling_price, bids_count)}
        self._cached_items: Dict[str, Tuple[int, int]] = {}
        self._cache_initialized = False

        self.log_counter = 0
        self.log_history: List[Dict[str, Any]] = []

        self.telemetry = {
            "status": "idle",
            "active_category": None,
            "current_page": 0,
            "total_pages": 0,
            "items_scanned": 0,
            "new_items_found": 0,
            "price_changes_detected": 0,
            "bids_updated": 0,
            "errors_count": 0,
            "started_at": None,
            "last_active_at": None,
            "latest_log": "موتور مستقل خزش ایسام آماده به کار است."
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
            try:
                broadcast_fn(entry)
            except Exception:
                pass

    def _init_cache(self):
        if self._cache_initialized or not db.is_configured():
            return
        try:
            db.auto_init_schema()
            rows = db.fetchall("SELECT item_id, selling_price_toman, bids_count FROM esam_items LIMIT 15000;")
            for r in rows:
                self._cached_items[r["item_id"]] = (r["selling_price_toman"] or 0, r["bids_count"] or 0)
            self._cache_initialized = True
            logger.info(f"Loaded {len(self._cached_items)} Esam items into memory cache.")
        except Exception as e:
            logger.warning(f"Could not initialize memory cache: {e}")

    def run_single_batch(self, category: Dict[str, Any], page: int, broadcast_fn: Optional[Callable] = None) -> Tuple[int, int, int]:
        """
        Scrapes a single page of items and persists updates/events in CockroachDB.
        Returns: (new_items_count, price_changes_count, bids_changed_count)
        """
        category_key = category["key"]
        category_name = category["name"]
        query_slug = category["slug"]

        self.telemetry["active_category"] = category_name
        self.telemetry["current_page"] = page

        items = self.adapter.fetch_category_items(
            query_slug=query_slug,
            page=page,
            category_key=category_key,
            category_name=category_name
        )

        if not items:
            self.emit_log("INFO", f"📄 [{category_name}] صفحه {page}: کالایی یافت نشد یا پایان صفحه.", broadcast_fn)
            return 0, 0, 0

        new_count = 0
        price_change_count = 0
        bids_change_count = 0

        self._init_cache()

        if db.is_configured():
            for item in items:
                try:
                    item_id = item["item_id"]
                    curr_price = item["selling_price_toman"]
                    curr_bids = item["bids_count"]

                    if item_id not in self._cached_items:
                        # 1. New Item Listing
                        db.execute("""
                            INSERT INTO esam_items (
                                item_id, title_fa, category_key, category_name_fa, brand,
                                condition, is_auction, selling_price_toman, base_price_toman,
                                buy_now_price_toman, bids_count, time_remaining, seller_name,
                                seller_score, seller_city, url, image_url, description, last_seen_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                            ) ON CONFLICT (item_id) DO UPDATE SET
                                selling_price_toman = EXCLUDED.selling_price_toman,
                                bids_count = EXCLUDED.bids_count,
                                time_remaining = EXCLUDED.time_remaining,
                                last_seen_at = CURRENT_TIMESTAMP;
                        """, (
                            item_id, item["title_fa"], item["category_key"], item["category_name_fa"],
                            item["brand"], item["condition"], item["is_auction"], item["selling_price_toman"],
                            item["base_price_toman"], item["buy_now_price_toman"], item["bids_count"],
                            item["time_remaining"], item["seller_name"], item["seller_score"],
                            item["seller_city"], item["url"], item["image_url"],
                            (item.get("description") or "")[:1500]  # NEW: توضیحات آگهی
                        ))

                        # Log observation
                        db.execute("""
                            INSERT INTO esam_price_observations (item_id, price_toman, is_auction, bids_count)
                            VALUES (%s, %s, %s, %s);
                        """, (item_id, curr_price, item["is_auction"], curr_bids))

                        # Log New Listing Event
                        db.execute("""
                            INSERT INTO esam_price_events (
                                item_id, title_fa, event_type, old_price_toman, new_price_toman,
                                price_change_toman, change_percent, severity
                            ) VALUES (%s, %s, 'NEW_LISTING', 0, %s, 0, 0, 'INFO');
                        """, (item_id, item["title_fa"][:150], curr_price))

                        self._cached_items[item_id] = (curr_price, curr_bids)
                        new_count += 1

                    else:
                        old_price, old_bids = self._cached_items[item_id]
                        price_diff = curr_price - old_price
                        bids_diff = curr_bids - old_bids

                        # Always refresh last seen & time remaining
                        db.execute("""
                            UPDATE esam_items SET
                                last_seen_at = CURRENT_TIMESTAMP,
                                time_remaining = %s,
                                selling_price_toman = %s,
                                bids_count = %s
                            WHERE item_id = %s;
                        """, (item["time_remaining"], curr_price, curr_bids, item_id))

                        # Check for price fluctuation
                        if curr_price > 0 and old_price > 0 and price_diff != 0:
                            change_pct = round(((curr_price - old_price) / old_price) * 100.0, 2)
                            event_type = "PRICE_DROP" if price_diff < 0 else "PRICE_HIKE"
                            severity = "GOLDEN" if change_pct <= -20 else ("WARNING" if change_pct <= -5 else "INFO")

                            db.execute("""
                                INSERT INTO esam_price_observations (item_id, price_toman, is_auction, bids_count)
                                VALUES (%s, %s, %s, %s);
                            """, (item_id, curr_price, item["is_auction"], curr_bids))

                            db.execute("""
                                INSERT INTO esam_price_events (
                                    item_id, title_fa, event_type, old_price_toman, new_price_toman,
                                    price_change_toman, change_percent, severity
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                            """, (item_id, item["title_fa"][:150], event_type, old_price, curr_price, price_diff, change_pct, severity))

                            price_change_count += 1

                        # Check for new bids in auction
                        if bids_diff > 0:
                            db.execute("""
                                INSERT INTO esam_price_events (
                                    item_id, title_fa, event_type, old_price_toman, new_price_toman,
                                    price_change_toman, change_percent, severity
                                ) VALUES (%s, %s, 'NEW_BID', %s, %s, %s, 0, 'WARNING');
                            """, (item_id, item["title_fa"][:150], old_price, curr_price, price_diff))
                            bids_change_count += 1

                        self._cached_items[item_id] = (curr_price, curr_bids)

                except Exception as e:
                    logger.error(f"Error saving Esam item {item.get('item_id')}: {e}")
                    self.telemetry["errors_count"] += 1

        self.telemetry["items_scanned"] += len(items)
        self.telemetry["new_items_found"] += new_count
        self.telemetry["price_changes_detected"] += price_change_count
        self.telemetry["bids_updated"] += bids_change_count

        self.emit_log(
            "INFO",
            f"📄 [{category_name}] صفحه {page}: دریافت {len(items)} کالا ({new_count} جدید، {price_change_count} نوسان قیمت، {bids_change_count} پیشنهاد جدید)",
            broadcast_fn
        )

        return new_count, price_change_count, bids_change_count

    def run_continuous_loop(self, broadcast_fn: Optional[Callable] = None):
        # NEW: مهاجرت ستون description (یک‌بار؛ اگر باشد بی‌اثر است)
        try:
            db.execute("ALTER TABLE esam_items ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';")
        except Exception as _e:
            logger.debug(f"esam_items description migration note: {_e}")
        """
        Continuous polite scraping loop covering auctions and categories.
        """
        self.is_running = True
        self.stop_requested = False
        self.telemetry["status"] = "running"
        self.telemetry["started_at"] = datetime.now(timezone.utc).isoformat()

        self.emit_log("INFO", "🚀 موتور خزش پیوسته ایسام با موفقیت استارت خورد.", broadcast_fn)

        categories = DEFAULT_CATEGORIES

        # Try to load categories from DB if present
        if db.is_configured():
            try:
                db_cats = db.fetchall("SELECT category_key, title_fa, query_slug, is_auction_feed FROM esam_categories WHERE is_active = TRUE ORDER BY id ASC;")
                if db_cats:
                    categories = [
                        {"key": r["category_key"], "name": r["title_fa"], "slug": r["query_slug"], "is_auction": r.get("is_auction_feed", False)}
                        for r in db_cats
                    ]
            except Exception:
                pass

        cat_idx = 0
        while not self.stop_requested:
            cat = categories[cat_idx % len(categories)]
            max_pages = 4 if cat["is_auction"] else 3

            for page in range(1, max_pages + 1):
                if self.stop_requested:
                    break

                try:
                    self.run_single_batch(cat, page, broadcast_fn)
                except Exception as e:
                    self.telemetry["errors_count"] += 1
                    self.emit_log("ERROR", f"❌ خطا در خزش [{cat['name']} صفحه {page}]: {e}", broadcast_fn)

                # Polite delay between pages
                sleep_time = random.uniform(2.0, 4.0)
                for _ in range(int(sleep_time * 10)):
                    if self.stop_requested:
                        break
                    time.sleep(0.1)

            cat_idx += 1
            # Delay between categories
            inter_cat_delay = random.uniform(3.0, 6.0)
            for _ in range(int(inter_cat_delay * 10)):
                if self.stop_requested:
                    break
                time.sleep(0.1)

        self.is_running = False
        self.stop_requested = False
        self.telemetry["status"] = "idle"
        self.emit_log("WARNING", "⏹️ موتور خزش ایسام متوقف گردید.", broadcast_fn)

    def stop(self):
        self.stop_requested = True

esam_crawler = ContinuousEsamCrawlerEngine()
