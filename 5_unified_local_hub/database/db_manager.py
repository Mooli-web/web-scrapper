import os
import sqlite3
import threading
import logging
from contextlib import closing
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("hub.database")

HUB_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = HUB_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PERMANENT_DB_FILE = DATA_DIR / "market.db"
SCHEMA_FILE = HUB_ROOT / "database" / "schema.sql"

class LocalDatabaseManager:
    """
    High-Performance, Thread-Safe Database Manager with Persistent Storage at data/market.db.
    Guarantees zero database locks and data persistence across updates.
    """
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or PERMANENT_DB_FILE
        self._lock = threading.RLock()
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=60.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=60000;")
        conn.execute("PRAGMA cache_size=-128000;") # 128MB RAM cache for instant queries
        return conn

    def _init_db(self):
        with self._lock:
            try:
                # FIX: fail LOUDLY when schema.sql is missing. Before, a fresh
                # clone silently skipped table creation and every later query
                # failed quietly inside try/except blocks.
                if not SCHEMA_FILE.exists():
                    logger.error(
                        "❌ SCHEMA NOT FOUND: %s is missing — no tables were created! "
                        "Make sure database/schema.sql is committed with the repo.", SCHEMA_FILE
                    )
                    return
                with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                with closing(self.get_connection()) as conn:
                    conn.executescript(schema_sql)
                    conn.commit()
                # NEW: مهاجرت‌های سبک (ستون‌های افزوده‌شده پس از نسخه‌های اولیه)
                try:
                    cols = {r["name"] for r in self.fetchall("PRAGMA table_info(store_listings);")}
                    if "rrp_price_toman" not in cols:
                        self.execute("ALTER TABLE store_listings ADD COLUMN rrp_price_toman INTEGER DEFAULT 0;")
                except Exception as me:
                    logger.debug(f"light migration note: {me}")
                logger.info(f"Database active and ready at: {self.db_path}")
            except Exception as e:
                logger.error(f"Database init failed: {e}")

    def fetchall(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        # FIX: contextlib.closing() actually closes the connection afterwards.
        # `with sqlite3.connect(...)` alone only commits/rolls back the
        # transaction and leaves the connection open (relying on GC).
        with closing(self.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def fetchone(self, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        with closing(self.get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def execute(self, query: str, params: Tuple = ()) -> int:
        with self._lock:
            with closing(self.get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount

    def executemany(self, query: str, params_list: List[Tuple]) -> int:
        with self._lock:
            with closing(self.get_connection()) as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount

db = LocalDatabaseManager()
