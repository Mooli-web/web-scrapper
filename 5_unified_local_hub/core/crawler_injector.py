import os
import json
import logging
from typing import Dict, Any, List
from pathlib import Path
from database.db_manager import db
from core.groq_client import groq_client

logger = logging.getLogger("hub.crawler_injector")

EXPORTS_DIR = Path(__file__).resolve().parent.parent / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
SEEDS_FILE = EXPORTS_DIR / "crawler_seeds.json"

def map_divar_category(category_key: str, title: str = "") -> str:
    """
    FIX: the old mapping only knew mobile/laptop/game-consoles, so smartwatches
    (and everything else) were seeded with category 'game-consoles'.
    NOTE: align these return values with the real slugs in your
    2_divar_cloud `divar_categories` table if they differ.
    """
    c = (category_key or '').lower()
    t = (title or '')
    if 'mobile' in c or 'phone' in c:
        return 'mobile-phones'
    if 'laptop' in c or 'notebook' in c or 'ultrabook' in c:
        return 'laptops'
    if 'watch' in c or 'ساعت' in t or 'watch' in t.lower():
        return 'wearables'
    if 'console' in c or 'بازی' in t:
        return 'game-consoles'
    if 'gpu' in c or 'graphic' in c or 'کارت گرافیک' in t:
        return 'computer-parts'
    # Unknown -> empty string means "search without category filter" (safer than
    # forcing a wrong category).
    return ''

class CrawlerFeedbackLoopEngine:
    """
    Automated AI Crawler Feedback Loop & Taxonomy Seed Injector.
    Takes discovered market models from Digikala/Master DB, generates target queries,
    and feeds them to Divar, Esam, and Torob crawlers for laser-focused catalog expansion.
    """
    def __init__(self):
        pass

    def extract_active_market_models(self) -> List[Dict[str, Any]]:
        """Extracts top canonical products and models from master database."""
        rows = db.fetchall("""
            SELECT canonical_key, title_fa, brand, category_key, digikala_price_toman, torob_min_price_toman
            FROM canonical_products
            ORDER BY last_synced_at DESC
            LIMIT 200;
        """)
        return rows

    def generate_crawler_seeds(self) -> Dict[str, Any]:
        """
        Generates targeted search queries for Divar, Esam, and Torob.
        """
        models = self.extract_active_market_models()
        divar_seeds = []
        esam_seeds = []
        torob_seeds = []

        seen_queries = set()

        for m in models:
            title = m['title_fa']
            brand = m.get('brand') or ''
            cat = m.get('category_key') or 'digital'
            c_key = m.get('canonical_key') or ''

            # Create focused search phrase (e.g. 'iPhone 13 128', 'PS5 Slim', 'RTX 4060', 'MacBook M3')
            words = title.split()
            core_words = [w for w in words if w not in ['مدل', 'گوشی', 'موبایل', 'کنسول', 'بازی', 'اینچ', 'دو', 'تک', 'سیم', 'کارت', 'گارانتی', 'اصلی']][:4]
            query_phrase = " ".join(core_words)

            if len(query_phrase) >= 3 and query_phrase not in seen_queries:
                seen_queries.add(query_phrase)

                # Divar seed (FIX: uses the dedicated category mapper)
                divar_seeds.append({
                    "query": query_phrase,
                    "category": map_divar_category(cat, title),
                    "target_canonical_key": c_key
                })

                # Esam seed
                esam_seeds.append({
                    "query": query_phrase,
                    "target_canonical_key": c_key
                })

                # Torob seed
                torob_seeds.append({
                    "name": title[:40],
                    "query": query_phrase,
                    "category_key": cat
                })

        seeds_payload = {
            "generated_at": db.fetchone("SELECT CURRENT_TIMESTAMP as now;")['now'],
            "total_seeds": len(seen_queries),
            "divar_seeds_count": len(divar_seeds),
            "esam_seeds_count": len(esam_seeds),
            "torob_seeds_count": len(torob_seeds),
            "divar_seeds": divar_seeds[:100],
            "esam_seeds": esam_seeds[:100],
            "torob_seeds": torob_seeds[:100]
        }

        # Save to file
        with open(SEEDS_FILE, "w", encoding="utf-8") as f:
            json.dump(seeds_payload, f, ensure_ascii=False, indent=2)

        logger.info(f"Generated {len(seen_queries)} targeted crawler seeds saved to {SEEDS_FILE}")
        return seeds_payload

crawler_injector = CrawlerFeedbackLoopEngine()
