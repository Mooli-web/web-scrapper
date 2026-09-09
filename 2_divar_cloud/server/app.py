import os
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from server.routes import router, active_ws_clients, broadcast_telemetry
from server.ai_relay import router as ai_relay_router  # NEW: Groq relay for local hub
from crawler.engine import divar_crawler
from crawler.config import CONTINUOUS_MODE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("divar.server")

app = FastAPI(title="Divar Cloud Crawler Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ai_relay_router)  # NEW: /ai-relay/v1/* forwards to Groq

@app.websocket("/ws/crawler-live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_ws_clients.append(websocket)
    await websocket.send_json({"telemetry": divar_crawler.telemetry})
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        if websocket in active_ws_clients:
            active_ws_clients.remove(websocket)

@app.on_event("startup")
async def startup_event():
    logger.info("Divar Cloud Web Service is running on Render.")
    enable_scheduler = os.getenv("ENABLE_INTERNAL_SCHEDULER", "true").lower() in ("true", "1", "yes")
    
    if enable_scheduler and CONTINUOUS_MODE:
        logger.info("Starting internal 24/7 Divar continuous background worker...")
        def run_in_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            def on_event(payload):
                try:
                    loop.run_until_complete(broadcast_telemetry(payload))
                except Exception:
                    pass
            divar_crawler.run_continuous_loop(progress_callback=on_event)

        import threading
        threading.Thread(target=run_in_thread, daemon=True).start()

# Mount React frontend static assets if built
dashboard_dist = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if dashboard_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(dashboard_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
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
            "service": "Divar Cloud Crawler Engine",
            "docs": "/docs",
            "api_status": "/api/status"
        }
