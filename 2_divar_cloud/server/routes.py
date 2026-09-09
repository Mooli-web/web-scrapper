import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends, Body
from pydantic import BaseModel

from crawler.db import db
from crawler.engine import divar_crawler
from crawler.divar_adapter import DivarAdapter
from server.auth import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    create_access_token,
    verify_credentials,
    AUTH_ENABLED
)

logger = logging.getLogger("divar.routes")
router = APIRouter(prefix="/api")

# --- NEW: Junk Filter (فیلتر هویتی آگهی‌های بی‌ارزش در لحظه‌ی کشف) ---
from crawler.junk_filter import junk_filter  # noqa: E402

@router.post("/junk-filter/backfill")
def junk_filter_backfill(payload: dict = Body(...)):
    """
    NEW: پاکسازی یک‌باره‌ی آگهی‌های چرتِ موجود در دیتابیس این سرویس با همان
    قوانین هویتی فیلتر. اول با dry_run=true نمونه و آمار بگیر، بعد dry_run=false.
    """
    from crawler.junk_filter import should_drop
    dry_run = bool(payload.get("dry_run", True))
    rows = db.fetchall("SELECT token AS rid, title_fa, selling_price_toman AS price FROM divar_posts;") or []
    victims = []
    for r in rows:
        reason = should_drop(r["title_fa"] or "", r["price"] or 0)
        if reason:
            victims.append({"id": r["rid"], "title": (r["title_fa"] or "")[:80], "reason": reason})
    deleted = 0
    if not dry_run and victims:
        for i in range(0, len(victims), 500):
            chunk = victims[i:i + 500]
            ids = [v["id"] for v in chunk]
            ph = ",".join(["%s"] * len(ids))
            db.execute("DELETE FROM divar_posts WHERE token IN (%s);" % ph, tuple(ids))
        deleted = len(victims)
    return {"dry_run": dry_run, "total_rows": len(rows), "candidates": len(victims),
            "deleted": deleted, "sample": victims[:30]}

@router.get("/junk-filter/stats")
def get_junk_filter_stats():
    """آمار فیلتر چرت: چند کاندیدا، چند حذف، نمونه‌های اخیر با دلیل."""
    return junk_filter.get_stats()

@router.post("/junk-filter/mode")
def set_junk_filter_mode(payload: dict):
    """تغییر حالت: shadow (فقط آمار) | active (حذف واقعی) | off"""
    ok = junk_filter.set_mode(str(payload.get("mode", "")))
    if not ok:
        raise HTTPException(status_code=400, detail="mode باید shadow | active | off باشد")
    return {"status": "success", "mode": junk_filter.mode}

active_ws_clients: List[Any] = []

class LoginRequest(BaseModel):
    username: str
    password: str

async def broadcast_telemetry(payload: Dict[str, Any]):
    for ws in list(active_ws_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            if ws in active_ws_clients:
                active_ws_clients.remove(ws)

# --- 1. Auth ---

@router.post("/login")
def login(req: LoginRequest):
    if req.username == ADMIN_USERNAME and req.password == ADMIN_PASSWORD:
        token = create_access_token(req.username)
        return {
            "status": "success",
            "access_token": token,
            "token_type": "bearer",
            "user": {"username": req.username, "role": "admin"}
        }
    raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است.")

@router.get("/auth/me")
def get_current_user(user: str = Depends(verify_credentials)):
    return {"authenticated": True, "username": user, "auth_enabled": AUTH_ENABLED}

# --- 2. Live Diagnostics ---

@router.get("/database/test-connection")
def test_database():
    health = db.check_health()
    table_counts = {}
    if health.get("connected"):
        for t in ["divar_categories", "divar_posts", "divar_price_observations", "divar_price_events"]:
            try:
                cnt_row = db.fetchone(f"SELECT COUNT(*) AS cnt FROM {t};")
                table_counts[t] = cnt_row["cnt"] if cnt_row else 0
            except Exception:
                table_counts[t] = 0

    return {
        "health": health,
        "table_counts": table_counts
    }

@router.get("/divar/test-connection")
def test_divar():
    adapter = DivarAdapter()
    return adapter.probe_connection()

# --- 3. Live Continuous Crawler Controls & Log Stream ---

@router.get("/crawler/status")
def get_crawler_status(user: str = Depends(verify_credentials)):
    return divar_crawler.telemetry

@router.get("/crawler/logs-stream")
def get_crawler_logs(after_id: int = 0, user: str = Depends(verify_credentials)):
    new_logs = [l for l in divar_crawler.log_history if l["id"] > after_id]
    return {
        "telemetry": divar_crawler.telemetry,
        "new_logs": new_logs,
        "latest_id": divar_crawler.log_counter
    }

@router.post("/crawler/start")
def start_crawler(background_tasks: BackgroundTasks, user: str = Depends(verify_credentials)):
    if divar_crawler.is_running:
        return {"status": "already_running", "message": "خزنده در حال حاضر فعال است."}

    def run_task():
        loop = asyncio.new_event_loop()
        def on_event(payload):
            try:
                loop.run_until_complete(broadcast_telemetry(payload))
            except Exception:
                pass
        divar_crawler.run_continuous_loop(progress_callback=on_event)

    background_tasks.add_task(run_task)
    return {"status": "started", "message": "خزش پیوسته ۲۴/۷ دیوار آغاز شد."}

@router.post("/crawler/stop")
def stop_crawler(user: str = Depends(verify_credentials)):
    divar_crawler.stop()
    return {"status": "stopping", "message": "دستور توقف به خزنده ارسال شد."}

# --- 4. Overview & Categories ---

@router.get("/overview")
def get_overview(user: str = Depends(verify_credentials)):
    try:
        stats = db.fetchone(
            """
            SELECT 
                COUNT(*) AS total_posts,
                COUNT(*) FILTER (WHERE condition = 'در حد نو') AS like_new_count,
                COUNT(*) FILTER (WHERE condition = 'نو (پلمپ/آکبند)') AS brand_new_count,
                COALESCE(AVG(selling_price_toman), 0) AS avg_price
            FROM divar_posts
            WHERE is_active IS TRUE;
            """
        ) or {}

        events_24h = db.fetchone(
            "SELECT COUNT(*) AS count_24h FROM divar_price_events WHERE created_at >= NOW() - INTERVAL '24 hours';"
        ) or {"count_24h": 0}

        recent_ads = db.fetchall(
            """
            SELECT p.*, c.title_fa AS category_name
            FROM divar_posts p
            LEFT JOIN divar_categories c ON p.category_key = c.category_key
            WHERE p.is_active IS TRUE
            ORDER BY p.last_seen_at DESC
            LIMIT 6;
            """
        )

        return {
            "total_posts": stats.get("total_posts", 0) or 0,
            "like_new_count": stats.get("like_new_count", 0) or 0,
            "brand_new_count": stats.get("brand_new_count", 0) or 0,
            "avg_price": int(stats.get("avg_price", 0) or 0),
            "events_24h": events_24h.get("count_24h", 0) or 0,
            "database_health": db.check_health(),
            "crawler_telemetry": divar_crawler.telemetry,
            "recent_ads": recent_ads
        }
    except Exception as e:
        logger.error(f"Overview error: {e}")
        return {
            "total_posts": 0, "like_new_count": 0, "brand_new_count": 0, "avg_price": 0,
            "events_24h": 0, "database_health": db.check_health(), "crawler_telemetry": divar_crawler.telemetry, "recent_ads": []
        }

@router.get("/categories")
def get_categories(user: str = Depends(verify_credentials)):
    try:
        return db.fetchall("SELECT * FROM divar_categories WHERE is_active IS TRUE ORDER BY category_key ASC;")
    except Exception:
        return []

# --- 5. Posts Ledger ---

@router.get("/posts")
def get_posts(
    search: Optional[str] = None,
    category: Optional[str] = None,
    condition: Optional[str] = None,
    sort_by: str = "newest",
    page: int = 1,
    page_size: int = 20,
    user: str = Depends(verify_credentials)
):
    try:
        offset = max(0, (page - 1) * page_size)
        where_clauses = ["p.is_active IS TRUE"]
        params = []

        if search and search.strip():
            where_clauses.append("(p.title_fa ILIKE %s OR p.brand ILIKE %s OR p.district ILIKE %s)")
            s = f"%{search.strip()}%"
            params.extend([s, s, s])

        if category and category != "all":
            where_clauses.append("p.category_key = %s")
            params.append(category)

        if condition and condition != "all":
            where_clauses.append("p.condition = %s")
            params.append(condition)

        where_sql = " AND ".join(where_clauses)

        order_map = {
            "newest": "p.last_seen_at DESC",
            "price_asc": "p.selling_price_toman ASC",
            "price_desc": "p.selling_price_toman DESC",
            "title_asc": "p.title_fa ASC"
        }
        order_clause = order_map.get(sort_by, "p.last_seen_at DESC")

        count_row = db.fetchone(f"SELECT COUNT(*) AS total FROM divar_posts p WHERE {where_sql};", tuple(params))
        total = count_row["total"] if count_row else 0

        query_sql = f"""
            SELECT p.*, c.title_fa AS category_name
            FROM divar_posts p
            LEFT JOIN divar_categories c ON p.category_key = c.category_key
            WHERE {where_sql}
            ORDER BY {order_clause}
            LIMIT %s OFFSET %s;
        """
        rows = db.fetchall(query_sql, tuple(params + [page_size, offset]))

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total > 0 else 1
        }
    except Exception as e:
        logger.error(f"Posts error: {e}")
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

# --- 6. Database Wipe ---

@router.post("/wipe-database")
def wipe_database(user: str = Depends(verify_credentials)):
    try:
        db.execute("DELETE FROM divar_price_events;")
        db.execute("DELETE FROM divar_price_observations;")
        db.execute("DELETE FROM divar_posts;")
        db.execute("UPDATE divar_categories SET post_count = 0, last_crawled_at = NULL;")
        divar_crawler._cached_posts.clear()
        divar_crawler._cache_initialized = False
        return {"status": "success", "message": "تمامی داده‌های آگهی‌های دیوار با موفقیت صفر و پاکسازی شدند."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
def get_system_status():
    health = db.check_health()
    return {
        "status": "operational" if health.get("connected") else "disconnected",
        "database": health,
        "crawler_telemetry": divar_crawler.telemetry,
        "auth_enabled": AUTH_ENABLED
    }
