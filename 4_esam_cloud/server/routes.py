import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends, Body
from pydantic import BaseModel

from crawler.db import db
from crawler.engine import esam_crawler
from crawler.esam_adapter import EsamAdapter
from server.auth import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    create_access_token,
    verify_credentials,
    AUTH_ENABLED
)

logger = logging.getLogger("esam.routes")
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
    rows = db.fetchall("SELECT item_id AS rid, title_fa, selling_price_toman AS price FROM esam_items;") or []
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
            db.execute("DELETE FROM esam_items WHERE item_id IN (%s);" % ph, tuple(ids))
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

class LoginRequest(BaseModel):
    username: str
    password: str

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
        try:
            for tbl in ["esam_items", "esam_price_observations", "esam_price_events", "esam_categories"]:
                r = db.fetchone(f"SELECT count(*) AS c FROM {tbl};")
                table_counts[tbl] = r["c"] if r else 0
        except Exception:
            pass
    return {**health, "table_counts": table_counts}

@router.get("/esam/test-probe")
def test_esam_probe(slug: str = "search/laptop?cc=40100", page: int = 1):
    adapter = EsamAdapter()
    t0 = datetime.now()
    items = adapter.fetch_category_items(query_slug=slug, page=page, category_key="probe", category_name="تست زنده")
    elapsed_ms = (datetime.now() - t0).total_seconds() * 1000
    return {
        "status": "success" if items else "empty_or_blocked",
        "items_count": len(items),
        "elapsed_ms": round(elapsed_ms, 2),
        "sample_items": items[:3]
    }

# --- 3. Mission Control & Telemetry ---

@router.get("/crawler/logs-stream")
def get_crawler_logs_stream(after_id: int = 0):
    new_logs = [log for log in esam_crawler.log_history if log["id"] > after_id]
    return {
        "telemetry": esam_crawler.telemetry,
        "is_running": esam_crawler.is_running,
        "latest_id": esam_crawler.log_counter,
        "new_logs": new_logs
    }

@router.post("/crawler/start")
def start_crawler(background_tasks: BackgroundTasks, user: str = Depends(verify_credentials)):
    if esam_crawler.is_running:
        return {"status": "already_running", "message": "موتور خزش پیوسته ایسام در حال اجراست."}
    
    background_tasks.add_task(esam_crawler.run_continuous_loop)
    return {"status": "started", "message": "خزنده پیوسته ایسام با موفقیت راه‌اندازی شد."}

@router.post("/crawler/stop")
def stop_crawler(user: str = Depends(verify_credentials)):
    if not esam_crawler.is_running:
        return {"status": "not_running", "message": "خزنده ایسام فعال نیست."}
    
    esam_crawler.stop()
    return {"status": "stopping", "message": "دستور توقف به ورکر ایسام ارسال شد."}

@router.post("/crawler/trigger-batch")
def trigger_batch(
    category_key: str = Query("laptop"),
    page: int = Query(1, ge=1, le=10),
    user: str = Depends(verify_credentials)
):
    cat_info = {"key": category_key, "name": category_key, "slug": f"search/{category_key}", "is_auction": False}
    if db.is_configured():
        row = db.fetchone("SELECT category_key, title_fa, query_slug, is_auction_feed FROM esam_categories WHERE category_key = %s;", (category_key,))
        if row:
            cat_info = {"key": row["category_key"], "name": row["title_fa"], "slug": row["query_slug"], "is_auction": row.get("is_auction_feed", False)}

    new_c, price_c, bids_c = esam_crawler.run_single_batch(cat_info, page)
    return {
        "status": "success",
        "category": cat_info["name"],
        "page": page,
        "new_items": new_c,
        "price_changes": price_c,
        "bids_changes": bids_c
    }

# --- 4. Overview & Statistics ---

@router.get("/esam/overview")
def get_overview_stats():
    if not db.is_configured():
        return {
            "total_items": 0,
            "total_auctions": 0,
            "total_events": 0,
            "price_drops_24h": 0,
            "avg_price_toman": 0,
            "categories_breakdown": [],
            "conditions_breakdown": []
        }

    try:
        r_total = db.fetchone("SELECT count(*) as cnt, COALESCE(AVG(selling_price_toman), 0) as avg_p FROM esam_items WHERE selling_price_toman > 0;")
        r_auctions = db.fetchone("SELECT count(*) as cnt FROM esam_items WHERE is_auction = TRUE;")
        r_events = db.fetchone("SELECT count(*) as cnt FROM esam_price_events;")
        r_drops = db.fetchone("SELECT count(*) as cnt FROM esam_price_events WHERE event_type = 'PRICE_DROP' AND detected_at >= CURRENT_TIMESTAMP - INTERVAL '24 HOURS';")

        cat_rows = db.fetchall("""
            SELECT category_name_fa as name, count(*) as count, COALESCE(AVG(selling_price_toman), 0) as avg_price
            FROM esam_items
            GROUP BY category_name_fa
            ORDER BY count DESC
            LIMIT 10;
        """)

        cond_rows = db.fetchall("""
            SELECT condition as name, count(*) as count
            FROM esam_items
            GROUP BY condition
            ORDER BY count DESC;
        """)

        return {
            "total_items": r_total["cnt"] if r_total else 0,
            "total_auctions": r_auctions["cnt"] if r_auctions else 0,
            "total_events": r_events["cnt"] if r_events else 0,
            "price_drops_24h": r_drops["cnt"] if r_drops else 0,
            "avg_price_toman": round(float(r_total["avg_p"])) if r_total and r_total["avg_p"] else 0,
            "categories_breakdown": cat_rows,
            "conditions_breakdown": cond_rows
        }
    except Exception as e:
        logger.error(f"Error fetching overview stats: {e}")
        return {"error": str(e)}

# --- 5. Items Ledger with Multi-Column Sorting ---

@router.get("/esam/items")
def get_esam_items(
    search: Optional[str] = None,
    category: Optional[str] = None,
    condition: Optional[str] = None,
    auction_only: Optional[bool] = None,
    sort_by: str = Query("last_seen_at", pattern="^(selling_price_toman|base_price_toman|bids_count|last_seen_at|title_fa|condition)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    if not db.is_configured():
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    where_clauses = ["1=1"]
    params = []

    if search:
        where_clauses.append("(title_fa ILIKE %s OR seller_name ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    if category and category != "all":
        where_clauses.append("category_key = %s")
        params.append(category)

    if condition and condition != "all":
        where_clauses.append("condition = %s")
        params.append(condition)

    if auction_only is True:
        where_clauses.append("is_auction = TRUE")

    where_sql = " AND ".join(where_clauses)
    order_sql = f"ORDER BY {sort_by} {sort_order.upper()}"

    try:
        count_row = db.fetchone(f"SELECT count(*) as c FROM esam_items WHERE {where_sql};", tuple(params))
        total = count_row["c"] if count_row else 0

        query = f"""
            SELECT
                id, item_id, title_fa, category_key, category_name_fa, brand,
                condition, is_auction, selling_price_toman, base_price_toman,
                buy_now_price_toman, bids_count, time_remaining, seller_name,
                seller_score, seller_city, url, image_url, first_seen_at, last_seen_at
            FROM esam_items
            WHERE {where_sql}
            {order_sql}
            LIMIT %s OFFSET %s;
        """
        items = db.fetchall(query, tuple(params + [limit, offset]))

        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"Error querying Esam items: {e}")
        return {"items": [], "total": 0, "error": str(e)}

# --- 6. Auctions Page ---

@router.get("/esam/auctions")
def get_active_auctions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    if not db.is_configured():
        return {"auctions": [], "total": 0}

    try:
        total_row = db.fetchone("SELECT count(*) as c FROM esam_items WHERE is_auction = TRUE;")
        total = total_row["c"] if total_row else 0

        rows = db.fetchall("""
            SELECT
                id, item_id, title_fa, category_name_fa, condition,
                selling_price_toman, base_price_toman, bids_count,
                time_remaining, seller_name, seller_score, url, image_url, last_seen_at
            FROM esam_items
            WHERE is_auction = TRUE
            ORDER BY bids_count DESC, last_seen_at DESC
            LIMIT %s OFFSET %s;
        """, (limit, offset))

        return {"auctions": rows, "total": total}
    except Exception as e:
        return {"auctions": [], "total": 0, "error": str(e)}

# --- 7. Events Ledger ---

@router.get("/esam/events")
def get_price_events(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    if not db.is_configured():
        return {"events": [], "total": 0}

    where = ["1=1"]
    params = []

    if event_type and event_type != "all":
        where.append("event_type = %s")
        params.append(event_type)

    if severity and severity != "all":
        where.append("severity = %s")
        params.append(severity)

    where_sql = " AND ".join(where)

    try:
        c_row = db.fetchone(f"SELECT count(*) as c FROM esam_price_events WHERE {where_sql};", tuple(params))
        total = c_row["c"] if c_row else 0

        events = db.fetchall(f"""
            SELECT
                e.id, e.item_id, e.title_fa, e.event_type, e.old_price_toman,
                e.new_price_toman, e.price_change_toman, e.change_percent,
                e.severity, e.detected_at, i.url, i.image_url, i.condition, i.is_auction
            FROM esam_price_events e
            LEFT JOIN esam_items i ON e.item_id = i.item_id
            WHERE {where_sql}
            ORDER BY e.detected_at DESC
            LIMIT %s OFFSET %s;
        """, tuple(params + [limit, offset]))

        return {"events": events, "total": total}
    except Exception as e:
        return {"events": [], "total": 0, "error": str(e)}

# --- 8. Categories List ---

@router.get("/esam/categories")
def get_categories():
    if not db.is_configured():
        return {"categories": []}
    try:
        cats = db.fetchall("""
            SELECT c.id, c.category_key, c.title_fa, c.category_code, c.query_slug, c.is_auction_feed, c.is_active,
                   count(i.id) as real_items_count
            FROM esam_categories c
            LEFT JOIN esam_items i ON c.category_key = i.category_key
            GROUP BY c.id, c.category_key, c.title_fa, c.category_code, c.query_slug, c.is_auction_feed, c.is_active
            ORDER BY c.id ASC;
        """)
        return {"categories": cats}
    except Exception as e:
        return {"categories": [], "error": str(e)}
