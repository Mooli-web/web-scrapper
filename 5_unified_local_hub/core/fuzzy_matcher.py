import json
import threading
import logging
from typing import Dict, Any, Optional, Tuple, List
from core.normalizer import clean_persian_text, generate_canonical_key, extract_storage_and_specs
from database.db_manager import db

logger = logging.getLogger("hub.matcher")

def token_similarity(s1: str, s2: str) -> float:
    words1 = set(s1.split())
    words2 = set(s2.split())
    if not words1 or not words2:
        return 0.0
    return len(words1.intersection(words2)) / len(words1.union(words2))

class EntityMatcher:
    """
    Ultra-Fast, Thread-Safe Entity Matcher.
    Uses O(1) canonical key hashing with indexed brand buckets.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._canonical_cache: Dict[str, Dict[str, Any]] = {}
        self._brand_index: Dict[str, List[str]] = {}
        self._load_cache()

    def _load_cache(self):
        with self._lock:
            try:
                rows = db.fetchall("SELECT canonical_key, title_fa, brand, category_key FROM canonical_products;")
                for r in rows:
                    k = r['canonical_key']
                    b = r['brand'] or 'other'
                    self._canonical_cache[k] = r
                    self._brand_index.setdefault(b, []).append(k)
                logger.info(f"Loaded {len(self._canonical_cache)} canonical products into fast matcher index.")
            except Exception as e:
                logger.warning(f"Matcher cache init note: {e}")

    def resolve_canonical_product(self, raw_title: str, category_hint: str = "", brand_hint: str = "") -> Tuple[str, str]:
        with self._lock:
            canonical_key, detected_brand, detected_cat = generate_canonical_key(raw_title, category_hint)
            brand = brand_hint or detected_brand
            category = category_hint or detected_cat

            # 1. Instant O(1) exact key match
            if canonical_key in self._canonical_cache:
                return canonical_key, self._canonical_cache[canonical_key]['title_fa']

            # 2. Fast brand-bucketed fuzzy match
            clean_title = clean_persian_text(raw_title)
            lower_clean = clean_title.lower()
            
            candidate_keys = self._brand_index.get(brand, [])
            if len(candidate_keys) < 200: # Fast bucket comparison
                for c_key in candidate_keys:
                    c_info = self._canonical_cache.get(c_key)
                    if c_info:
                        score = token_similarity(lower_clean, c_info['title_fa'].lower())
                        if score >= 0.70:
                            return c_key, c_info['title_fa']

            # 3. Create new canonical product
            specs = extract_storage_and_specs(raw_title)
            specs_str = json.dumps(specs, ensure_ascii=False)

            try:
                db.execute("""
                    INSERT INTO canonical_products (
                        canonical_key, title_fa, brand, category_key, specs_json, last_synced_at
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(canonical_key) DO UPDATE SET
                        last_synced_at = CURRENT_TIMESTAMP;
                """, (canonical_key, clean_title, brand, category, specs_str))

                info = {
                    'canonical_key': canonical_key,
                    'title_fa': clean_title,
                    'brand': brand,
                    'category_key': category
                }
                self._canonical_cache[canonical_key] = info
                self._brand_index.setdefault(brand, []).append(canonical_key)
            except Exception as e:
                logger.debug(f"Canonical product insert skipped: {e}")

            return canonical_key, clean_title

matcher = EntityMatcher()
