import json
import csv
import logging
from pathlib import Path
from typing import Dict, Any, List
from database.db_manager import db
from core.taxonomy import normalize_category, category_label

logger = logging.getLogger("hub.ai_exporter")

EXPORTS_DIR = Path(__file__).resolve().parent.parent / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

class AIDatasetGenerator:
    """
    Exports structured, high-quality feature matrices for Machine Learning,
    Price Forecasting, and Depreciation Curve training.
    """
    def __init__(self):
        pass

    def generate_tabular_dataset(self) -> List[Dict[str, Any]]:
        """
        Creates an ML-ready dataset combining canonical product metadata with store observations.
        """
        rows = db.fetchall("""
            SELECT
                l.id as listing_id,
                l.canonical_key,
                l.store_key,
                l.title_fa,
                l.price_toman,
                l.condition,
                l.rating_score,
                l.reviews_count,
                l.rrp_price_toman,
                l.is_auction,
                l.bids_count,
                l.observed_at,
                c.brand,
                c.category_key,
                c.digikala_price_toman,
                c.torob_min_price_toman,
                c.torob_shops_count,
                c.depreciation_percent
            FROM store_listings l
            JOIN canonical_products c ON l.canonical_key = c.canonical_key
            WHERE l.price_toman > 0;
        """)

        dataset = []
        for r in rows:
            new_ref = r['torob_min_price_toman'] or r['digikala_price_toman'] or r['price_toman']
            discount_pct = round(((new_ref - r['price_toman']) / new_ref) * 100.0, 2) if new_ref > 0 else 0.0

            # Condition encoding numeric
            cond_score = 1.0
            if 'در حد نو' in (r['condition'] or ''):
                cond_score = 0.85
            elif 'استوک' in (r['condition'] or ''):
                cond_score = 0.75
            elif 'دست دوم' in (r['condition'] or ''):
                cond_score = 0.65
            elif 'معیوب' in (r['condition'] or ''):
                cond_score = 0.20

            std_cat = normalize_category(r['category_key'], r['title_fa'] or "")
            dataset.append({
                "canonical_key": r['canonical_key'],
                "brand": r['brand'] or 'unknown',
                "category": r['category_key'] or 'digital',
                "category_std": std_cat,
                "category_std_fa": category_label(std_cat),
                "store": r['store_key'],
                "condition_raw": r['condition'],
                "condition_weight": cond_score,
                "is_auction": 1 if r['is_auction'] else 0,
                "bids_count": r['bids_count'] or 0,
                "seller_rating": float(r['rating_score'] or 0.0),   # NEW: امتیاز نظرات (ویژگی پیش‌بینی قیمت)
                "reviews_count": int(r['reviews_count'] or 0),
                "rrp_price_toman": int(r['rrp_price_toman'] or 0),   # NEW: قیمت قبل تخفیف دیجی‌کالا
                "market_floor_price_toman": new_ref,
                "listing_price_toman": r['price_toman'],
                "discount_vs_floor_percent": discount_pct,
                "depreciation_percent": r['depreciation_percent'] or 0.0,
                "is_arbitrage_opportunity": 1 if discount_pct >= 20.0 else 0,
                "observed_at": r['observed_at']
            })

        return dataset

    def export_all(self) -> Dict[str, Any]:
        """Exports dataset to CSV and JSON formats."""
        dataset = self.generate_tabular_dataset()
        if not dataset:
            return {"status": "empty", "rows_count": 0}

        # 1. Export JSON
        json_path = EXPORTS_DIR / "quad_market_dataset.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

        # 2. Export CSV
        csv_path = EXPORTS_DIR / "quad_market_dataset.csv"
        headers = list(dataset[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(dataset)

        logger.info(f"AI Dataset exported: {len(dataset)} samples saved to {EXPORTS_DIR}")
        return {
            "status": "success",
            "samples_count": len(dataset),
            "json_path": str(json_path),
            "csv_path": str(csv_path)
        }

ai_exporter = AIDatasetGenerator()
