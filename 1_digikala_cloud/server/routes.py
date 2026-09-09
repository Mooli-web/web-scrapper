import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel

from crawler.db import db
from crawler.storage_guard import StorageGuard
from crawler.engine import crawler_engine
from crawler.adapters.digikala import DigikalaAdapter
from server.serializers import serialize_for_api
from server.auth import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    create_access_token,
    verify_credentials,
    AUTH_ENABLED
)

logger = logging.getLogger("server.routes")
router = APIRouter(prefix="/api")

active_ws_clients: List[Any] = []

class LoginRequest(BaseModel):
    username: str
    password: str

async def broadcast_crawler_telemetry(payload: Dict[str, Any]):
    for ws in list(active_ws_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            if ws in active_ws_clients:
                active_ws_clients.remove(ws)

# --- 0. Root Info ---

@router.get("/")
@router.get("")
def api_root_info():
    return {
        "status": "online",
        "service": "God's Eye Market Intelligence Platform",
        "version": "2.5.0",
        "endpoints": {
            "status": "/api/status",
            "products": "/api/products",
            "overview": "/api/overview",
            "fake_discounts": "/api/fake-discounts",
            "seller_war": "/api/seller-war/battles",
            "docs": "/docs"
        }
    }

# --- 1. Authentication ---

@router.post("/login")
def login(req: LoginRequest):
    if req.username == ADMIN_USERNAME and req.password == ADMIN_PASSWORD:
        token = create_access_token(req.username)
        return {
            "status": "success",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "username": req.username,
                "role": "admin"
            }
        }
    raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است.")

@router.get("/auth/me")
def get_current_user(user: str = Depends(verify_credentials)):
    return {
        "authenticated": True,
        "username": user,
        "role": "admin",
        "auth_enabled": AUTH_ENABLED
    }

# --- 2. Live Diagnostics ---

@router.get("/database/test-connection")
def test_database_connection():
    health = db.check_health()
    table_counts = {}
    if health.get("connected"):
        for t in ["categories", "master_products", "store_listings", "price_observations", "price_events"]:
            try:
                cnt_row = db.fetchone(f"SELECT COUNT(*) AS cnt FROM {t};")
                table_counts[t] = cnt_row["cnt"] if cnt_row else 0
            except Exception:
                table_counts[t] = 0

    return serialize_for_api({
        "health": health,
        "table_counts": table_counts,
        "tested_at": datetime.now(timezone.utc).isoformat()
    })

@router.get("/digikala/test-connection")
def test_digikala_connection():
    adapter = DigikalaAdapter()
    result = adapter.probe_connection()
    return serialize_for_api(result)

# --- 3. Live Continuous Crawler Controls & Log Stream ---

@router.get("/crawler/status")
def get_crawler_status(user: str = Depends(verify_credentials)):
    return serialize_for_api(crawler_engine.telemetry)

@router.get("/crawler/logs-stream")
def get_crawler_logs_stream(after_id: int = 0, user: str = Depends(verify_credentials)):
    new_logs = [l for l in crawler_engine.log_history if l["id"] > after_id]
    return serialize_for_api({
        "telemetry": crawler_engine.telemetry,
        "new_logs": new_logs,
        "latest_id": crawler_engine.log_counter
    })

@router.post("/crawler/start")
def start_continuous_crawler(background_tasks: BackgroundTasks, user: str = Depends(verify_credentials)):
    if crawler_engine.is_running:
        return {"status": "already_running", "message": "خزنده دیجی‌کالا در حال حاضر فعال است."}

    def run_task():
        loop = asyncio.new_event_loop()
        def on_event(payload):
            try:
                loop.run_until_complete(broadcast_crawler_telemetry(payload))
            except Exception:
                pass
        crawler_engine.run_continuous_loop(progress_callback=on_event)

    background_tasks.add_task(run_task)
    return {"status": "started", "message": "خزش پیوسته و هوشمند بازار آغاز شد."}

@router.post("/crawler/stop")
def stop_continuous_crawler(user: str = Depends(verify_credentials)):
    crawler_engine.stop()
    return {"status": "stopping", "message": "دستور توقف به خزنده ارسال شد."}

# --- 4. Overview & Categories ---

@router.get("/overview")
def get_overview(user: str = Depends(verify_credentials)):
    try:
        overview = db.fetchone(
            """
            SELECT 
                COUNT(p.product_id) AS total_products,
                COUNT(p.product_id) FILTER (WHERE sl.discount_percent > 0) AS active_discounts,
                COUNT(p.product_id) FILTER (WHERE sl.available IS TRUE) AS in_stock_count,
                COALESCE(AVG(sl.discount_percent) FILTER (WHERE sl.discount_percent > 0), 0.0) AS avg_discount_percent
            FROM master_products p
            LEFT JOIN store_listings sl ON p.product_id = sl.product_id
            WHERE p.is_active IS TRUE;
            """
        ) or {}

        fake_stat = db.fetchone(
            """
            SELECT 
                COUNT(*) FILTER (WHERE sl.discount_percent > 0 AND sl.avg_price_30d > 0 AND sl.selling_price_toman > sl.avg_price_30d) AS fake_discounts_count,
                COUNT(*) FILTER (WHERE sl.discount_percent > 0 AND (sl.selling_price_toman <= sl.min_price_30d OR (sl.avg_price_30d > 0 AND sl.selling_price_toman < sl.avg_price_30d))) AS genuine_discounts_count,
                COUNT(*) FILTER (WHERE sl.discount_percent > 0 AND (sl.avg_price_30d = 0 OR sl.selling_price_toman = sl.avg_price_30d)) AS baseline_count
            FROM store_listings sl
            WHERE sl.available IS TRUE;
            """
        ) or {"fake_discounts_count": 0, "genuine_discounts_count": 0, "baseline_count": 0}

        seller_war_stat = db.fetchone(
            """
            SELECT COUNT(DISTINCT product_id) AS active_wars
            FROM price_observations
            GROUP BY product_id
            HAVING COUNT(DISTINCT seller_name) > 1
            LIMIT 1;
            """
        )

        cat_count_row = db.fetchone("SELECT COUNT(*) AS total_cats FROM categories WHERE is_active IS TRUE;")
        total_categories = cat_count_row["total_cats"] if cat_count_row else 0

        events_24h = db.fetchone(
            """
            SELECT COUNT(*) AS count_24h,
                   COUNT(*) FILTER (WHERE severity = 'high') AS high_severity_count
            FROM price_events
            WHERE created_at >= NOW() - INTERVAL '24 hours';
            """
        ) or {"count_24h": 0, "high_severity_count": 0}

        db_stats = StorageGuard.get_database_stats()
        db_health = db.check_health()

        recent_deals = db.fetchall(
            """
            SELECT e.*, p.title_fa, p.brand, p.image_url, sl.product_url, sl.selling_price_toman, sl.discount_percent, sl.seller_name
            FROM price_events e
            JOIN master_products p ON e.product_id = p.product_id
            JOIN store_listings sl ON e.product_id = sl.product_id AND e.store_key = sl.store_key
            WHERE e.event_type = 'price_drop'
            ORDER BY e.created_at DESC
            LIMIT 6;
            """
        )

        return serialize_for_api({
            "total_products": overview.get("total_products", 0) or 0,
            "total_categories": total_categories or 0,
            "active_discounts": overview.get("active_discounts", 0) or 0,
            "in_stock_count": overview.get("in_stock_count", 0) or 0,
            "out_of_stock_count": max(0, (overview.get("total_products", 0) or 0) - (overview.get("in_stock_count", 0) or 0)),
            "avg_discount_percent": round(float(overview.get("avg_discount_percent", 0.0) or 0.0), 1),
            "fake_discounts_count": fake_stat.get("fake_discounts_count", 0) or 0,
            "genuine_discounts_count": fake_stat.get("genuine_discounts_count", 0) or 0,
            "baseline_count": fake_stat.get("baseline_count", 0) or 0,
            "active_seller_wars": seller_war_stat.get("active_wars", 0) if seller_war_stat else 0,
            "events_24h": events_24h.get("count_24h", 0) or 0,
            "high_severity_24h": events_24h.get("high_severity_count", 0) or 0,
            "db_usage_percent": db_stats.get("usage_percent", 0.0) or 0.0,
            "db_size_mb": db_stats.get("estimated_storage_mb", 0.0) or 0.0,
            "database_health": db_health,
            "crawler_telemetry": crawler_engine.telemetry,
            "recent_deals": recent_deals
        })
    except Exception as e:
        logger.error(f"Overview error: {e}")
        db_health = db.check_health()
        return serialize_for_api({
            "total_products": 0, "total_categories": 0, "active_discounts": 0,
            "in_stock_count": 0, "out_of_stock_count": 0, "avg_discount_percent": 0.0,
            "fake_discounts_count": 0, "genuine_discounts_count": 0, "baseline_count": 0,
            "active_seller_wars": 0, "events_24h": 0, "high_severity_24h": 0,
            "db_usage_percent": 0.0, "db_size_mb": 0.0,
            "database_health": db_health, "crawler_telemetry": crawler_engine.telemetry, "recent_deals": []
        })

@router.get("/categories")
def get_categories(user: str = Depends(verify_credentials)):
    try:
        cats = db.fetchall(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM master_products p WHERE p.category_key = c.category_key) AS real_product_count,
                   (SELECT COUNT(*) FROM master_products p JOIN store_listings sl ON p.product_id = sl.product_id WHERE p.category_key = c.category_key AND sl.discount_percent > 0) AS real_discount_count,
                   (SELECT COALESCE(AVG(sl.selling_price_toman), 0) FROM master_products p JOIN store_listings sl ON p.product_id = sl.product_id WHERE p.category_key = c.category_key) AS avg_price_toman
            FROM categories c
            WHERE c.is_active IS TRUE
            ORDER BY c.depth ASC, c.category_key ASC;
            """
        )
        return serialize_for_api(cats)
    except Exception as e:
        logger.error(f"Categories error: {e}")
        return []

# --- 5. Products Catalog ---

@router.get("/products")
def get_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    seller: Optional[str] = None,
    min_discount: Optional[Any] = None,
    in_stock_only: bool = False,
    sort_by: str = "discount_desc",
    page: int = 1,
    page_size: int = 20,
    user: str = Depends(verify_credentials)
):
    try:
        offset = max(0, (page - 1) * page_size)
        where_clauses = ["p.is_active IS TRUE"]
        params = []

        if search and search not in ("undefined", "null", ""):
            where_clauses.append("(p.title_fa ILIKE %s OR p.brand ILIKE %s OR sl.seller_name ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        if category and category not in ("all", "undefined", "null", ""):
            where_clauses.append("(p.category_key = %s OR c.parent_key = %s)")
            params.extend([category, category])

        if brand and brand not in ("all", "undefined", "null", ""):
            where_clauses.append("p.brand ILIKE %s")
            params.append(f"%{brand}%")

        if seller and seller not in ("all", "undefined", "null", ""):
            where_clauses.append("sl.seller_name ILIKE %s")
            params.append(f"%{seller}%")

        try:
            if min_discount is not None and str(min_discount) not in ("undefined", "null", "", "0"):
                val = float(min_discount)
                if val > 0:
                    where_clauses.append("sl.discount_percent >= %s")
                    params.append(val)
        except Exception:
            pass

        if in_stock_only:
            where_clauses.append("sl.available IS TRUE")

        where_sql = " AND ".join(where_clauses)

        order_map = {
            "discount_desc": "sl.discount_percent DESC, sl.last_updated_at DESC",
            "price_asc": "sl.selling_price_toman ASC",
            "price_desc": "sl.selling_price_toman DESC",
            "newest": "p.first_seen_at DESC",
            "title_asc": "p.title_fa ASC",
            "min_price_asc": "sl.min_price_30d ASC"
        }
        order_clause = order_map.get(sort_by, "sl.discount_percent DESC, sl.last_updated_at DESC")

        count_row = db.fetchone(
            f"""
            SELECT COUNT(*) AS total
            FROM master_products p
            LEFT JOIN categories c ON p.category_key = c.category_key
            LEFT JOIN store_listings sl ON p.product_id = sl.product_id
            WHERE {where_sql};
            """,
            tuple(params)
        )
        total = count_row["total"] if count_row else 0

        query_sql = f"""
            SELECT p.product_id, p.title_fa, p.brand, p.category_key, p.image_url,
                   c.title_fa AS category_name,
                   sl.store_key, sl.selling_price_toman, sl.rrp_price_toman, sl.discount_percent,
                   sl.seller_name, sl.available, sl.product_url, sl.min_price_30d, sl.avg_price_30d,
                   sl.last_updated_at
            FROM master_products p
            LEFT JOIN categories c ON p.category_key = c.category_key
            LEFT JOIN store_listings sl ON p.product_id = sl.product_id
            WHERE {where_sql}
            ORDER BY {order_clause}
            LIMIT %s OFFSET %s;
        """
        rows = db.fetchall(query_sql, tuple(params + [page_size, offset]))

        return serialize_for_api({
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total > 0 else 1
        })
    except Exception as e:
        logger.error(f"Products endpoint error: {e}")
        return serialize_for_api({"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1})

@router.get("/products/{product_id}")
def get_product_details(product_id: int, user: str = Depends(verify_credentials)):
    try:
        product = db.fetchone(
            """
            SELECT p.*, c.title_fa AS category_name,
                   sl.selling_price_toman, sl.rrp_price_toman, sl.discount_percent,
                   sl.seller_name, sl.available, sl.product_url, sl.min_price_30d, sl.avg_price_30d,
                   sl.last_updated_at
            FROM master_products p
            LEFT JOIN categories c ON p.category_key = c.category_key
            LEFT JOIN store_listings sl ON p.product_id = sl.product_id
            WHERE p.product_id = %s;
            """,
            (product_id,)
        )
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        history = db.fetchall(
            """
            SELECT selling_price_toman, rrp_price_toman, discount_percent, seller_name, available, observed_at, store_key
            FROM price_observations
            WHERE product_id = %s
            ORDER BY observed_at ASC;
            """,
            (product_id,)
        )

        events = db.fetchall(
            """
            SELECT * FROM price_events
            WHERE product_id = %s
            ORDER BY created_at DESC;
            """,
            (product_id,)
        )

        sellers_history = db.fetchall(
            """
            SELECT DISTINCT seller_name, 
                   MIN(selling_price_toman) AS lowest_offered_price,
                   MAX(selling_price_toman) AS highest_offered_price,
                   COUNT(*) AS observation_count,
                   MAX(observed_at) AS last_seen
            FROM price_observations
            WHERE product_id = %s AND seller_name IS NOT NULL
            GROUP BY seller_name
            ORDER BY lowest_offered_price ASC;
            """,
            (product_id,)
        )

        return serialize_for_api({
            "product": product,
            "history": history,
            "events": events,
            "competing_sellers": sellers_history
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Product details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 6. Fake Discount Detector Engine (Cold-Start Safe & Informative) ---

@router.get("/fake-discounts")
def get_fake_discount_analysis(
    status: Optional[str] = "all", # 'all', 'fake', 'genuine', 'baseline'
    category: Optional[str] = None,
    min_claimed_discount: int = 5,
    page: int = 1,
    page_size: int = 20,
    user: str = Depends(verify_credentials)
):
    """
    Fake Discount Detector Algorithm with Cold-Start Baseline Protection.
    """
    try:
        offset = max(0, (page - 1) * page_size)
        where_clauses = ["p.is_active IS TRUE", "sl.available IS TRUE", "sl.discount_percent >= %s"]
        params = [min_claimed_discount]

        if category and category not in ("all", "undefined", "null", ""):
            where_clauses.append("(p.category_key = %s OR c.parent_key = %s)")
            params.extend([category, category])

        if status == "fake":
            where_clauses.append("sl.avg_price_30d > 0 AND sl.selling_price_toman > sl.avg_price_30d")
        elif status == "genuine":
            where_clauses.append("(sl.selling_price_toman <= sl.min_price_30d OR (sl.avg_price_30d > 0 AND sl.selling_price_toman < sl.avg_price_30d))")
        elif status == "baseline":
            where_clauses.append("(sl.avg_price_30d = 0 OR sl.selling_price_toman = sl.avg_price_30d)")

        where_sql = " AND ".join(where_clauses)

        stats = db.fetchone(
            f"""
            SELECT 
                COUNT(*) AS total_analyzed,
                COUNT(*) FILTER (WHERE sl.avg_price_30d > 0 AND sl.selling_price_toman > sl.avg_price_30d) AS fake_count,
                COUNT(*) FILTER (WHERE sl.selling_price_toman <= sl.min_price_30d OR (sl.avg_price_30d > 0 AND sl.selling_price_toman < sl.avg_price_30d)) AS genuine_count,
                COUNT(*) FILTER (WHERE sl.avg_price_30d = 0 OR sl.selling_price_toman = sl.avg_price_30d) AS baseline_count,
                COALESCE(MAX(sl.selling_price_toman - sl.avg_price_30d) FILTER (WHERE sl.selling_price_toman > sl.avg_price_30d AND sl.avg_price_30d > 0), 0) AS max_inflation_amount
            FROM master_products p
            LEFT JOIN categories c ON p.category_key = c.category_key
            LEFT JOIN store_listings sl ON p.product_id = sl.product_id
            WHERE p.is_active IS TRUE AND sl.available IS TRUE AND sl.discount_percent >= %s;
            """,
            (min_claimed_discount,)
        ) or {}

        count_row = db.fetchone(
            f"""
            SELECT COUNT(*) AS total
            FROM master_products p
            LEFT JOIN categories c ON p.category_key = c.category_key
            LEFT JOIN store_listings sl ON p.product_id = sl.product_id
            WHERE {where_sql};
            """,
            tuple(params)
        )
        total = count_row["total"] if count_row else 0

        query_sql = f"""
            SELECT p.product_id, p.title_fa, p.brand, p.category_key, p.image_url,
                   c.title_fa AS category_name,
                   sl.selling_price_toman, sl.rrp_price_toman, sl.discount_percent AS claimed_discount,
                   sl.seller_name, sl.product_url, sl.min_price_30d, sl.avg_price_30d,
                   CASE 
                       WHEN sl.avg_price_30d > 0 AND sl.selling_price_toman > sl.avg_price_30d THEN 'FAKE'
                       WHEN sl.selling_price_toman <= sl.min_price_30d THEN 'GENUINE_GOLDEN'
                       WHEN sl.avg_price_30d > 0 AND sl.selling_price_toman < sl.avg_price_30d THEN 'REAL_DEAL'
                       ELSE 'BASELINE_RECORDED'
                   END AS authenticity_status,
                   CASE 
                       WHEN sl.avg_price_30d > 0 THEN ROUND(((sl.avg_price_30d - sl.selling_price_toman)::NUMERIC / sl.avg_price_30d::NUMERIC) * 100.0, 1)
                       ELSE 0.0
                   END AS real_discount_vs_avg,
                   CASE 
                       WHEN sl.avg_price_30d > 0 AND sl.selling_price_toman > sl.avg_price_30d THEN (sl.selling_price_toman - sl.avg_price_30d)
                       ELSE 0
                   END AS inflation_margin_toman
            FROM master_products p
            LEFT JOIN categories c ON p.category_key = c.category_key
            LEFT JOIN store_listings sl ON p.product_id = sl.product_id
            WHERE {where_sql}
            ORDER BY 
                CASE WHEN sl.avg_price_30d > 0 AND sl.selling_price_toman > sl.avg_price_30d THEN (sl.selling_price_toman - sl.avg_price_30d) END DESC,
                sl.discount_percent DESC
            LIMIT %s OFFSET %s;
        """
        rows = db.fetchall(query_sql, tuple(params + [page_size, offset]))

        return serialize_for_api({
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "stats": {
                "total_analyzed": stats.get("total_analyzed", 0) or 0,
                "fake_count": stats.get("fake_count", 0) or 0,
                "genuine_count": stats.get("genuine_count", 0) or 0,
                "baseline_count": stats.get("baseline_count", 0) or 0,
                "max_inflation_amount": stats.get("max_inflation_amount", 0) or 0,
                "fake_ratio_percent": round((stats.get("fake_count", 0) / max(1, stats.get("total_analyzed", 1))) * 100.0, 1)
            }
        })
    except Exception as e:
        logger.error(f"Fake discounts error: {e}")
        return serialize_for_api({"items": [], "total": 0, "page": page, "page_size": page_size, "stats": {}})

# --- 7. Seller Price War & Buy Box Engine ---

@router.get("/seller-war/battles")
def get_seller_price_wars(
    category: Optional[str] = None,
    limit: int = 30,
    user: str = Depends(verify_credentials)
):
    try:
        where_clauses = ["p.is_active IS TRUE", "sl.available IS TRUE"]
        params = []

        if category and category not in ("all", "undefined", "null", ""):
            where_clauses.append("(p.category_key = %s OR c.parent_key = %s)")
            params.extend([category, category])

        where_sql = " AND ".join(where_clauses)

        query_sql = f"""
            SELECT p.product_id, p.title_fa, p.brand, p.image_url,
                   c.title_fa AS category_name,
                   sl.seller_name AS buybox_winner,
                   sl.selling_price_toman AS buybox_price,
                   sl.rrp_price_toman,
                   sl.discount_percent,
                   sl.product_url,
                   sl.min_price_30d,
                   sl.avg_price_30d,
                   COALESCE((SELECT COUNT(DISTINCT seller_name) FROM price_observations WHERE product_id = p.product_id), 1) AS competing_sellers_count,
                   COALESCE((SELECT COUNT(*) FROM price_events WHERE product_id = p.product_id AND event_type = 'price_drop'), 0) AS total_price_drops
            FROM master_products p
            LEFT JOIN categories c ON p.category_key = c.category_key
            JOIN store_listings sl ON p.product_id = sl.product_id
            WHERE {where_sql}
            ORDER BY 
                (SELECT COUNT(DISTINCT seller_name) FROM price_observations WHERE product_id = p.product_id) DESC,
                sl.discount_percent DESC
            LIMIT %s;
        """
        battles = db.fetchall(query_sql, tuple(params + [limit]))

        top_sellers = db.fetchall(
            """
            SELECT seller_name, 
                   COUNT(DISTINCT product_id) AS buybox_won_count,
                   COALESCE(AVG(discount_percent), 0.0) AS avg_discount_offered,
                   COUNT(*) FILTER (WHERE selling_price_toman <= min_price_30d) AS floor_price_wins
            FROM store_listings
            WHERE available IS TRUE AND seller_name IS NOT NULL
            GROUP BY seller_name
            ORDER BY buybox_won_count DESC
            LIMIT 10;
            """
        )

        return serialize_for_api({
            "battles": battles,
            "top_sellers": top_sellers,
            "total_battles": len(battles)
        })
    except Exception as e:
        logger.error(f"Seller war error: {e}")
        return serialize_for_api({"battles": [], "top_sellers": [], "total_battles": 0})

# --- 8. Events & Database Management ---

@router.get("/events")
def get_price_events(
    severity: Optional[str] = None,
    limit: int = 50,
    user: str = Depends(verify_credentials)
):
    try:
        where_clauses = ["1=1"]
        params = []

        if severity and severity != "all":
            where_clauses.append("e.severity = %s")
            params.append(severity)

        where_sql = " AND ".join(where_clauses)
        events = db.fetchall(
            f"""
            SELECT e.*, p.title_fa, p.brand, p.image_url, sl.product_url, sl.seller_name,
                   c.title_fa AS category_name
            FROM price_events e
            JOIN master_products p ON e.product_id = p.product_id
            LEFT JOIN categories c ON p.category_key = c.category_key
            LEFT JOIN store_listings sl ON e.product_id = sl.product_id AND e.store_key = sl.store_key
            WHERE {where_sql}
            ORDER BY e.created_at DESC
            LIMIT %s;
            """,
            tuple(params + [limit])
        )
        return serialize_for_api(events)
    except Exception as e:
        logger.error(f"Events error: {e}")
        return []

@router.get("/db-size")
def get_db_size(user: str = Depends(verify_credentials)):
    try:
        stats = StorageGuard.get_database_stats()
        return serialize_for_api(stats)
    except Exception as e:
        return serialize_for_api({
            "tables": [], "total_rows": 0, "estimated_storage_mb": 0.0,
            "estimated_storage_gb": 0.0, "quota_max_gb": 5.0, "threshold_guard_gb": 3.5,
            "usage_percent": 0.0, "is_above_threshold": False, "status": "healthy"
        })

@router.post("/wipe-database")
def wipe_all_database_data(user: str = Depends(verify_credentials)):
    try:
        tables = [
            "price_events", "price_observations", "store_listings",
            "master_products", "crawl_logs"
        ]
        cleared = {}
        for t in tables:
            try:
                cnt = db.execute(f"DELETE FROM {t};")
                cleared[t] = cnt
            except Exception as ex:
                logger.warning(f"Note deleting {t}: {ex}")

        db.execute("UPDATE categories SET product_count = 0, last_crawled_at = NULL;")

        crawler_engine._cached_listings.clear()
        crawler_engine._known_master_products.clear()
        crawler_engine._cache_initialized = False

        return serialize_for_api({
            "status": "success",
            "message": "تمامی داده‌های کالاها، قیمت‌ها و سوابق با موفقیت صفر و پاکسازی شدند.",
            "cleared": cleared
        })
    except Exception as e:
        logger.error(f"Wipe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
def get_system_status():
    health = db.check_health()
    return serialize_for_api({
        "status": "operational" if health.get("connected") else "disconnected",
        "database": health,
        "crawler_telemetry": crawler_engine.telemetry,
        "auth_enabled": AUTH_ENABLED
    })
