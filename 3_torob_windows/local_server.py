import os
import time
import io
import csv
import json
import logging
import threading
import webbrowser
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import uvicorn

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        example_env = Path(__file__).resolve().parent / ".env.example"
        if example_env.exists():
            load_dotenv(dotenv_path=example_env, override=True)
except ImportError:
    pass

from torob_catalog_crawler import torob_catalog_engine, TOROB_CATEGORIES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("local.server")

app = FastAPI(title="Independent Torob Deep Intelligence Engine", version="10.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LocalState:
    def __init__(self):
        self.log_counter = 0
        self.log_history: List[Dict[str, Any]] = []

state = LocalState()

def emit_local_log(level: str, message: str):
    state.log_counter += 1
    now_str = datetime.now().strftime("%H:%M:%S")
    entry = {
        "id": state.log_counter,
        "time": now_str,
        "level": level,
        "message": message
    }
    state.log_history.append(entry)
    if len(state.log_history) > 400:
        state.log_history.pop(0)
    torob_catalog_engine.telemetry["latest_log"] = message
    logger.info(f"[{level}] {message}")

def run_continuous_torob_loop(category_filter: str = "all", pages_per_cat: int = 15):
    torob_catalog_engine.is_running = True
    torob_catalog_engine.stop_requested = False
    torob_catalog_engine.telemetry["status"] = "running"
    
    emit_local_log("INFO", f"🚀 راه‌اندازی مرورگر و آغاز خزش کاتالوگ ترب ({len(TOROB_CATEGORIES)} شاخه | تا {pages_per_cat} صفحه)...")

    cats_to_crawl = TOROB_CATEGORIES
    if category_filter and category_filter != "all":
        cats_to_crawl = [c for c in TOROB_CATEGORIES if c["key"] == category_filter] or TOROB_CATEGORIES

    try:
        torob_catalog_engine.start_driver()
        
        while not torob_catalog_engine.stop_requested:
            for idx, cat in enumerate(cats_to_crawl, 1):
                if torob_catalog_engine.stop_requested:
                    break

                emit_local_log("INFO", f"📁 [{idx}/{len(cats_to_crawl)}] ورود به شاخه ترب: {cat['name']}...")
                torob_catalog_engine.crawl_category_pages(cat, max_pages=pages_per_cat, emit_log_fn=emit_local_log)

                if not torob_catalog_engine.stop_requested:
                    pause = 8
                    emit_local_log("INFO", f"☕ پایان شاخه {cat['name']} | استراحت ارگانیک {pause} ثانیه‌ای...")
                    time.sleep(pause)

            if category_filter != "all":
                emit_local_log("INFO", f"🏁 خزش شاخه {category_filter} با موفقیت به اتمام رسید.")
                break
            else:
                emit_local_log("INFO", "🔄 پایان یک دور کامل؛ آغاز دور جدید پایش پیوسته...")
                time.sleep(20)

    except Exception as e:
        logger.error(f"Continuous Torob loop error: {e}")
        emit_local_log("ERROR", f"⚠️ خطای حلقه خزش: {e}")
    finally:
        torob_catalog_engine.is_running = False
        torob_catalog_engine.telemetry["status"] = "idle"
        emit_local_log("WARNING", "⏹️ خزش متوقف شد.")

# --- API Routes ---

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    html_path = Path(__file__).resolve().parent / "local_dashboard.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Local Dashboard HTML not found</h1>"

@app.get("/api/local/status")
def get_status():
    items = list(torob_catalog_engine.catalog.values())
    total_count = len(items)
    
    # Calculate deep statistics
    avg_price = round(sum(i.get("price", 0) for i in items) / max(1, total_count)) if total_count > 0 else 0
    max_shops_item = max(items, key=lambda x: x.get("num_shops", 1), default={})
    cheapest_item = min((i for i in items if i.get("price", 0) > 0), key=lambda x: x.get("price", 0), default={})
    most_expensive_item = max(items, key=lambda x: x.get("price", 0), default={})

    # Category breakdown stats
    cat_counts = {}
    for i in items:
        ck = i.get("category_name") or "متفرقه"
        cat_counts[ck] = cat_counts.get(ck, 0) + 1

    return {
        "telemetry": torob_catalog_engine.telemetry,
        "total_products": total_count,
        "avg_price": avg_price,
        "max_shops_item": max_shops_item,
        "cheapest_item": cheapest_item,
        "most_expensive_item": most_expensive_item,
        "category_counts": cat_counts,
        "categories": TOROB_CATEGORIES
    }

@app.get("/api/local/logs-stream")
def get_logs_stream(after_id: int = 0):
    new_logs = [l for l in state.log_history if l["id"] > after_id]
    return {
        "new_logs": new_logs,
        "latest_id": state.log_counter,
        "telemetry": torob_catalog_engine.telemetry
    }

@app.get("/api/local/torob-products")
def get_torob_products(
    search: Optional[str] = None,
    category: Optional[str] = "all",
    sort_by: str = "newest",
    page: int = 1,
    page_size: int = 20
):
    items = list(torob_catalog_engine.catalog.values())

    if search:
        s_lower = search.strip().lower()
        items = [i for i in items if s_lower in i.get("title", "").lower()]

    if category and category != "all":
        items = [i for i in items if i.get("category_key") == category]

    if sort_by == "price_asc":
        items.sort(key=lambda x: x.get("price", 0))
    elif sort_by == "price_desc":
        items.sort(key=lambda x: x.get("price", 0), reverse=True)
    elif sort_by == "shops_desc":
        items.sort(key=lambda x: x.get("num_shops", 1), reverse=True)
    else:
        items.reverse()

    total = len(items)
    offset = max(0, (page - 1) * page_size)
    paginated = items[offset:offset + page_size]

    return {
        "items": paginated,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size)
    }

@app.post("/api/local/start")
def start_scan(
    background_tasks: BackgroundTasks,
    category: Optional[str] = Query(default="all"),
    pages: int = Query(default=15)
):
    if torob_catalog_engine.is_running:
        return {"status": "already_running", "message": "خزنده در حال حاضر فعال است."}
    background_tasks.add_task(run_continuous_torob_loop, category, pages)
    return {"status": "started", "message": f"خزش عمیق با سقف {pages} صفحه آغاز شد."}

@app.post("/api/local/stop")
def stop_scan():
    torob_catalog_engine.stop_requested = True
    torob_catalog_engine.telemetry["status"] = "stopped"
    emit_local_log("WARNING", "⏹️ دستور توقف خزش ارسال شد.")
    return {"status": "stopping", "message": "خزنده متوقف شد."}

@app.get("/api/local/export-csv")
def export_torob_csv():
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["شناسه / کلید کالا", "عنوان کالا در ترب", "کف قیمت ترب (تومان)", "تعداد فروشندگان", "دسته‌بندی", "لینک ترب", "زمان ثبت"])

    for item in torob_catalog_engine.catalog.values():
        writer.writerow([
            item.get("key", ""),
            item.get("title", ""),
            item.get("price", 0),
            item.get("num_shops", 1),
            item.get("category_name", ""),
            item.get("url", ""),
            item.get("last_seen_at", "")
        ])

    output.seek(0)
    filename = f"torob_catalog_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

def open_browser_after_startup():
    time.sleep(1.5)
    url = "http://localhost:5000"
    print("\n" + "=" * 60)
    print(f"🌐 باز کردن خودکار داشبورد در مرورگر: {url}")
    print("=" * 60 + "\n")
    webbrowser.open(url)

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Deep Torob Continuous Crawler Engine Starting...")
    print("🌐 Dashboard URL: http://localhost:5000")
    print("=" * 60)
    
    threading.Thread(target=open_browser_after_startup, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="info")
