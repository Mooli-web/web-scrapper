import os
import re
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Body
from pydantic import BaseModel
import requests

from database.db_manager import db
from core.arbitrage_engine import arbitrage_engine
from core.ai_dataset_generator import ai_exporter
from core.data_cleaner import data_purifier
from core.ai_reviewer import ai_reviewer
from core.ai_classifier import local_ai
from core.groq_client import groq_client
from core.crawler_injector import crawler_injector
from sync.master_sync import orchestrator
from sync.pull_cloud_databases import cloud_puller, LIVE_LOGS, push_live_log
from sync.ingest_torob import ingest_torob_items
from sync.auto_sync import auto_sync_scheduler

router = APIRouter(prefix="/api")

# High-Speed In-Memory Status Cache (TTL 4 seconds to prevent DB lock under polling)
STATUS_CACHE: Dict[str, Any] = {}
LAST_STATUS_TIME = 0.0

# NEW: کش تحلیل بازار (TTL 60s)
MARKET_OVERVIEW_CACHE: Dict[str, Any] = {}
MARKET_OVERVIEW_TIME = 0.0

# NEW: جعبه‌سیاه برچسب‌ها — هر عملیات با منبع و زمان ثبت می‌شود تا هر اتفاق
# آینده قابل ردیابی باشد (incident forensics).
def _audit_log(source: str, action: str, ids, category: str = "", reason: str = ""):
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS label_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT, action TEXT, ids_count INTEGER,
                category TEXT, reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        db.execute("""INSERT INTO label_audit_log (source, action, ids_count, category, reason)
                      VALUES (?, ?, ?, ?, ?);""",
                   (str(source)[:40], str(action)[:30], len(ids or []), str(category)[:40], str(reason)[:120]))
    except Exception:
        pass

# NEW: بازمحاسبه‌ی تأخیری — با هر کلیکِ لیبل‌زنی، چرخه‌ی سنگین (پالایش کامل +
# آربیتراژ + اکسپورت) هم‌زمان اجرا نمی‌شود؛ فقط یک‌بار، چند ثانیه بعد از آخرین عملیات.
_RECOMPUTE_TIMER = None

def _schedule_recompute(delay_sec: float = 6.0):
    global _RECOMPUTE_TIMER
    import threading

    def _run():
        try:
            data_purifier.run_full_purification_pipeline()
            arbitrage_engine.run_arbitrage_scan()
            ai_exporter.export_all()
            push_live_log("INFO", "🧮 [لیبل‌زنی] بازمحاسبه‌ی پس‌پردازش انجام شد (پالایش/آربیتراژ/دیتاست)")
        except Exception as e:
            push_live_log("WARNING", f"🧮 [لیبل‌زنی] بازمحاسبه خطا: {e}")

    if _RECOMPUTE_TIMER:
        _RECOMPUTE_TIMER.cancel()
    _RECOMPUTE_TIMER = threading.Timer(delay_sec, _run)
    _RECOMPUTE_TIMER.daemon = True
    _RECOMPUTE_TIMER.start()

class IngestBatchRequest(BaseModel):
    digikala_items: Optional[List[Dict[str, Any]]] = None
    torob_items: Optional[List[Dict[str, Any]]] = None
    divar_items: Optional[List[Dict[str, Any]]] = None
    esam_items: Optional[List[Dict[str, Any]]] = None

class SettingsUpdateRequest(BaseModel):
    digikala_render_url: Optional[str] = ""
    divar_render_url: Optional[str] = ""
    esam_render_url: Optional[str] = ""
    torob_local_path: Optional[str] = ""

class GroqKeyPayload(BaseModel):
    groq_api_key: str
    model: Optional[str] = "openai/gpt-oss-20b"

# --- 1. Fast In-Memory Cached Status & Logs ---

@router.get("/status")
def get_hub_status():
    global STATUS_CACHE, LAST_STATUS_TIME
    now = time.time()

    if STATUS_CACHE and (now - LAST_STATUS_TIME < 4.0):
        return STATUS_CACHE

    r_prod = db.fetchone("SELECT count(*) as c FROM canonical_products;")
    r_list = db.fetchone("SELECT count(*) as c, COUNT(CASE WHEN is_verified = 1 THEN 1 END) as verified_count FROM store_listings;")
    r_arb = db.fetchone("SELECT count(*) as c, COALESCE(SUM(profit_spread_toman), 0) as total_profit FROM arbitrage_opportunities;")
    r_golden = db.fetchone("SELECT count(*) as c FROM arbitrage_opportunities WHERE deal_type = 'GOLDEN_FLIP';")

    store_counts = db.fetchall("SELECT store_key, count(*) as count, COUNT(CASE WHEN is_verified = 1 THEN 1 END) as ver_count FROM store_listings GROUP BY store_key;")
    store_map = {r['store_key']: r['count'] for r in store_counts}
    store_ver_map = {r['store_key']: r['ver_count'] for r in store_counts}

    total_listings = r_list['c'] if r_list else 0
    verified_listings = r_list['verified_count'] if r_list else 0

    STATUS_CACHE = {
        "status": "online",
        "platform": "Quad-Market Unified Commodity Intelligence Hub",
        "database": "Local SQLite Master DB (data/market.db)",
        "total_canonical_products": r_prod['c'] if r_prod else 0,
        "total_store_listings": total_listings,
        "verified_clean_listings": verified_listings,
        "data_purity_percent": round((verified_listings / total_listings) * 100.0, 1) if total_listings > 0 else 100.0,
        "total_arbitrage_deals": r_arb['c'] if r_arb else 0,
        "golden_flips_count": r_golden['c'] if r_golden else 0,
        "total_profit_potential_toman": r_arb['total_profit'] if r_arb else 0,
        "store_breakdown": {
            "digikala": store_map.get("digikala", 0),
            "torob": store_map.get("torob", 0),
            "divar": store_map.get("divar", 0),
            "esam": store_map.get("esam", 0)
        },
        "store_verified_breakdown": {
            "digikala": store_ver_map.get("digikala", 0),
            "torob": store_ver_map.get("torob", 0),
            "divar": store_ver_map.get("divar", 0),
            "esam": store_ver_map.get("esam", 0)
        }
    }
    LAST_STATUS_TIME = now
    return STATUS_CACHE

@router.get("/sync/logs")
def get_sync_logs(after_id: int = 0):
    new_logs = [l for l in LIVE_LOGS if l["id"] > after_id]
    return {"logs": new_logs, "total": len(LIVE_LOGS)}

@router.get("/sync/scheduler")
def get_scheduler_status():
    """NEW: وضعیت چرخه‌ی خودکار (سینک + پالایش + AI + آربیتراژ)."""
    return auto_sync_scheduler.status()

@router.post("/sync/scheduler")
def update_scheduler(payload: Dict[str, Any] = Body(...)):
    """
    NEW: تغییر تنظیمات زمان‌بند بدون ری‌استارت، یا اجرای فوری یک چرخه.
    بدنه: {"enabled": true/false} یا {"interval_minutes": 120} یا {"daily_at": "08:30"}
    یا {"run_now": true} — چرخه‌ی فوری در نخ جدا اجرا می‌شود.
    """
    from threading import Thread
    if payload.get("run_now"):
        Thread(target=auto_sync_scheduler.run_cycle, kwargs={"reason": "دستی (API)"}, daemon=True).start()
        return {"status": "started", "message": "چرخه‌ی خودکار در پس‌زمینه آغاز شد — کنسول داشبورد را ببینید."}
    ok = auto_sync_scheduler.apply_settings(payload)
    if not ok:
        raise HTTPException(status_code=400, detail="مقدار تنظیم نامعتبر است (interval_minutes>=30 یا daily_at به شکل HH:MM)")
    return {"status": "success", "scheduler": auto_sync_scheduler.status()}

@router.get("/sync/diagnostics")
def get_sync_diagnostics():
    """
    FIX: the dashboard's Diagnostics tab calls /api/sync/diagnostics, but this
    endpoint was never defined (404). It now exposes CloudDataPuller.get_diagnostics().
    """
    return cloud_puller.get_diagnostics()

# --- 2. Live Source Probes (100% Transparent Connection & Sample Inspector) ---

@router.get("/sources/live-probes")
def get_live_source_probes():
    """
    Sends live test probes to Digikala, Divar, Esam Render web services and Torob local file.
    Returns status, latency, total available count, AND 3 real live samples with image and direct link!
    """
    cloud_puller.reload_config()
    probes = {}

    # 1. Digikala Probe
    if cloud_puller.digikala_render_url and cloud_puller.digikala_render_url.startswith("http"):
        t0 = time.perf_counter()
        token = cloud_puller._get_auth_token(cloud_puller.digikala_render_url)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            r = requests.get(f"{cloud_puller.digikala_render_url}/api/products?page_size=3&page=1", headers=headers, timeout=10)
            latency = round((time.perf_counter() - t0) * 1000, 1)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items") or data.get("products") or []
                total = data.get("total") or len(items)
                samples = []
                for it in items[:3]:
                    p_id = it.get("product_id") or it.get("id")
                    samples.append({
                        "title": it.get("title_fa") or it.get("title"),
                        "price": it.get("selling_price_toman") or it.get("selling_price") or it.get("price"),
                        "url": it.get("product_url") or f"https://www.digikala.com/product/dkp-{p_id}",
                        "image_url": it.get("image_url")
                    })
                probes["digikala"] = {
                    "status": "online",
                    "url": cloud_puller.digikala_render_url,
                    "latency_ms": latency,
                    "total_available": total,
                    "samples": samples
                }
            else:
                probes["digikala"] = {"status": "error", "http_code": r.status_code, "error": r.text[:150], "samples": []}
        except Exception as e:
            probes["digikala"] = {"status": "error", "error": str(e), "samples": []}
    else:
        probes["digikala"] = {"status": "not_configured", "error": "آدرس رندر دیجی‌کالا در تنظیمات وارد نشده است.", "samples": []}

    # 2. Divar Probe
    if cloud_puller.divar_render_url and cloud_puller.divar_render_url.startswith("http"):
        t0 = time.perf_counter()
        token = cloud_puller._get_auth_token(cloud_puller.divar_render_url)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            r = requests.get(f"{cloud_puller.divar_render_url}/api/posts?page_size=3&page=1", headers=headers, timeout=10)
            latency = round((time.perf_counter() - t0) * 1000, 1)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items") or data.get("posts") or []
                total = data.get("total") or len(items)
                samples = []
                for it in items[:3]:
                    t_id = it.get("token") or it.get("item_id")
                    samples.append({
                        "title": it.get("title_fa") or it.get("title"),
                        "price": it.get("selling_price_toman") or it.get("selling_price") or it.get("price"),
                        "url": it.get("post_url") or f"https://divar.ir/v/{t_id}",
                        "image_url": it.get("image_url"),
                        "district": it.get("district") or it.get("city") or "تهران"
                    })
                probes["divar"] = {
                    "status": "online",
                    "url": cloud_puller.divar_render_url,
                    "latency_ms": latency,
                    "total_available": total,
                    "samples": samples
                }
            else:
                probes["divar"] = {"status": "error", "http_code": r.status_code, "error": r.text[:150], "samples": []}
        except Exception as e:
            probes["divar"] = {"status": "error", "error": str(e), "samples": []}
    else:
        probes["divar"] = {"status": "not_configured", "error": "آدرس رندر دیوار در تنظیمات وارد نشده است.", "samples": []}

    # 3. Esam Probe
    if cloud_puller.esam_render_url and cloud_puller.esam_render_url.startswith("http"):
        t0 = time.perf_counter()
        try:
            r = requests.get(f"{cloud_puller.esam_render_url}/api/esam/items?limit=3&offset=0", timeout=10)
            latency = round((time.perf_counter() - t0) * 1000, 1)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items") or []
                total = data.get("total") or len(items)
                samples = []
                for it in items[:3]:
                    samples.append({
                        "title": it.get("title_fa") or it.get("title"),
                        "price": it.get("selling_price_toman") or it.get("price"),
                        "url": it.get("url") or "https://esam.ir",
                        "image_url": it.get("image_url")
                    })
                probes["esam"] = {
                    "status": "online",
                    "url": cloud_puller.esam_render_url,
                    "latency_ms": latency,
                    "total_available": total,
                    "samples": samples
                }
            else:
                probes["esam"] = {"status": "error", "http_code": r.status_code, "error": r.text[:150], "samples": []}
        except Exception as e:
            probes["esam"] = {"status": "error", "error": str(e), "samples": []}
    else:
        probes["esam"] = {"status": "not_configured", "error": "آدرس رندر ایسام در تنظیمات وارد نشده است.", "samples": []}

    # 4. Torob Probe
    torob_items, torob_source = cloud_puller.pull_torob_items()
    samples_torob = []
    for it in torob_items[:3]:
        samples_torob.append({
            "title": it.get("title") or it.get("name1") or it.get("title_fa"),
            "price": it.get("price") or it.get("selling_price_toman"),
            "url": it.get("url") or it.get("more_info_url") or "https://torob.com",
            "image_url": it.get("image_url") or it.get("image")
        })
    probes["torob"] = {
        "status": "online" if torob_items else "missing",
        "source": torob_source,
        "total_available": len(torob_items),
        "samples": samples_torob
    }

    return probes

# --- 3. Data Audit & Quality Verification ---

@router.post("/audit/run-purification")
def run_data_purification():
    """Runs the purification pipeline: keyword/regex blacklist + price-floor rules +
    reference-price deviation checks, then rescans arbitrage and re-exports AI datasets.
    Flagged (rejected) items are exported to exports/audit_review_for_agent.json
    for optional Agent review via /api/audit/apply-agent-decisions."""
    purify_res = data_purifier.run_full_purification_pipeline()
    arb_res = arbitrage_engine.run_arbitrage_scan()
    ai_exporter.export_all()
    
    global LAST_STATUS_TIME
    LAST_STATUS_TIME = 0.0 # Clear cache
    return {
        "status": "completed",
        "purification": purify_res,
        "arbitrage": arb_res
    }

@router.get("/audit/quality-report")
def get_quality_report():
    r_total = db.fetchone("SELECT count(*) as c, COUNT(CASE WHEN is_verified = 1 THEN 1 END) as ver_c FROM store_listings;")
    counts_by_status = db.fetchall("""
        SELECT quality_status, count(*) as cnt
        FROM store_listings
        GROUP BY quality_status;
    """)
    status_map = {r['quality_status']: r['cnt'] for r in counts_by_status}

    total = r_total['c'] if r_total else 0
    verified = r_total['ver_c'] if r_total else 0

    return {
        "total_listings": total,
        "verified_clean": verified,
        "rejected_noise": total - verified,
        "purity_percentage": round((verified / total) * 100.0, 1) if total > 0 else 100.0,
        "breakdown": {
            "verified": status_map.get("VERIFIED", 0),
            "accessory_or_junk": status_map.get("ACCESSORY_OR_JUNK", 0),
            "defective_parts": status_map.get("DEFECTIVE_PARTS", 0),
            "fake_price": status_map.get("FAKE_PRICE", 0),
            "statistical_outlier": status_map.get("STATISTICAL_OUTLIER", 0),
            "needs_ai_review": status_map.get("NEEDS_AI_REVIEW", 0),
            "ai_rejected": status_map.get("AI_REJECTED", 0),
            "rejected_by_agent": status_map.get("REJECTED_BY_AGENT", 0)
        }
    }

@router.post("/audit/ai-review")
def run_ai_review(payload: Dict[str, Any] = Body(default=None)):
    """
    NEW: runs the AI review layer (Groq) on NEEDS_AI_REVIEW listings.
    Body (optional): {"max_batches": 4, "batch_size": 25}
    Cached titles are re-applied for free; then up to max_batches API calls run.
    """
    payload = payload or {}
    try:
        max_batches = max(1, min(int(payload.get("max_batches", 4)), 50))
    except (TypeError, ValueError):
        max_batches = 4
    try:
        batch_size = max(5, min(int(payload.get("batch_size", 25)), 50))
    except (TypeError, ValueError):
        batch_size = 25

    res = ai_reviewer.run_review(max_batches=max_batches, batch_size=batch_size)

    # اگر حتی یک تصمیم جدید اعمال شد، آمار وابسته بازمحاسبه شود
    if res.get("api_processed") or res.get("cached_applied"):
        arbitrage_engine.run_arbitrage_scan()
        ai_exporter.export_all()

    global LAST_STATUS_TIME
    LAST_STATUS_TIME = 0.0
    res["stats"] = ai_reviewer.get_stats()
    return res

@router.get("/audit/ai-stats")
def get_ai_review_stats():
    """NEW: AI review layer stats (pending/cache/tokens) without running a review."""
    return ai_reviewer.get_stats()

@router.get("/audit/purification-stats")
def get_purification_stats():
    """
    NEW: آمار کامل سه‌لایه‌ی پالایش — کالاهای موجود / بررسی لوکال / بررسی AI
    (+ بازبینی ایجنت و وضعیت کلیدهای Groq).
    """
    total = (db.fetchone("SELECT COUNT(*) AS c FROM store_listings;") or {}).get("c", 0)
    by_status = {r["quality_status"]: r["cnt"] for r in db.fetchall(
        "SELECT quality_status, COUNT(*) AS cnt FROM store_listings GROUP BY quality_status;")}

    ai_verified = (db.fetchone(
        "SELECT COUNT(*) AS c FROM store_listings WHERE quality_status='VERIFIED' AND rejection_reason LIKE '🤖%';"
    ) or {}).get("c", 0)
    agent_verified = (db.fetchone(
        "SELECT COUNT(*) AS c FROM store_listings WHERE quality_status='VERIFIED' AND rejection_reason LIKE '%Agent%';"
    ) or {}).get("c", 0)
    verified_total = by_status.get("VERIFIED", 0)
    local_verified = max(0, verified_total - ai_verified - agent_verified)

    local_rejected = {
        "accessory_or_junk": by_status.get("ACCESSORY_OR_JUNK", 0),
        "defective_parts": by_status.get("DEFECTIVE_PARTS", 0),
        "fake_price": by_status.get("FAKE_PRICE", 0),
        "statistical_outlier": by_status.get("STATISTICAL_OUTLIER", 0),
    }
    local_rejected_total = sum(local_rejected.values())

    ai_rejected = by_status.get("AI_REJECTED", 0)
    ai_pending = by_status.get("NEEDS_AI_REVIEW", 0)
    cached_titles = (db.fetchone("SELECT COUNT(*) AS c FROM ai_review_cache;") or {}).get("c", 0)

    def pct(n):
        return round((n / total) * 100.0, 1) if total else 0.0

    return {
        "total_listings": total,
        "local_review": {
            "verified": local_verified,
            "rejected": local_rejected,
            "rejected_total": local_rejected_total,
            "total": local_verified + local_rejected_total,
            "coverage_percent": pct(local_verified + local_rejected_total),
        },
        "ai_review": {
            "verified": ai_verified,
            "rejected": ai_rejected,
            "total_decided": ai_verified + ai_rejected,
            "pending": ai_pending,
            "cached_titles": cached_titles,
            "coverage_percent": pct(ai_verified + ai_rejected + ai_pending),
        },
        "agent_review": {
            "verified": agent_verified,
            "rejected": by_status.get("REJECTED_BY_AGENT", 0),
        },
        "groq": {
            "configured": groq_client.is_configured(),
            "keys_count": len(groq_client.api_keys),
            "active_key_masked": groq_client.masked_active_key(),
            "model": groq_client.active_model,
            "api_calls": groq_client.total_api_calls,
            "tokens_used": groq_client.total_tokens_consumed,
        },
    }

@router.post("/audit/confirm-junk")
def confirm_junk_items(payload: Dict[str, Any] = Body(...)):
    """
    NEW: تأیید کاربر که آگهی‌های انتخاب‌شده چرت‌اند + یادگیری الگو.
    بلافاصله پالایش مجدد اجرا می‌شود تا مشابه‌ها هم با الگوهای تازه حذف شوند.
    """
    ids = payload.get("ids") or []
    _audit_log(payload.get("source", "api"), "junk", ids, reason=str(payload.get("reason", "") or ""))
    res = data_purifier.confirm_junk(ids, reason=str(payload.get("reason", "") or ""))
    if res["confirmed"]:
        _schedule_recompute()  # FIX: بازمحاسبه‌ی سنگین تأخیری — پاسخ فوری
        global LAST_STATUS_TIME
        LAST_STATUS_TIME = 0.0
    res["signals"] = data_purifier.list_learned_signals()
    return res

@router.get("/audit/learned-signals")
def get_learned_signals():
    """NEW: فهرست الگوهای آموخته‌شده از تأیید کاربر."""
    return {"signals": data_purifier.list_learned_signals()}

@router.delete("/audit/learned-signals/{signal_id}")
def delete_learned_signal(signal_id: int):
    """NEW: حذف یک الگوی آموخته‌شده (اگر اشتباه بود)."""
    ok = data_purifier.remove_learned_signal(signal_id)
    return {"status": "success" if ok else "not_found", "signal_id": signal_id}

@router.get("/audit/agent-batch")
def get_agent_audit_batch():
    """Returns the flagged batch file for Agent review."""
    batch_file = Path(__file__).resolve().parent.parent / "exports" / "audit_review_for_agent.json"
    if batch_file.exists():
        with open(batch_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"total_flagged": 0, "items": []}

@router.post("/audit/apply-agent-decisions")
def apply_agent_decisions(payload: Union[List[Dict[str, Any]], Dict[str, Any]] = Body(...)):
    """Applies Agent verified decisions into local SQLite database."""
    # FIX: previously typed strictly as Dict — a bare JSON list payload (a valid
    # format per the documented contract) was rejected with a 422 error.
    if isinstance(payload, list):
        decisions = payload
    else:
        decisions = payload.get("decisions") or payload.get("items") or []
    count = data_purifier.apply_agent_decisions(decisions)
    arbitrage_engine.run_arbitrage_scan()
    ai_exporter.export_all()
    return {"status": "success", "decisions_applied": count, "message": f"✅ {count} تصمیم Agent با موفقیت در دیتابیس اعمال و ذخیره شد."}

@router.get("/audit/samples")
def get_audit_samples(limit: int = 25):
    clean_samples = db.fetchall("""
        SELECT id, title_fa, store_key, price_toman, condition, quality_status, rejection_reason, confidence_score, url
        FROM store_listings
        WHERE is_verified = 1
        ORDER BY RANDOM()
        LIMIT ?;
    """, (limit,))

    rejected_samples = db.fetchall("""
        SELECT id, title_fa, store_key, price_toman, condition, quality_status, rejection_reason, confidence_score, url
        FROM store_listings
        WHERE is_verified = 0
        ORDER BY RANDOM()
        LIMIT ?;
    """, (limit,))

    return {
        "verified_clean": clean_samples,
        "rejected_anomalies": rejected_samples
    }

# --- 4. Diagnostics & Settings ---

@router.post("/settings/save")
def save_settings(req: SettingsUpdateRequest):
    env_file = Path(".env")
    if not env_file.exists():
        env_file = Path(__file__).resolve().parent.parent / ".env"

    # FIX: previously this rewrote the whole .env and WIPED every key that is
    # not part of the settings form (GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL,
    # RENDER_ADMIN_*...). Now existing keys are preserved and only the four
    # source URLs (and PORT, if absent) are updated.
    existing: Dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    existing["DIGIKALA_RENDER_URL"] = req.digikala_render_url or ""
    existing["DIVAR_RENDER_URL"] = req.divar_render_url or ""
    existing["ESAM_RENDER_URL"] = req.esam_render_url or ""
    existing["TOROB_LOCAL_PATH"] = req.torob_local_path or ""
    existing.setdefault("PORT", "7000")

    content = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    with open(env_file, "w", encoding="utf-8") as f:
        f.write(content)

    cloud_puller.reload_config()
    return {"status": "saved", "message": "تنظیمات با موفقیت ذخیره شد."}

# --- 5. Arbitrage Deals Ledger (Strictly Verified & Non-Repeating) ---

@router.get("/arbitrage/deals")
def get_arbitrage_deals(
    deal_type: Optional[str] = None,
    source_store: Optional[str] = None,
    min_discount: float = Query(0.0, ge=0.0, le=100.0),
    sort_by: str = Query("discount_percent", pattern="^(discount_percent|profit_spread_toman|buy_price_toman|detected_at|title_fa)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    where = ["discount_percent >= ?"]
    params = [min_discount]

    if deal_type and deal_type != "all":
        where.append("deal_type = ?")
        params.append(deal_type)

    if source_store and source_store != "all":
        where.append("source_store = ?")
        params.append(source_store)

    where_sql = " AND ".join(where)
    order_sql = f"ORDER BY {sort_by} {sort_order.upper()}"

    count_row = db.fetchone(f"SELECT count(*) as c FROM arbitrage_opportunities WHERE {where_sql};", tuple(params))
    total = count_row['c'] if count_row else 0

    deals = db.fetchall(f"""
        SELECT *
        FROM arbitrage_opportunities
        WHERE {where_sql}
        {order_sql}
        LIMIT ? OFFSET ?;
    """, tuple(params + [limit, offset]))

    return {"deals": deals, "total": total, "limit": limit, "offset": offset}

# --- 6. Canonical 4-Way Comparison Products Ledger ---

@router.get("/canonical/products")
def get_canonical_products(
    search: Optional[str] = None,
    brand: Optional[str] = None,
    sort_by: str = Query("torob_min_price_toman", pattern="^(torob_min_price_toman|digikala_price_toman|divar_min_price_toman|esam_min_price_toman|depreciation_percent|last_synced_at|title_fa)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    where = ["1=1"]
    params = []

    if search:
        where.append("(title_fa LIKE ? OR canonical_key LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if brand and brand != "all":
        where.append("brand = ?")
        params.append(brand)

    where_sql = " AND ".join(where)
    order_sql = f"ORDER BY {sort_by} {sort_order.upper()}"

    c_row = db.fetchone(f"SELECT count(*) as c FROM canonical_products WHERE {where_sql};", tuple(params))
    total = c_row['c'] if c_row else 0

    products = db.fetchall(f"""
        SELECT *
        FROM canonical_products
        WHERE {where_sql}
        {order_sql}
        LIMIT ? OFFSET ?;
    """, tuple(params + [limit, offset]))

    return {"products": products, "total": total, "limit": limit, "offset": offset}

# --- 7. Depreciation Analytics ---

@router.get("/analytics/market-overview")
def get_market_overview():
    """
    NEW: تحلیل آماری پایه بر پایه‌ی دسته‌بندی یکپارچه (taxonomy).
    برای هر دسته‌ی استاندارد: تعداد محصول/آگهی تاییدشده، میانه‌ی قیمت نو (ترب/دیجی‌کالا)
    و دست‌دوم (دیوار/ایسام)، شکاف نو/دست‌دوم، استهلاک، بازه قیمت و برندهای برتر.
    کش ۶۰ ثانیه‌ای برای جلوگیری از فشار به دیتابیس.
    """
    global MARKET_OVERVIEW_CACHE, MARKET_OVERVIEW_TIME
    now = time.time()
    if MARKET_OVERVIEW_CACHE and (now - MARKET_OVERVIEW_TIME) < 60:
        return MARKET_OVERVIEW_CACHE

    from core.taxonomy import normalize_category, STANDARD_CATEGORIES

    products = db.fetchall("""
        SELECT canonical_key, title_fa, brand, category_key, category_std,
               digikala_price_toman, torob_min_price_toman,
               divar_avg_price_toman, esam_avg_price_toman, depreciation_percent
        FROM canonical_products;
    """)
    listings = db.fetchall("""
        SELECT canonical_key, store_key, price_toman
        FROM store_listings WHERE is_verified = 1 AND price_toman > 0;
    """)

    key_to_std = {}
    cats: Dict[str, Dict[str, Any]] = {k: {
        "key": k, "label": v, "products": 0, "listings": 0,
        "new_prices": [], "used_prices": [], "all_prices": [],
        "dep": [], "brands": {}
    } for k, v in STANDARD_CATEGORIES.items()}

    def median(vals):
        vs = sorted(v for v in vals if v)
        if not vs:
            return 0
        n = len(vs)
        m = n // 2
        return vs[m] if n % 2 else int((vs[m-1] + vs[m]) / 2)

    # FIX: فقط «محصولات فعال» (دارای حداقل یک آگهی تاییدشده) شمرده می‌شوند —
    # آگهی‌های چرت محصولِ بی‌صاحب (زامبی) می‌سازند و آمار را متورم می‌کردند
    # (نمونه: متفرقه ۳,۳۵۱ محصول با فقط ۲۸ آگهی).
    active_keys = {l["canonical_key"] for l in listings}
    inactive_products = 0
    for p in products:
        std = (p.get("category_std") or "").strip()
        if std not in STANDARD_CATEGORIES:
            std = normalize_category(p["category_key"], p["title_fa"] or "")
        if p["canonical_key"] not in active_keys:
            inactive_products += 1
            continue  # محصول زامبی — در تحلیل بازار شمرده نمی‌شود
        key_to_std[p["canonical_key"]] = std
        c = cats[std]
        c["products"] += 1
        new_ref = p["torob_min_price_toman"] or p["digikala_price_toman"] or 0
        if new_ref:
            c["new_prices"].append(new_ref)
        used = p["divar_avg_price_toman"] or p["esam_avg_price_toman"] or 0
        if used:
            c["used_prices"].append(used)
        if p["depreciation_percent"]:
            c["dep"].append(float(p["depreciation_percent"]))
        b = (p["brand"] or "other")
        c["brands"][b] = c["brands"].get(b, 0) + 1

    for l in listings:
        std = key_to_std.get(l["canonical_key"])
        if std and std in cats:
            cats[std]["listings"] += 1
            cats[std]["all_prices"].append(l["price_toman"])

    out_cats = []
    for c in cats.values():
        if c["products"] == 0:
            continue
        new_med = median(c["new_prices"])
        used_med = median(c["used_prices"])
        out_cats.append({
            "key": c["key"], "label": c["label"],
            "products": c["products"], "listings": c["listings"],
            "new_price_median": new_med,
            "used_price_median": used_med,
            "new_used_gap_percent": round(((new_med - used_med) / new_med) * 100.0, 1) if (new_med and used_med) else 0,
            "depreciation_avg": round(sum(c["dep"]) / len(c["dep"]), 1) if c["dep"] else 0,
            "price_min": min(c["all_prices"]) if c["all_prices"] else 0,
            "price_max": max(c["all_prices"]) if c["all_prices"] else 0,
            "top_brands": [
                {"brand": b, "products": n}
                for b, n in sorted(c["brands"].items(), key=lambda x: -x[1])[:5]
            ],
        })
    out_cats.sort(key=lambda x: -x["products"])

    total_listings = sum(c["listings"] for c in out_cats)
    MARKET_OVERVIEW_CACHE = {
        "generated_at": db.fetchone("SELECT CURRENT_TIMESTAMP as now;")["now"],
        "total_products": len(active_keys),
        "inactive_products_excluded": inactive_products,
        "total_verified_listings": total_listings,
        "categories": out_cats,
    }
    MARKET_OVERVIEW_TIME = now
    return MARKET_OVERVIEW_CACHE

# NEW: الگوی SQL مشترکِ «تایید انسانی» — هم برای شمارنده هم برای پرچم ردیف‌ها
_HUMAN_REASON_SQL = ("(l.rejection_reason LIKE '\u272b%' OR l.rejection_reason LIKE '%تائید%شما%' "
                 "OR l.rejection_reason LIKE '%تأیید%شما%' OR l.rejection_reason LIKE '%تایید%شما%')")

@router.get("/analytics/category-products")
def get_category_products(
    category: str = Query(..., min_length=1),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    hide_verified: bool = Query(True),
    sort: str = Query("alpha", pattern="^(price|newest|alpha)$")
):
    """
    NEW: آگهی‌های تاییدشده‌ی یک دسته‌ی استاندارد (برای نمای دریل‌داون داشبورد).
    """
    # FIX: صفحه‌بندی مستقیم روی آگهی‌های تاییدشده — قبلاً ۱۰۰ محصول اول انتخاب
    # می‌شد و اگر آگهی تاییدشده نداشتند لیست تقریباً خالی برمی‌گشت.
    ensure_stmt = "SELECT COUNT(*) AS c FROM canonical_products WHERE COALESCE(category_std,'') != ''"
    # NEW: category=all → صفِ همه‌ی دسته‌ها (میز بررسی) + نمایش دسته‌ی هر ردیف
    is_all = (category.lower() == "all")
    if is_all:
        where_cat = "1=1"
        params_cat = ()
    else:
        has_std = (db.fetchone(ensure_stmt) or {"c": 0})["c"] > 0
        where_cat = "COALESCE(c.category_std, '') = ?" if has_std else "1=0"
        params_cat = (category,) if has_std else ()

    # NEW: شمارنده‌ی تاییدهای انسانی (✋) — متر پیشرفت لیبل‌زنی
    cnt = db.fetchone(f"""
        SELECT COUNT(*) AS listings, COUNT(DISTINCT l.canonical_key) AS products,
               COUNT(CASE WHEN {_HUMAN_REASON_SQL} THEN 1 END) AS human_listings,
               COUNT(DISTINCT CASE WHEN {_HUMAN_REASON_SQL} THEN l.canonical_key END) AS human_products,
               COUNT(CASE WHEN {_HUMAN_REASON_SQL} THEN 1 END) AS reviewed_listings
        FROM store_listings l JOIN canonical_products c ON l.canonical_key = c.canonical_key
        WHERE l.is_verified = 1 AND l.price_toman > 0 AND {where_cat};
    """, params_cat) or {"listings": 0, "products": 0, "human_listings": 0, "human_products": 0}

    # NEW: پنهان‌سازی سرور-ساید — نمای پیش‌فرض فقط «باقی‌مانده‌ها» است تا
    # صفحه‌ی ۱ همیشه پر از کار بررسی‌نشده باشد (قبلاً CSS مخفی می‌کرد و
    # صفحه‌ها نیمه‌خالی می‌ماندند). تیکِ نمایش → همه با نشان ✋✓ می‌آیند.
    view_filter = f" AND NOT {_HUMAN_REASON_SQL}" if hide_verified else ""
    listings_view = cnt["listings"] or 0
    if hide_verified:
        vc = db.fetchone(f"""
            SELECT COUNT(*) AS listings
            FROM store_listings l JOIN canonical_products c ON l.canonical_key = c.canonical_key
            WHERE l.is_verified = 1 AND l.price_toman > 0 AND {where_cat}{view_filter};
        """, params_cat)
        listings_view = (vc["listings"] if vc else 0) or 0

    junk_row = db.fetchone(f"""
        SELECT COUNT(*) AS c
        FROM store_listings l JOIN canonical_products c ON l.canonical_key = c.canonical_key
        WHERE l.quality_status = 'CONFIRMED_JUNK' AND {where_cat};
    """, params_cat)
    junk_cnt = (junk_row["c"] if junk_row else 0) or 0

    items = db.fetchall(f"""
        SELECT l.id, l.title_fa, l.price_toman, l.store_key, l.condition, l.url,
               l.quality_status, l.image_url, c.brand,
               CASE WHEN {_HUMAN_REASON_SQL} THEN 1 ELSE 0 END AS is_human_verified,
               COALESCE(NULLIF(c.category_std, ''), c.category_key, '') AS item_category
        FROM store_listings l JOIN canonical_products c ON l.canonical_key = c.canonical_key
        WHERE l.is_verified = 1 AND l.price_toman > 0 AND {where_cat}{view_filter}
        ORDER BY {("l.price_toman DESC" if sort == "price" else "l.id DESC" if sort == "newest" else "l.title_fa COLLATE NOCASE ASC")}
        LIMIT ? OFFSET ?;
    """, params_cat + (limit, offset))
    return {"api_build": "human-counters-v6",
            "total": cnt["products"],               # همه‌ی محصولاتِ دارای آگهی تاییدشده
            "listings_total": listings_view,        # شمارشِ نمای فعال (باقی‌مانده‌ها یا همه)
            "listings_all": cnt["listings"] or 0,   # کل — برای نمایش هنگام تیکِ نمایش همه
            "human_verified_products": cnt["human_products"] or 0,
            "human_verified_listings": cnt["human_listings"] or 0,
            "human_reviewed_listings": ((cnt["reviewed_listings"] or 0) + junk_cnt),
            "hide_verified": hide_verified, "sort": sort,
            "category": category, "items": items}

@router.post("/audit/category-audit")
def run_category_audit(payload: Dict[str, Any] = Body(default=None)):
    """
    NEW: ممیزی دسته با AI — محصولاتِ هنوز-دسته‌گرفته-نشده با AI، همراه توضیحات،
    دسته‌بندی/اصلاح می‌شوند. بدنه اختیاری: {"max_batches": 4, "batch_size": 25}
    """
    payload = payload or {}
    try:
        mb = max(1, min(int(payload.get("max_batches", 4)), 100))
    except (TypeError, ValueError):
        mb = 4
    try:
        bs = max(5, min(int(payload.get("batch_size", 25)), 50))
    except (TypeError, ValueError):
        bs = 25
    res = ai_reviewer.run_category_audit(max_batches=mb, batch_size=bs)
    global LAST_STATUS_TIME
    LAST_STATUS_TIME = 0.0
    res["stats"] = ai_reviewer.get_stats()
    return res

@router.post("/audit/bulk-action")
def bulk_listing_action(payload: Dict[str, Any] = Body(...)):
    """
    NEW: عملیات گروهی روی آگهی‌های انتخاب‌شده‌ی یک دسته:
      {"ids": [1,2,3], "action": "junk"|"verify"|"set-category", "category": "gpu"}
    - junk: حذف چرت + یادگیری الگوی exact-title
    - verify: تایید انسانی + قفل
    - set-category: دسته‌ی دستی (manual) روی محصول کانونیکال همه‌ی آگهی‌ها
    """
    from core.taxonomy import ensure_category_columns, STANDARD_CATEGORIES
    global LAST_STATUS_TIME, MARKET_OVERVIEW_CACHE, MARKET_OVERVIEW_TIME
    ids = [i for i in (payload.get("ids") or []) if isinstance(i, int) and not isinstance(i, bool)]
    action = str(payload.get("action", "") or "")
    _audit_log(payload.get("source", "api"), action, ids,
               str(payload.get("category", "") or ""), str(payload.get("reason", "") or ""))
    if not ids:
        raise HTTPException(status_code=400, detail="فهرست ids خالی است")
    if len(ids) > 500:
        raise HTTPException(status_code=400, detail="حداکثر ۵۰۰ آیتم در هر عملیات گروهی")

    if action == "junk":
        res = data_purifier.confirm_junk(ids, reason=str(payload.get("reason", "") or ""))
        if res["confirmed"]:
            _schedule_recompute()  # FIX: تأخیری — پاسخ فوری برای لیبل‌زنی روان
        res["action"] = "junk"
        LAST_STATUS_TIME = 0.0
        MARKET_OVERVIEW_CACHE, MARKET_OVERVIEW_TIME = {}, 0.0
        return res

    if action == "verify":
        decisions = [{"id": i, "decision": "VERIFIED",
                      "reason": "✋ تأیید گروهی شما: کالای اصلی است", "confidence": 100.0}
                    for i in ids]
        applied = data_purifier.apply_agent_decisions(decisions)
        _schedule_recompute()  # FIX: تأخیری
        LAST_STATUS_TIME = 0.0
        MARKET_OVERVIEW_CACHE, MARKET_OVERVIEW_TIME = {}, 0.0
        # NEW: applied=0 خطا نیست — آیتم‌ها بین‌راه (مثلاً توسط حذف تکراری خودکار) رفته‌اند
        return {"action": "verify", "applied": applied,
                "message": (f"✅ {applied} آگهی تایید و قفل شد." if applied
                            else "این آیتم‌ها دیگر موجود نبودند (تکراری‌ها خودکار حذف شده‌اند) — بی‌خطر است")}

    if action == "set-category":
        category = str(payload.get("category", "") or "").strip().lower()
        if category not in STANDARD_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"دسته نامعتبر — یکی از: {', '.join(STANDARD_CATEGORIES)}")
        ensure_category_columns()
        ph = ",".join("?" * len(ids))
        keys = [r["canonical_key"] for r in db.fetchall(
            f"SELECT DISTINCT canonical_key FROM store_listings WHERE id IN ({ph});", tuple(ids))]
        # NEW: keys خالی خطا نیست (آیتم‌ها بین‌راه حذف شده‌اند) — شاخه‌ی tolerant پایین handled می‌کند
        from core.taxonomy import record_category_change
        record_category_change(keys, category,
                               note=str(payload.get("note", "") or ""),
                               is_uncertain=bool(payload.get("is_uncertain", False)))  # NEW: برای آموزش ML
        if not keys:
            LAST_STATUS_TIME = 0.0
            MARKET_OVERVIEW_CACHE, MARKET_OVERVIEW_TIME = {}, 0.0
            return {"action": "set-category", "updated_products": 0, "category": category,
                    "message": "این آیتم‌ها دیگر موجود نبودند (حذف خودکار تکراری) — بی‌خطر است"}
        kph = ",".join("?" * len(keys))
        db.execute(f"""UPDATE canonical_products SET category_std = ?, category_source = 'manual'
                       WHERE canonical_key IN ({kph});""", tuple([category] + keys))
        LAST_STATUS_TIME = 0.0
        MARKET_OVERVIEW_CACHE, MARKET_OVERVIEW_TIME = {}, 0.0
        return {"action": "set-category", "updated_products": len(keys),
                "category": category, "message": f"🗂 {len(keys)} محصول به «{category}» منتقل و قفل شد."}

    raise HTTPException(status_code=400, detail="action باید junk | verify | set-category باشد")

@router.post("/audit/set-category")
def set_listing_category(payload: Dict[str, Any] = Body(...)):
    """
    NEW: تغییر دسته‌ی دستی — روی «محصول کانونیکال» همان آگهی اعمال می‌شود و
    قوی‌ترین نوع دسته است (category_source='manual' — هیچ قاعده/AI‌ای آن را
    بازنویسی نمی‌کند).
    """
    from core.taxonomy import ensure_category_columns, STANDARD_CATEGORIES
    item_id = payload.get("id")
    category = str(payload.get("category", "") or "").strip().lower()
    if not isinstance(item_id, int):
        raise HTTPException(status_code=400, detail="id نامعتبر است")
    if category not in STANDARD_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"دسته نامعتبر — یکی از: {', '.join(STANDARD_CATEGORIES)}")

    from core.taxonomy import record_category_change
    ensure_category_columns()
    row = db.fetchone("SELECT canonical_key FROM store_listings WHERE id = ?;", (item_id,))
    if not row:
        raise HTTPException(status_code=404, detail="آگهی پیدا نشد")

    # NEW: یادداشت اختیاری + علامت «مطمئن نیستم» — دیتای طلایی برای ML آینده
    record_category_change([row["canonical_key"]], category,
                           note=str(payload.get("note", "") or ""),
                           is_uncertain=bool(payload.get("is_uncertain", False)))
    n = db.execute("""
        UPDATE canonical_products SET category_std = ?, category_source = 'manual'
        WHERE canonical_key = ?;
    """, (category, row["canonical_key"]))
    if not n:
        raise HTTPException(status_code=404, detail="محصول کانونیکال پیدا نشد")

    global LAST_STATUS_TIME, MARKET_OVERVIEW_CACHE, MARKET_OVERVIEW_TIME
    LAST_STATUS_TIME = 0.0
    MARKET_OVERVIEW_CACHE, MARKET_OVERVIEW_TIME = {}, 0.0
    return {"status": "success", "canonical_key": row["canonical_key"],
            "category": category, "message": "✅ دسته‌ی محصول تغییر کرد و قفل شد (manual)."}

@router.post("/audit/verify-listing")
def verify_single_listing(payload: Dict[str, Any] = Body(...)):
    """
    NEW: تأیید انسانیِ تکیِ یک آگهی به‌عنوان «کالای اصلی» (قفل می‌شود —
    پالایش‌های بعدی بازنویسی‌اش نمی‌کنند).
    """
    item_id = payload.get("id")
    if not isinstance(item_id, int):
        raise HTTPException(status_code=400, detail="id نامعتبر است")
    n = data_purifier.apply_agent_decisions([{
        "id": item_id, "decision": "VERIFIED",
        "reason": "✋ تأیید شما: کالای اصلی است", "confidence": 100.0
    }])
    _audit_log(payload.get("source", "api"), "verify-single", [item_id])
    if not n:
        raise HTTPException(status_code=404, detail="آگهی پیدا نشد")
    global LAST_STATUS_TIME
    LAST_STATUS_TIME = 0.0
    return {"status": "success", "message": "✅ آگهی تایید و قفل شد."}

@router.get("/analytics/weekly-report")
def get_weekly_report():
    """
    NEW: گزارش هفتگی بازار — snapshot در قالب Markdown (ذخیره در exports/ + قابل دانلود از /exports).
    """
    from datetime import date
    from pathlib import Path as _P

    overview = get_market_overview()  # از کش ۶۰ ثانیه‌ای استفاده می‌کند
    today = date.today()
    iso = today.isocalendar()
    week_tag = f"{iso[0]}-W{iso[1]:02d}"

    q = db.fetchone("""
        SELECT COUNT(*) c, COUNT(CASE WHEN is_verified=1 THEN 1 END) v FROM store_listings;
    """) or {"c": 0, "v": 0}
    purity = round((q["v"] / q["c"]) * 100.0, 1) if q["c"] else 0.0

    lines = [
        f"# 📊 گزارش هفتگی بازار — هفته {week_tag} ({today.strftime('%Y-%m-%d')})",
        "",
        f"- **محصولات کانونیکال:** {overview['total_products']:,}",
        f"- **آگهی‌های تاییدشده:** {overview['total_verified_listings']:,}",
        f"- **کل آگهی‌ها:** {q['c']:,} (پاکی داده: {purity}٪)",
        "",
        "| دسته | محصولات | آگهی | میانه نو (ت) | میانه دست‌دوم (ت) | شکاف | برند غالب |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in overview["categories"]:
        top_brand = next((b["brand"] for b in c["top_brands"] if b["brand"] != "other"), "—")
        gap = f"{c['new_used_gap_percent']}٪" if c["new_used_gap_percent"] else "—"
        lines.append(
            f"| {c['label']} | {c['products']:,} | {c['listings']:,} | "
            f"{c['new_price_median']:,} | {c['used_price_median']:,} | {gap} | {top_brand} |"
        )
    lines += ["", f"_تولید خودکار توسط هاب — {overview['generated_at']}_"]

    exports_dir = _P(__file__).resolve().parent.parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    md_path = exports_dir / f"weekly_report_{week_tag}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "status": "success",
        "week": week_tag,
        "markdown_path": str(md_path),
        "download_url": f"/exports/weekly_report_{week_tag}.md",
        "summary": {
            "total_products": overview["total_products"],
            "verified_listings": overview["total_verified_listings"],
            "total_listings": q["c"],
            "purity_percent": purity,
            "categories_count": len(overview["categories"]),
        },
    }

@router.get("/analytics/depreciation")
def get_depreciation_analytics():
    brand_stats = db.fetchall("""
        SELECT
            brand,
            count(*) as products_count,
            AVG(depreciation_percent) as avg_depreciation,
            AVG(torob_min_price_toman) as avg_new_price,
            AVG(divar_avg_price_toman) as avg_used_price
        FROM canonical_products
        WHERE torob_min_price_toman > 0 AND (divar_avg_price_toman > 0 OR esam_avg_price_toman > 0)
        GROUP BY brand
        ORDER BY products_count DESC;
    """)

    return {"brand_depreciation": brand_stats}

# --- 8. AI Datasets & Ingestion ---

@router.get("/ai/dataset-stats")
def get_ai_dataset_stats():
    return ai_exporter.export_all()

@router.post("/sync/upload-torob-json")
def upload_torob_json_data(payload: Dict[str, Any] = Body(...)):
    try:
        raw_items = payload.get("products") or payload.get("items") or payload.get("data") or payload
        if isinstance(raw_items, dict):
            items = list(raw_items.values())
        elif isinstance(raw_items, list):
            items = raw_items
        else:
            items = []

        count = ingest_torob_items(items)
        data_purifier.run_full_purification_pipeline()
        arbitrage_engine.run_arbitrage_scan()
        ai_exporter.export_all()
        return {"status": "success", "items_ingested": count, "message": f"✅ {count} کالا از فایل ترب با موفقیت در دیتابیس ثبت شد."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"خطا در پردازش فایل ترب: {e}")

@router.post("/sync/pull-cloud")
def pull_from_cloud_databases():
    res = cloud_puller.pull_all_and_sync()
    data_purifier.run_full_purification_pipeline()
    return res

@router.post("/sync/rescan-arbitrage")
def rescan_arbitrage():
    data_purifier.run_full_purification_pipeline()
    res = arbitrage_engine.run_arbitrage_scan()
    ai_exporter.export_all()
    return res
