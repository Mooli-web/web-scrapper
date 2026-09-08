import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from server.routes import router

# NEW: چرخه‌ی خودکار (سینک + پالایش + AI + آربیتراژ) — با بالا آمدن سرور فعال می‌شود
from sync.auto_sync import auto_sync_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("hub.server")

app = FastAPI(
    title="Quad-Market Master Intelligence Hub",
    description="Unified Local Aggregator & Arbitrage Platform for Digikala, Torob, Divar, and Esam",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"

@app.on_event("startup")
async def _start_auto_sync_scheduler():
    auto_sync_scheduler.start()

@app.get("/review")
def serve_review_desk():
    # NEW: میز بررسی متمرکز — فقط باقی‌مانده‌های همه‌ی دسته‌ها
    f = DASHBOARD_DIR / "review.html"
    if f.exists():
        return FileResponse(f)
    return {"status": "online", "note": "review.html not found"}

@app.get("/")
def serve_dashboard():
    index_file = DASHBOARD_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "status": "online",
        "service": "Quad-Market Master Intelligence Hub",
        "api_docs": "/docs",
        "status_endpoint": "/api/status"
    }

# Also serve exports if needed
EXPORTS_DIR = Path(__file__).resolve().parent.parent / "exports"
if EXPORTS_DIR.exists():
    app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")
