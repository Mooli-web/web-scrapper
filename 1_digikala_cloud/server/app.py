import os
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.routes import router, active_ws_clients
from server.ai_relay import router as ai_relay_router  # NEW: Groq relay for local hub
from crawler.engine import crawler_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("server.app")

ENABLE_INTERNAL_SCHEDULER = os.getenv("ENABLE_INTERNAL_SCHEDULER", "true").lower() in ("true", "1", "yes")

async def background_crawler_loop():
    """Starts slow, continuous 24/7 background crawling on boot."""
    logger.info("Continuous background crawler loop starting in 15 seconds...")
    await asyncio.sleep(15)
    
    while True:
        try:
            if not crawler_engine.is_running:
                logger.info("Starting continuous market crawler cycle...")
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, crawler_engine.run_continuous_loop)
        except Exception as e:
            logger.error(f"Error in background crawler loop: {e}")
        await asyncio.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = None
    if ENABLE_INTERNAL_SCHEDULER:
        worker_task = asyncio.create_task(background_crawler_loop())
    yield
    if worker_task:
        worker_task.cancel()

app = FastAPI(
    title="Market Intelligence Engine",
    description="Continuous High-Precision Commodity Price Monitoring",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ai_relay_router)  # NEW: /ai-relay/v1/* forwards to Groq

# Live WebSocket Telemetry
@app.websocket("/ws/crawler-live")
async def websocket_crawler_live(websocket: WebSocket):
    await websocket.accept()
    active_ws_clients.append(websocket)
    try:
        await websocket.send_json(crawler_engine.telemetry)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_ws_clients:
            active_ws_clients.remove(websocket)
    except Exception:
        if websocket in active_ws_clients:
            active_ws_clients.remove(websocket)

# Mount Frontend Build
dist_path = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if dist_path.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="API route not found")
        file_target = dist_path / full_path
        if file_target.is_file():
            return FileResponse(file_target)
        return FileResponse(dist_path / "index.html")
else:
    @app.get("/")
    def root_api():
        return {
            "app": "Market Intelligence Engine API",
            "version": "2.0.0",
            "status": "online"
        }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=True)
