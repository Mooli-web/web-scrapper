import logging
from typing import Dict, Any, List
from sync.ingest_digikala import ingest_digikala_items
from sync.ingest_torob import ingest_torob_items
from sync.ingest_divar import ingest_divar_items
from sync.ingest_esam import ingest_esam_items
from core.arbitrage_engine import arbitrage_engine
from core.ai_dataset_generator import ai_exporter
from database.db_manager import db

logger = logging.getLogger("hub.master_sync")

class MasterDataHubOrchestrator:
    """
    Master Ingestion & Arbitrage Synchronization Engine.
    Coordinates real-time aggregation across Digikala, Torob, Divar, and Esam into Local Master DB.
    """
    def __init__(self):
        pass

    def sync_batch(
        self,
        digikala_items: List[Dict[str, Any]] = None,
        torob_items: List[Dict[str, Any]] = None,
        divar_items: List[Dict[str, Any]] = None,
        esam_items: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Ingests multi-market batch, matches entities, updates prices, and calculates arbitrage spreads.
        """
        c_digi = ingest_digikala_items(digikala_items or [])
        c_torob = ingest_torob_items(torob_items or [])
        c_divar = ingest_divar_items(divar_items or [])
        c_esam = ingest_esam_items(esam_items or [])

        total_ingested = c_digi + c_torob + c_divar + c_esam

        # Run Arbitrage and Depreciation Analysis
        arb_res = arbitrage_engine.run_arbitrage_scan()

        # Log Sync Results
        db.execute("""
            INSERT INTO sync_logs (source, items_synced, matches_found, opportunities_found, status, details)
            VALUES ('MASTER_PIPELINE', ?, ?, ?, 'SUCCESS', ?);
        """, (
            total_ingested,
            arb_res['products_scanned'],
            arb_res['opportunities_found'],
            f"Digikala: {c_digi}, Torob: {c_torob}, Divar: {c_divar}, Esam: {c_esam}"
        ))

        # Auto export AI datasets
        ai_res = ai_exporter.export_all()

        return {
            "status": "success",
            "total_ingested": total_ingested,
            "breakdown": {
                "digikala": c_digi,
                "torob": c_torob,
                "divar": c_divar,
                "esam": c_esam
            },
            "canonical_products_analyzed": arb_res['products_scanned'],
            "arbitrage_opportunities": arb_res['opportunities_found'],
            "ai_samples_ready": ai_res.get("samples_count", 0)
        }

orchestrator = MasterDataHubOrchestrator()
