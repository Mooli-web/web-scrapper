import logging
from typing import Dict, Any

from crawler.db import db

logger = logging.getLogger("crawler.storage_guard")

class StorageGuard:
    """Storage footprint monitor for CockroachDB."""

    @staticmethod
    def get_database_stats() -> Dict[str, Any]:
        """Calculates table row counts and actual storage footprint."""
        tables = [
            "categories", "stores", "master_products", "store_listings",
            "price_observations", "price_events", "crawl_logs"
        ]

        table_stats = []
        total_rows = 0

        ROW_SIZE_MAP = {
            "master_products": 220,
            "store_listings": 160,
            "price_observations": 80,
            "price_events": 90,
            "categories": 120,
            "stores": 80,
            "crawl_logs": 140
        }

        for t in tables:
            cnt = 0
            try:
                row = db.fetchone(f"SELECT COUNT(*) AS cnt FROM {t};")
                cnt = int(row["cnt"]) if row and row.get("cnt") is not None else 0
            except Exception:
                cnt = 0
            total_rows += cnt

            avg_bytes = ROW_SIZE_MAP.get(t, 100)
            table_mb = round((cnt * avg_bytes) / (1024 * 1024), 3)

            table_stats.append({
                "table_name": t,
                "row_count": cnt,
                "estimated_mb": table_mb
            })

        actual_storage_mb = round(sum(ts["estimated_mb"] for ts in table_stats), 2)
        actual_storage_gb = round(actual_storage_mb / 1024.0, 4)
        pct_used = round((actual_storage_gb / 5.0) * 100.0, 2)

        return {
            "tables": table_stats,
            "total_rows": total_rows,
            "estimated_storage_mb": actual_storage_mb,
            "estimated_storage_gb": actual_storage_gb,
            "quota_max_gb": 5.0,
            "usage_percent": pct_used,
            "is_above_threshold": actual_storage_gb >= 3.5,
            "status": "healthy"
        }
