import os
import re
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import psycopg
from psycopg.rows import dict_row

from crawler.config import DATABASE_URL

logger = logging.getLogger("crawler.db")

def _prepare_dsn(dsn: str) -> str:
    """Bulletproof CockroachDB DSN sanitizer."""
    if not dsn:
        return ""
    cleaned = dsn.strip().strip("'").strip('"').strip()
    cleaned = re.sub(r'sslmode=verify[^\s&"\']*', 'sslmode=require', cleaned)
    if 'sslmode=' not in cleaned:
        separator = '&' if '?' in cleaned else '?'
        cleaned = f"{cleaned}{separator}sslmode=require"
    return cleaned

def json_serialize(obj: Any) -> Any:
    from datetime import datetime, date
    from decimal import Decimal
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return obj

class DatabaseManager:
    def __init__(self, dsn: Optional[str] = None):
        self.raw_dsn = (dsn or DATABASE_URL).strip()
        self.dsn = _prepare_dsn(self.raw_dsn)

    def is_configured(self) -> bool:
        return bool(self.dsn and (self.dsn.startswith("postgresql://") or self.dsn.startswith("postgres://")))

    def get_connection(self):
        if not self.is_configured():
            raise ConnectionError("DATABASE_URL is missing or invalid.")
        eff_dsn = _prepare_dsn(self.raw_dsn or os.getenv("DATABASE_URL", ""))
        return psycopg.connect(eff_dsn, connect_timeout=12, row_factory=dict_row)

    def check_health(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "disconnected",
                "connected": False,
                "latency_ms": 0,
                "error": "DATABASE_URL is missing.",
                "hint": "Set DATABASE_URL in Render Dashboard or .env file."
            }

        t0 = time.perf_counter()
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 AS ok, current_database() AS db_name, version() AS ver;")
                    row = cur.fetchone()
                    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                    return {
                        "status": "healthy",
                        "connected": True,
                        "engine": "CockroachDB Serverless (PostgreSQL Wire Compatible)",
                        "database_name": row.get("db_name") if row else "defaultdb",
                        "latency_ms": latency_ms
                    }
        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "status": "error",
                "connected": False,
                "latency_ms": latency_ms,
                "error": str(e)
            }

    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()

    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchone()

    def execute(self, sql: str, params: Optional[Tuple] = None) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                conn.commit()
                return cur.rowcount

    def execute_script(self, script_sql: str):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(script_sql)
            conn.commit()

db = DatabaseManager()
