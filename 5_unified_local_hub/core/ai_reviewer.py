"""
AI Reviewer — لایه‌ی دوم پالایش: بازبینی هوشمند آگهی‌های مبهم با Groq.

جریان کار:
  data_cleaner (لایه ۱) هر آگهی بدون «نشانه‌ی کالای اصلی» را NEEDS_AI_REVIEW
  می‌کند؛ این ماژول آن‌ها را دسته‌ای (پیش‌فرض ۲۵ تایی) برای مدل زبانی می‌فرستد،
  پاسخ JSON را اعمال می‌کند و برای هر «عنوان» یک‌بار برای همیشه در جدول
  ai_review_cache کش می‌کند — یعنی هزینه‌ی API فقط یک بار برای هر عنوان پرداخت
  می‌شود و اجراهای بعدی رایگان‌اند.
"""

import hashlib
import json
import logging
import time
from typing import Dict, Any, List, Optional

from database.db_manager import db
from core.groq_client import groq_client
from core.normalizer import clean_persian_text
from core.taxonomy import STANDARD_CATEGORIES, ensure_category_columns

logger = logging.getLogger("hub.ai_reviewer")


def _live(level: str, message: str):
    """NEW: ارسال رویدادهای AI به کنسول لاگ داشبورد (در صورت حضور سرور)."""
    try:
        from sync.pull_cloud_databases import push_live_log
        push_live_log(level, message)
    except Exception:
        pass

SCOPED_CATEGORIES_HINT = (
    "موبایل/گوشی، لپ‌تاپ، کنسول بازی، کارت گرافیک و قطعات کامپیوتر، "
    "ساعت/مچ‌بند هوشمند، هدفون و ایرباد، تبلت، مانیتور، هارد/SSD"
)

SYSTEM_PROMPT = (
    "You are a strict data-quality auditor for an Iranian electronics marketplace hub. "
    "Judge EACH item COMPLETELY INDEPENDENTLY — never mention or rely on other items in your reasons.\n\n"
    "IN-SCOPE real products (is_device=true): phones (INCLUDING old/vintage models like Nokia), tablets/iPads, "
    "laptops/Macs, gaming consoles, COMPLETE desktop PCs (سیستم گیمینگ/رندر) INCLUDING mining rigs (ریگ), GPUs "
    "(including رافیک = colloquial graphics card), CPUs, RAM sticks, "
    "motherboards, internal AND external SSDs/hard drives, e-readers (Kindle/کیندل/کتابخوان), monitors, "
    "smartwatches/bands, headphones/earbuds. "
    "A real product stays is_device=true EVEN IF its price looks too high or too low — price outliers are "
    "handled by a separate statistical layer, not by you.\n"
    "NOT devices (is_device=false): accessories (case/strap/cable/charger/stand/cooler/fan/keyboard/mouse), "
    "empty boxes, broken/parts-only items, gift cards/subscriptions/accounts, services, BUY/TRADE REQUEST ads "
    "(عنوان دارای «خرید» یا «معاوضه» یا «پرداخت آنی» — poster wants to BUY, nothing is for sale), "
    "and out-of-scope goods (shoes, jewelry, stamps, home appliances, toys, clothing).\n"
    "Prices are in Toman: real phone ≥15M, laptop ≥25M, console ≥20M, GPU ≥10M typically.\n"
    "ALSO classify each item into EXACTLY ONE standard category key from this list: "
    "mobile, laptop, tablet, console, gpu, cpu, ram, storage, motherboard, desktop-pc, monitor, watch, headphone, other "
    "(desktop-pc = complete ready PC/mining rig; gpu = graphics card only). Use the title AND the description "
    "(desc) as evidence — the desc often reveals the true product type. "
    "Answer ONLY with a valid JSON object, no extra text."
)


def title_hash(title: str) -> str:
    return hashlib.md5(clean_persian_text(title).lower().encode("utf-8")).hexdigest()


class AIBatchReviewer:
    """دسته‌ای، کش‌شده و مقاوم در برابر خطا."""

    def __init__(self):
        self._ensure_cache_table()

    # ------------------------------------------------------------------ setup
    def _ensure_cache_table(self):
        """جدول کش را اگر وجود ندارد می‌سازد (بدون نیاز به دیتابیس نو)."""
        try:
            db.execute("""
                CREATE TABLE IF NOT EXISTS ai_review_cache (
                    title_hash  TEXT PRIMARY KEY,
                    title       TEXT,
                    is_device   INTEGER NOT NULL,
                    reason_fa   TEXT DEFAULT '',
                    confidence  REAL DEFAULT 0,
                    model       TEXT DEFAULT '',
                    reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # NEW: ستون category برای کشِ دسته‌بندی AI (SQLite از IF NOT EXISTS در ALTER پشتیبانی نمی‌کند)
            cols = {r["name"] for r in db.fetchall("PRAGMA table_info(ai_review_cache);")}
            if "category" not in cols:
                db.execute("ALTER TABLE ai_review_cache ADD COLUMN category TEXT DEFAULT '';")
        except Exception as e:
            logger.warning(f"ai_review_cache init note: {e}")

    # --------------------------------------------------------------- fetching
    def get_cached_hashes(self) -> set:
        rows = db.fetchall("SELECT title_hash FROM ai_review_cache;")
        return {r["title_hash"] for r in rows}

    def get_pending_listings(self, limit: int = 500) -> List[Dict[str, Any]]:
        """آگهی‌های NEEDS_AI_REVIEW که هنوز عنوانشان کش نشده است."""
        rows = db.fetchall("""
            SELECT l.id, l.canonical_key, l.title_fa, l.price_toman, l.store_key,
                   c.category_key, l.description
            FROM store_listings l
            JOIN canonical_products c ON l.canonical_key = c.canonical_key
            WHERE l.quality_status = 'NEEDS_AI_REVIEW'
            ORDER BY l.id ASC
            LIMIT ?;
        """, (limit,))
        cached = self.get_cached_hashes()
        return [r for r in rows if title_hash(r["title_fa"]) not in cached]

    def count_pending(self) -> int:
        r = db.fetchone("SELECT COUNT(*) AS c FROM store_listings WHERE quality_status = 'NEEDS_AI_REVIEW';")
        return r["c"] if r else 0

    # ------------------------------------------------------------ cached pass
    def apply_cached_verdicts(self) -> int:
        """آگهی‌هایی که عنوانشان قبلاً بازبینی شده را رایگان اعمال می‌کند."""
        rows = db.fetchall("""
            SELECT id, title_fa FROM store_listings
            WHERE quality_status = 'NEEDS_AI_REVIEW' LIMIT 2000;
        """)
        if not rows:
            return 0
        cached = {r["title_hash"]: r for r in db.fetchall(
            "SELECT title_hash, title, is_device, reason_fa, confidence, category FROM ai_review_cache;"
        )}
        updates = []
        cat_updates = []  # NEW: دسته‌های کش‌شده هم رایگان اعمال می‌شوند
        by_id = {r["id"]: r for r in rows}
        for row in rows:
            c = cached.get(title_hash(row["title_fa"]))
            if not c:
                continue
            if int(c["is_device"]) == 1:
                updates.append((1, "VERIFIED", f"🤖 {c['reason_fa']}", float(c["confidence"]), row["id"]))
            else:
                updates.append((0, "AI_REJECTED", f"🤖 {c['reason_fa']}", float(c["confidence"]), row["id"]))
        if updates:
            db.executemany("""
                UPDATE store_listings SET is_verified = ?, quality_status = ?,
                       rejection_reason = ?, confidence_score = ?
                WHERE id = ?;
            """, updates)
            logger.info(f"Applied {len(updates)} cached AI verdicts (zero API cost).")
        return len(updates)

    # ---------------------------------------------------------------- review
    def review_one_batch(self, batch: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """یک دسته را به Groq می‌فرستد و تصمیم‌ها را اعمال و کش می‌کند."""
        if not batch:
            return {"processed": 0, "verified": 0, "rejected": 0}

        payload_items = [
            {"i": idx, "title": r["title_fa"], "price_toman": r["price_toman"],
             "store": r["store_key"], "category": r["category_key"] or "digital",
             # NEW: توضیحات آگهی — شاهد اصلی دسته‌بندی درست
             "desc": str(r.get("description") or "")[:280]}
            for idx, r in enumerate(batch, start=1)
        ]
        user_prompt = (
            "Audit these marketplace listings. For EACH item return a verdict.\n"
            'Respond ONLY as JSON: {"verdicts":[{"i":1,"is_device":true,'
            '"category":"gpu","reason_fa":"دلیل کوتاه فارسی","confidence":0.97}, ...]}\n\n'
            + json.dumps(payload_items, ensure_ascii=False)
        )

        raw = groq_client.chat_json(SYSTEM_PROMPT, user_prompt, max_tokens=2500)
        if not raw or "verdicts" not in raw:
            return None  # خطای API — بعداً دوباره تلاش می‌شود

        verdicts = raw["verdicts"]
        by_index = {}
        for v in verdicts:
            try:
                by_index[int(v.get("i"))] = v
            except (TypeError, ValueError):
                continue

        updates = []
        cache_rows = []
        cat_updates = []  # NEW: اصلاح دسته‌ی کانونیکال توسط AI
        verified_n = rejected_n = 0
        for idx, r in enumerate(batch, start=1):
            v = by_index.get(idx)
            if not v:
                continue
            is_device = bool(v.get("is_device", False))
            # NEW: دسته‌ی استاندارد از AI (در صورت معتبر بودن)
            ai_cat = str(v.get("category", "") or "").strip().lower()
            if ai_cat in STANDARD_CATEGORIES and r.get("canonical_key"):
                cat_updates.append((ai_cat, r["canonical_key"]))
            try:
                conf = min(100.0, max(0.0, float(v.get("confidence", 0.9)) * 100.0))
            except (TypeError, ValueError):
                conf = 90.0
            reason = str(v.get("reason_fa", ""))[:250] or ("کالای اصلی تایید شد" if is_device else "کالای جانبی/خارج از اسکوپ")

            if is_device:
                updates.append((1, "VERIFIED", f"🤖 {reason}", conf, r["id"]))
                verified_n += 1
            else:
                updates.append((0, "AI_REJECTED", f"🤖 {reason}", conf, r["id"]))
                rejected_n += 1

            h = title_hash(r["title_fa"])
            cache_rows.append((h, r["title_fa"], 1 if is_device else 0, reason,
                               conf, groq_client.active_model,
                               ai_cat if ai_cat in STANDARD_CATEGORIES else ""))

        if updates:
            db.executemany("""
                UPDATE store_listings SET is_verified = ?, quality_status = ?,
                       rejection_reason = ?, confidence_score = ?
                WHERE id = ?;
            """, updates)
        if cache_rows:
            db.executemany("""
                INSERT INTO ai_review_cache (title_hash, title, is_device, reason_fa, confidence, model, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(title_hash) DO UPDATE SET
                    is_device = excluded.is_device,
                    reason_fa = excluded.reason_fa,
                    confidence = excluded.confidence,
                    model = excluded.model,
                    category = excluded.category,
                    reviewed_at = CURRENT_TIMESTAMP;
            """, cache_rows)

        # NEW: دسته‌ی اصلاح‌شده توسط AI روی محصول کانونیکال اعمال می‌شود
        if cat_updates:
            db.executemany("""
                UPDATE canonical_products SET category_std = ?, category_source = 'ai'
                WHERE canonical_key = ?;
            """, cat_updates)

        return {"processed": len(updates), "verified": verified_n, "rejected": rejected_n,
                "categories_fixed": len(cat_updates)}

    def run_review(self, max_batches: int = 4, batch_size: int = 25) -> Dict[str, Any]:
        """اجرای کامل: اول کش‌های رایگان، بعد API تا سقف max_batches."""
        result = {
            "groq_configured": groq_client.is_configured(),
            "cached_applied": 0,
            "batches_done": 0,
            "api_processed": 0,
            "api_verified": 0,
            "api_rejected": 0,
            "still_pending": 0,
            "rate_limit_waits": 0,
            "categories_fixed": 0,
            "errors": []
        }

        result["cached_applied"] = self.apply_cached_verdicts()
        consecutive_429 = 0
        _live("INFO", f"🤖 [AI] شروع بازبینی هوشمند — در صف: {self.count_pending()} | اعمال رایگان از کش: {result['cached_applied']}")

        if not result["groq_configured"]:
            result["still_pending"] = self.count_pending()
            result["errors"].append("کلید GROQ_API_KEY تنظیم نشده است — فقط کش‌های قبلی اعمال شد.")
            _live("WARNING", "⚠️ [AI] کلید Groq تنظیم نشده — فقط کش‌های قبلی اعمال شد")
            return result

        # NOTE: حلقه while (نه for) چون صبرکردن برای 429 نباید سهمیه‌ی
        # max_batches را مصرف کند — فقط دسته‌های موفق شمرده می‌شوند.
        batches_done = 0
        while batches_done < max_batches:
            batch = self.get_pending_listings(limit=batch_size)
            if not batch:
                break
            try:
                res = self.review_one_batch(batch)
                if res is None:
                    # NEW: 429 = محدودیت نرخ. پنجره‌ی سهمیه‌ی Groq ۶۰ ثانیه است؛
                    # ۶۵ ثانیه صبر یعنی سهمیه تازه شده. تا ۱۵ دور صبر می‌کنیم
                    # (~۱۶ دقیقه) تا یک درخواست واحد، کل صف را بدون دخالت انسان
                    # پیش ببرد؛ فقط بعد از آن پیام می‌دهد و می‌ایستد.
                    if groq_client.last_http_status == 429 and consecutive_429 < 15:
                        consecutive_429 += 1
                        result["rate_limit_waits"] = result.get("rate_limit_waits", 0) + 1
                        wait_s = 20 if consecutive_429 == 1 else 65
                        logger.info(
                            f"Groq rate limit (429, all keys) — wait {wait_s}s "
                            f"[{consecutive_429}/15] then retry same batch..."
                        )
                        _live("WARNING", f"⚠️ [AI] محدودیت نرخ Groq — {wait_s} ثانیه صبر و ادامه... [{consecutive_429}/15]")
                        time.sleep(wait_s)
                        continue
                    result["errors"].append(
                        "پاسخ نامعتبر از مدل"
                        + (" (محدودیت نرخ 429 پایدار — ۱-۲ دقیقه بعد دوباره اجرا کنید)" if groq_client.last_http_status == 429 else "")
                    )
                    break
                consecutive_429 = 0
                batches_done += 1
                result["batches_done"] = batches_done
                result["api_processed"] += res["processed"]
                result["api_verified"] += res["verified"]
                result["api_rejected"] += res["rejected"]
                result["categories_fixed"] = result.get("categories_fixed", 0) + res.get("categories_fixed", 0)
                _live("INFO", f"🤖 [AI] دسته {batches_done}: {res['processed']} تصمیم (تایید {res['verified']} / رد {res['rejected']}) — باقی‌مانده: {self.count_pending()}")
            except Exception as e:
                result["errors"].append(f"دسته {batches_done + 1}: {e}")
                break
            time.sleep(3)  # احترام به محدودیت نرخ رایگان Groq

        result["still_pending"] = self.count_pending()
        logger.info(f"AI review: {result['api_processed']} processed via API, "
                    f"{result['cached_applied']} from cache, {result['still_pending']} pending.")
        _live("SUCCESS", f"✅ [AI] پایان بازبینی: {result['api_processed']} تصمیم با Groq (تایید {result['api_verified']} / رد {result['api_rejected']}) | رایگان از کش: {result['cached_applied']} | باقی‌مانده در صف: {result['still_pending']}")
        return result

    def run_category_audit(self, max_batches: int = 4, batch_size: int = 25) -> Dict[str, Any]:
        """
        NEW: ممیزی دسته با AI — یک نماینده (آگهی با توضیحات) برای هر محصولی که
        هنوز دسته‌ی AI ندارد می‌رود به Groq و دسته‌ی استاندارد اصلاح می‌شود.
        دسته‌ی قاعده‌ای نقطه‌ی شروع است؛ AI با شواهد عنوان+توضیحات اصلاح می‌کند.
        """
        ensure_category_columns()
        result = {"batches_done": 0, "processed": 0, "categories_changed": 0, "errors": []}
        if not groq_client.is_configured():
            result["errors"].append("کلید Groq تنظیم نشده است.")
            return result

        for b in range(max_batches):
            # FIX: ممیزی فقط محصولات «بدون هیچ دسته‌ی ذخیره‌شده» را می‌گیرد —
            # دسته‌های rule/ai/manual همه معتبرند و manual (دستِ کاربر) مقدس است.
            rows = db.fetchall("""
                SELECT l.canonical_key, l.title_fa, l.description, l.price_toman,
                       c.category_std, c.category_key
                FROM store_listings l
                JOIN canonical_products c ON l.canonical_key = c.canonical_key
                WHERE l.is_verified = 1 AND COALESCE(c.category_source, '') = ''
                GROUP BY l.canonical_key
                LIMIT ?;
            """, (batch_size,))
            if not rows:
                break
            payload_items = [
                {"i": i, "title": r["title_fa"], "price_toman": r["price_toman"],
                 "current_category": r["category_std"] or r["category_key"] or "digital",
                 "desc": str(r.get("description") or "")[:280]}
                for i, r in enumerate(rows, start=1)
            ]
            user_prompt = (
                "Classify each listing into EXACTLY ONE standard category key: "
                "mobile, laptop, tablet, console, gpu, cpu, ram, storage, motherboard, "
                "desktop-pc, monitor, watch, headphone, other. "
                "The current_category may be WRONG — decide from title AND desc yourself.\n"
                'Respond ONLY as JSON: {"verdicts":[{"i":1,"category":"gpu"}, ...]}\n\n'
                + json.dumps(payload_items, ensure_ascii=False)
            )
            try:
                raw = groq_client.chat_json(
                    "You are a precise product taxonomy classifier for an Iranian marketplace. "
                    "Answer ONLY with valid JSON.",
                    user_prompt, max_tokens=1800,
                )
                if not raw or "verdicts" not in raw:
                    if groq_client.last_http_status == 429:
                        result["errors"].append("محدودیت نرخ (429) — بعداً ادامه دهید.")
                    break
                by_index = {}
                for v in raw["verdicts"]:
                    try:
                        by_index[int(v.get("i"))] = v
                    except (TypeError, ValueError):
                        continue
                changed = 0
                cat_updates = []
                for i, r in enumerate(rows, start=1):
                    v = by_index.get(i)
                    if not v:
                        continue
                    cat = str(v.get("category", "") or "").strip().lower()
                    if cat in STANDARD_CATEGORIES:
                        cat_updates.append((cat, r["canonical_key"]))
                        if cat != (r["category_std"] or ""):
                            changed += 1
                if cat_updates:
                    db.executemany("""
                        UPDATE canonical_products SET category_std = ?, category_source = 'ai'
                        WHERE canonical_key = ?;
                    """, cat_updates)
                result["batches_done"] += 1
                result["processed"] += len(cat_updates)
                result["categories_changed"] += changed
                _live("INFO", f"🗂️ [AI] ممیزی دسته بسته {result['batches_done']}: {len(cat_updates)} محصول، {changed} اصلاح")
            except Exception as e:
                result["errors"].append(f"دسته {b + 1}: {e}")
                break
            time.sleep(3)
        _live("SUCCESS", f"🗂️ [AI] ممیزی دسته انجام شد: {result['processed']} محصول دسته‌بندی AI گرفت ({result['categories_changed']} اصلاح)")
        return result

    def get_stats(self) -> Dict[str, Any]:
        pending = self.count_pending()
        cache_row = db.fetchone("SELECT COUNT(*) AS c FROM ai_review_cache;")
        ai_rej = db.fetchone(
            "SELECT COUNT(*) AS c FROM store_listings WHERE quality_status = 'AI_REJECTED';")
        ai_ver = db.fetchone(
            "SELECT COUNT(*) AS c FROM store_listings WHERE rejection_reason LIKE '🤖%';")
        try:
            ai_cat = db.fetchone("SELECT COUNT(*) AS c FROM canonical_products WHERE category_source = 'ai';")
            rule_cat = db.fetchone("SELECT COUNT(*) AS c FROM canonical_products WHERE category_source = 'rule';")
        except Exception:
            ai_cat = rule_cat = None
        return {
            "pending_review": pending,
            "products_ai_categorized": ai_cat["c"] if ai_cat else 0,
            "products_rule_categorized": rule_cat["c"] if rule_cat else 0,
            "cached_titles": cache_row["c"] if cache_row else 0,
            "ai_rejected_total": ai_rej["c"] if ai_rej else 0,
            "ai_verified_total": ai_ver["c"] if ai_ver else 0,
            "groq_configured": groq_client.is_configured(),
            "groq_keys_count": len(groq_client.api_keys),
            "groq_active_key": groq_client.masked_active_key(),
            "groq_model": groq_client.active_model,
            "groq_api_calls": groq_client.total_api_calls,
            "groq_tokens_used": groq_client.total_tokens_consumed
        }


ai_reviewer = AIBatchReviewer()
