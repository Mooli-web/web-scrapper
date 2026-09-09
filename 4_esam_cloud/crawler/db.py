import os
import re
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
import psycopg
from psycopg.rows import dict_row

from crawler.config import DATABASE_URL

logger = logging.getLogger("esam.db")

def _prepare_dsn(dsn: str) -> str:
    """
    Bulletproof CockroachDB DSN sanitizer:
    - Strips quotes and whitespace
    - Replaces any verify-full or truncated sslmode with sslmode=require
    - Guarantees clean connection on Render and local environments
    """
    if not dsn:
        return ""
    cleaned = dsn.strip().strip("'").strip('"').strip()
    cleaned = re.sub(r'sslmode=verify[^\s&"\']*', 'sslmode=require', cleaned)
    if 'sslmode=' not in cleaned:
        separator = '&' if '?' in cleaned else '?'
        cleaned = f"{cleaned}{separator}sslmode=require"
    return cleaned

class EsamDatabaseManager:
    def __init__(self, dsn: Optional[str] = None):
        self.raw_dsn = (dsn or DATABASE_URL).strip()
        self.dsn = _prepare_dsn(self.raw_dsn)

    def is_configured(self) -> bool:
        return bool(self.dsn and (self.dsn.startswith("postgresql://") or self.dsn.startswith("postgres://")))

    def get_connection(self):
        if not self.is_configured():
            raise ConnectionError("DATABASE_URL is not configured.")
        eff_dsn = _prepare_dsn(self.raw_dsn or os.getenv("DATABASE_URL", ""))
        return psycopg.connect(eff_dsn, connect_timeout=12, row_factory=dict_row)

    def check_health(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "disconnected",
                "connected": False,
                "latency_ms": 0,
                "error": "DATABASE_URL is missing."
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
                        "engine": "CockroachDB Serverless",
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

    def auto_init_schema(self):
        """Initializes tables and seeds categories automatically if not present."""
        if not self.is_configured():
            return
        try:
            schema_sql = """
            CREATE TABLE IF NOT EXISTS esam_items (
                id SERIAL PRIMARY KEY,
                item_id VARCHAR(100) UNIQUE NOT NULL,
                title_fa TEXT NOT NULL,
                category_key VARCHAR(100) NOT NULL,
                category_name_fa VARCHAR(150),
                brand VARCHAR(150),
                condition VARCHAR(100) DEFAULT 'دست دوم',
                is_auction BOOLEAN DEFAULT FALSE,
                selling_price_toman BIGINT DEFAULT 0,
                base_price_toman BIGINT DEFAULT 0,
                buy_now_price_toman BIGINT DEFAULT 0,
                bids_count INT DEFAULT 0,
                time_remaining VARCHAR(100),
                seller_name VARCHAR(150),
                seller_score VARCHAR(50),
                seller_city VARCHAR(100),
                url TEXT NOT NULL,
                image_url TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                first_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                price_updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS esam_price_observations (
                id SERIAL PRIMARY KEY,
                item_id VARCHAR(100) NOT NULL REFERENCES esam_items(item_id) ON DELETE CASCADE,
                price_toman BIGINT NOT NULL,
                is_auction BOOLEAN DEFAULT FALSE,
                bids_count INT DEFAULT 0,
                observed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS esam_price_events (
                id SERIAL PRIMARY KEY,
                item_id VARCHAR(100) NOT NULL REFERENCES esam_items(item_id) ON DELETE CASCADE,
                title_fa TEXT NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                old_price_toman BIGINT,
                new_price_toman BIGINT,
                price_change_toman BIGINT,
                change_percent NUMERIC(6, 2),
                severity VARCHAR(20) DEFAULT 'INFO',
                detected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS esam_categories (
                id SERIAL PRIMARY KEY,
                category_key VARCHAR(100) UNIQUE NOT NULL,
                title_fa VARCHAR(150) NOT NULL,
                category_code VARCHAR(50),
                query_slug VARCHAR(200),
                is_auction_feed BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                items_count INT DEFAULT 0,
                last_crawled_at TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS crawler_telemetry (
                key VARCHAR(50) PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS crawler_logs (
                id SERIAL PRIMARY KEY,
                level VARCHAR(20) NOT NULL,
                message TEXT NOT NULL,
                category_key VARCHAR(100),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """
            self.execute_script(schema_sql)
            logger.info("CockroachDB Esam schema auto-initialized successfully.")
        except Exception as e:
            logger.warning(f"Schema auto-init note: {e}")

db = EsamDatabaseManager()
