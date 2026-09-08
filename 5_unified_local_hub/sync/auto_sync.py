# -*- coding: utf-8 -*-
"""
⏰ Auto Sync Scheduler — چرخه‌ی خودکار هاب (سینک + پالایش + بازبینی AI + آربیتراژ)
===================================================================================
دیگر نیازی به دکمه زدن نیست؛ در زمان‌بندی مشخص، خودکار:

    ۱. دانلود آگهی‌های جدید از ۴ بازار (pull_all_and_sync)
    ۲. اجرای پالایش لایه ۱ (قوانین + الگوهای آموخته‌شده)
    ۳. تخلیه‌ی خودکار صف AI — تا صفر شدن صف یا سقف زمانی (AUTO_AI_MAX_MINUTES)؛
       صبر برای 429 داخل run_review مدیریت می‌شود؛ اگر دو دور پیاپی پیشرفت نبود،
       می‌ایستد تا چرخه‌ی بعدی ادامه دهد (هیچ تصمیمی از دست نمی‌رود — کش می‌ماند)
    ۴. بازمحاسبه‌ی آربیتراژ و خروجی AI dataset

تنظیم در .env (همه اختیاری):
    AUTO_SYNC_ENABLED=true            # پیش‌فرض true
    AUTO_SYNC_INTERVAL_MINUTES=360    # هر ۶ ساعت (حداقل ۳۰)
    AUTO_SYNC_DAILY_AT=08:30          # اگر ست شود، «روزی یک بار ساعت ۸:۳۰» به‌جای بازه
    AUTO_SYNC_ON_START=true           # با هر بالا آمدن هاب، یک چرخه بلافاصله اجرا شود
    AUTO_AI_MAX_MINUTES=90            # سقف زمان تخلیه‌ی AI در هر چرخه

مشاهده/کنترل: GET و POST ‎/api/sync/scheduler — گزارش چرخه‌ها در کنسول داشبورد.
"""

import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from core.data_cleaner import data_purifier
from core.arbitrage_engine import arbitrage_engine
from core.ai_dataset_generator import ai_exporter
from core.ai_reviewer import ai_reviewer
from core.groq_client import groq_client
from database.db_manager import db

logger = logging.getLogger("hub.auto_sync")


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


class AutoSyncScheduler:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.running = False
        self.last_run_at: Optional[str] = None
        self.next_run_at: Optional[str] = None
        self.last_cycle: Dict[str, Any] = {}
        self._last_daily_key = ""
        self.reload_config()

    # ------------------------------------------------------------ تنظیمات
    def reload_config(self):
        self.enabled = _env_bool("AUTO_SYNC_ENABLED", "true")
        try:
            self.interval_min = max(30, int(os.getenv("AUTO_SYNC_INTERVAL_MINUTES", "360")))
        except ValueError:
            self.interval_min = 360
        daily = os.getenv("AUTO_SYNC_DAILY_AT", "").strip()
        self.daily_at = daily if (":" in daily and len(daily) <= 5) else ""
        self.on_start = _env_bool("AUTO_SYNC_ON_START", "true")
        try:
            self.ai_max_minutes = max(5, int(os.getenv("AUTO_AI_MAX_MINUTES", "90")))
        except ValueError:
            self.ai_max_minutes = 90
        self._compute_next_run()

    def _compute_next_run(self):
        now = datetime.now()
        if self.daily_at:
            try:
                h, m = (int(x) for x in self.daily_at.split(":"))
                nxt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if nxt <= now:
                    nxt += timedelta(days=1)
                self.next_run_at = nxt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                self.next_run_at = (now + timedelta(minutes=self.interval_min)).strftime("%Y-%m-%d %H:%M")
        else:
            base = datetime.strptime(self.last_run_at, "%Y-%m-%d %H:%M") if self.last_run_at else now
            self.next_run_at = (base + timedelta(minutes=self.interval_min)).strftime("%Y-%m-%d %H:%M")

    # ------------------------------------------------------------ زمان‌بندی
    def _should_run(self, now: datetime) -> bool:
        if not self.enabled:
            return False
        if self.daily_at:
            key = now.strftime("%Y-%m-%d")
            try:
                h, m = (int(x) for x in self.daily_at.split(":"))
            except ValueError:
                return False
            if now.hour == h and now.minute == m and self._last_daily_key != key:
                self._last_daily_key = key
                return True
            return False
        if not self.last_run_at:
            return self.on_start
        last = datetime.strptime(self.last_run_at, "%Y-%m-%d %H:%M")
        return (now - last).total_seconds() >= self.interval_min * 60

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="auto-sync")
        self._thread.start()
        logger.info(f"Auto-sync scheduler started | enabled={self.enabled} "
                    f"| mode={'daily ' + self.daily_at if self.daily_at else f'every {self.interval_min}min'} "
                    f"| on_start={self.on_start}")

    def stop(self):
        self._stop.set()

    def _loop(self):
        # اولین چرخه با کمی تأخیر تا سرور کامل بالا بیاید
        time.sleep(20)
        while not self._stop.is_set():
            try:
                if self._should_run(datetime.now()):
                    self.run_cycle(reason="زمان‌بندی" if self.last_run_at else "شروع")
            except Exception as e:
                logger.warning(f"Auto-sync loop note: {e}")
            self._stop.wait(45)

    # ------------------------------------------------------------ چرخه‌ی اصلی
    def run_cycle(self, reason: str = "دستی") -> Dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            logger.info("Auto-sync cycle skipped — another cycle is already running.")
            return {"status": "skipped", "reason": "چرخه‌ی دیگری در حال اجراست"}
        try:
            self.running = True
            from sync.pull_cloud_databases import cloud_puller, push_live_log

            push_live_log("INFO", f"⏰ [زمان‌بند/{reason}] شروع چرخه‌ی خودکار: سینک ← پالایش ← AI ← آربیتراژ")

            # ۱) سینک ۴ بازار
            try:
                pull_res = cloud_puller.pull_all_and_sync() or {}
            except Exception as e:
                pull_res = {"error": str(e)}
                push_live_log("WARNING", f"⏰ [زمان‌بند] خطا در سینک: {e}")
            ingested = pull_res.get("total_ingested", 0)

            # ۱.۵) NEW: حذف خودکار تکراری‌های دقیق (اسپم/بازپست) قبل از پالایش
            try:
                from dedupe_listings import dedupe_exact_quiet
                removed = dedupe_exact_quiet()
                if removed:
                    push_live_log("INFO", f"🧹 [زمان‌بند] {removed:,} آگهی تکراری (بازپست) حذف شد")
            except Exception as e:
                logger.debug(f"auto dedupe note: {e}")

            # ۲) پالایش لایه ۱
            pur = data_purifier.run_full_purification_pipeline()
            pur_b = pur.get("breakdown", {})

            # ۳) تخلیه‌ی خودکار صف AI
            ai_summary = {"rounds": 0, "api_processed": 0, "api_verified": 0,
                          "api_rejected": 0, "cached_applied": 0, "stopped_reason": "صف خالی شد"}
            if groq_client.is_configured():
                deadline = time.time() + self.ai_max_minutes * 60
                stalled = 0
                while time.time() < deadline:
                    if ai_reviewer.count_pending() == 0:
                        break
                    r = ai_reviewer.run_review(max_batches=40, batch_size=50)
                    ai_summary["rounds"] += 1
                    ai_summary["api_processed"] += r.get("api_processed", 0)
                    ai_summary["api_verified"] += r.get("api_verified", 0)
                    ai_summary["api_rejected"] += r.get("api_rejected", 0)
                    ai_summary["cached_applied"] += r.get("cached_applied", 0)
                    progress = r.get("api_processed", 0) + r.get("cached_applied", 0)
                    if progress == 0:
                        stalled += 1
                        if stalled >= 2:
                            ai_summary["stopped_reason"] = "توقف موقت (محدودیت نرخ/خطا) — چرخه‌ی بعدی ادامه می‌دهد"
                            break
                        time.sleep(30)
                    else:
                        stalled = 0
                else:
                    ai_summary["stopped_reason"] = f"سقف زمان {self.ai_max_minutes} دقیقه — چرخه‌ی بعدی ادامه می‌دهد"
            else:
                ai_summary["stopped_reason"] = "کلید Groq تنظیم نشده"

            # ۳.۵) NEW: ممیزی دسته با AI (فقط محصولات تازه — بعد از اولین پاس کامل، چند دسته در هر چرخه)
            try:
                cat_res = ai_reviewer.run_category_audit(max_batches=2, batch_size=25)
                ai_summary["categories_processed"] = cat_res.get("processed", 0)
                ai_summary["categories_changed"] = cat_res.get("categories_changed", 0)
            except Exception as e:
                logger.debug(f"category audit note: {e}")

            # ۴) آربیتراژ و خروجی
            arb = arbitrage_engine.run_arbitrage_scan()
            exp = ai_exporter.export_all()

            self.last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._compute_next_run()
            self.last_cycle = {
                "ran_at": self.last_run_at,
                "reason": reason,
                "ingested": ingested,
                "purification": pur_b,
                "ai": ai_summary,
                "pending_after": ai_reviewer.count_pending(),
                "arbitrage_deals": arb.get("opportunities_found", 0),
                "dataset_samples": exp.get("samples_count", 0),
            }
            push_live_log(
                "SUCCESS",
                f"⏰ [زمان‌بند] چرخه تمام شد: {ingested} آگهی جدید | پالایش {pur_b.get('verified_clean', 0)}✅ "
                f"| AI {ai_summary['api_processed'] + ai_summary['cached_applied']} تصمیم "
                f"| صف باقی‌مانده {self.last_cycle['pending_after']} "
                f"| {self.last_cycle['arbitrage_deals']} فرصت آربیتراژ"
            )
            return {"status": "completed", **self.last_cycle}
        finally:
            self.running = False
            self._lock.release()

    # ------------------------------------------------------------ وضعیت/API
    def status(self) -> Dict[str, Any]:
        pending = 0
        try:
            pending = ai_reviewer.count_pending()
        except Exception:
            pass
        return {
            "enabled": self.enabled,
            "mode": (f"روزی یک‌بار ساعت {self.daily_at}" if self.daily_at
                     else f"هر {self.interval_min} دقیقه"),
            "on_start": self.on_start,
            "ai_max_minutes": self.ai_max_minutes,
            "running_now": self.running,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "ai_pending": pending,
            "groq_configured": groq_client.is_configured(),
            "last_cycle": self.last_cycle,
        }

    def apply_settings(self, payload: Dict[str, Any]) -> bool:
        """تغییر تنظیمات بدون ری‌استارت (فقط در حافظه — برای همیشگی، .env را بنویس)."""
        if "enabled" in payload:
            self.enabled = bool(payload["enabled"])
        if "interval_minutes" in payload:
            try:
                self.interval_min = max(30, int(payload["interval_minutes"]))
                self.daily_at = ""
            except (TypeError, ValueError):
                return False
        if "daily_at" in payload:
            v = str(payload["daily_at"] or "").strip()
            if v:
                if ":" not in v or len(v) > 5:
                    return False
                self.daily_at = v
            else:
                self.daily_at = ""
        self._compute_next_run()
        return True


auto_sync_scheduler = AutoSyncScheduler()
