import os
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from server.routes import router
from server.ai_relay import router as ai_relay_router  # NEW: Groq relay for local hub
from crawler.engine import esam_crawler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("esam.server")

app = FastAPI(title="Esam Cloud Price & Auction Intelligence Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ai_relay_router)  # NEW: /ai-relay/v1/* forwards to Groq

@app.on_event("startup")
async def startup_event():
    logger.info("Esam Cloud Web Service is running on Render / Local.")
    auto_start = os.getenv("AUTO_START_CRAWLER", "false").lower() in ("true", "1", "yes")
    
    if auto_start:
        logger.info("Starting internal 24/7 Esam continuous background worker...")
        import threading
        threading.Thread(target=esam_crawler.run_continuous_loop, daemon=True).start()

# Mount React frontend static assets if built
dashboard_dist = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if dashboard_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(dashboard_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        if full_path.startswith("api/"):
            return None
        file_path = dashboard_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dashboard_dist / "index.html")
else:
    @app.get("/")
    def index():
        return {
            "status": "online",
            "service": "Esam Cloud Crawler & Auction Intelligence Engine",
            "docs": "/docs",
            "db_health": "/api/database/test-connection",
            "items_api": "/api/esam/items"
        }
