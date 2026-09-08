import logging
from typing import Dict, Any, List, Tuple
from database.db_manager import db

logger = logging.getLogger("hub.arbitrage")

class ArbitrageOpportunityEngine:
    """
    Verified-Only, Zero-Duplication Arbitrage Engine.
    Operates strictly on VERIFIED clean listings (is_verified = 1).
    Guarantees that each canonical product has at most ONE single best deal per store.
    """
    def __init__(self):
        pass

    def run_arbitrage_scan(self) -> Dict[str, Any]:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Clear old arbitrage deals to guarantee ZERO duplicate rows
            cursor.execute("DELETE FROM arbitrage_opportunities;")

            # 2. Fast aggregated calculation across verified listings
            # FIX: مرجع مقاوم (میانه) به‌جای MIN — در غیر این صورت همین موتور
            # ستون‌های مقاومِ محاسبه‌شده در پالایش را با MIN مسموم بازنویسی می‌کرد.
            from core.data_cleaner import robust_reference, _mean
            cursor.execute("""
                SELECT l.canonical_key, l.store_key, l.price_toman
                FROM store_listings l
                WHERE l.price_toman > 0 AND l.is_verified = 1;
            """)
            price_rows = cursor.fetchall()

            per_key: Dict[str, Dict[str, list]] = {}
            for pr in price_rows:
                bucket = per_key.setdefault(pr['canonical_key'], {'digikala': [], 'torob': [], 'divar': [], 'esam': []})
                if pr['store_key'] in bucket:
                    bucket[pr['store_key']].append(pr['price_toman'])

            update_params = []
            for c_key, bucket in per_key.items():
                digi_price = robust_reference(bucket['digikala'])
                torob_price = robust_reference(bucket['torob'])
                divar_min = min(bucket['divar']) if bucket['divar'] else 0
                divar_avg = int(_mean(bucket['divar']))
                esam_min = min(bucket['esam']) if bucket['esam'] else 0
                esam_avg = int(_mean(bucket['esam']))

                new_ref = torob_price or digi_price or 0
                used_prices = [p for p in [divar_avg, esam_avg] if p > 0]
                depreciation_pct = 0.0
                if new_ref > 0 and used_prices:
                    avg_used = sum(used_prices) / len(used_prices)
                    depreciation_pct = round(((new_ref - avg_used) / new_ref) * 100.0, 1)

                update_params.append((
                    digi_price, torob_price, divar_avg, divar_min,
                    esam_avg, esam_min, depreciation_pct, c_key
                ))

            cursor.executemany("""
                UPDATE canonical_products SET
                    digikala_price_toman = ?,
                    torob_min_price_toman = ?,
                    divar_avg_price_toman = ?,
                    divar_min_price_toman = ?,
                    esam_avg_price_toman = ?,
                    esam_min_price_toman = ?,
                    depreciation_percent = ?,
                    last_synced_at = CURRENT_TIMESTAMP
                WHERE canonical_key = ?;
            """, update_params)

            # 3. Find Arbitrage Deals with Single-Best Deduplication and Verified Gate
            cursor.execute("""
                SELECT
                    l.canonical_key,
                    l.title_fa,
                    l.store_key as source_store,
                    l.price_toman as buy_price,
                    l.condition,
                    l.url as item_url,
                    l.image_url,
                    l.seller_name,
                    l.location_district,
                    c.digikala_price_toman,
                    c.torob_min_price_toman,
                    COALESCE(NULLIF(c.torob_min_price_toman, 0), c.digikala_price_toman) as ref_price
                FROM store_listings l
                JOIN canonical_products c ON l.canonical_key = c.canonical_key
                WHERE l.store_key IN ('divar', 'esam')
                  AND l.is_verified = 1
                  AND l.price_toman >= 500000
                  AND COALESCE(NULLIF(c.torob_min_price_toman, 0), c.digikala_price_toman) > l.price_toman
                ORDER BY l.price_toman ASC, l.observed_at DESC;
            """)
            deal_candidates = cursor.fetchall()

            arb_inserts = []
            seen_products_per_store = set()

            for d in deal_candidates:
                buy_price = d['buy_price']
                ref_price = d['ref_price']
                spread = ref_price - buy_price
                discount_pct = round((spread / ref_price) * 100.0, 1)

                # Strict Single-Best Deduplication per (canonical_key, source_store)
                product_store_sig = f"{d['canonical_key']}_{d['source_store']}"
                if product_store_sig in seen_products_per_store:
                    continue
                seen_products_per_store.add(product_store_sig)

                # Classify Deal Tier (ignore impossible >65% outliers)
                if discount_pct > 65.0:
                    continue
                elif discount_pct >= 30.0:
                    deal_type = 'GOLDEN_FLIP'
                elif discount_pct >= 20.0:
                    deal_type = 'SUPER_DEAL'
                elif discount_pct >= 10.0:
                    deal_type = 'UNDERVALUED'
                else:
                    continue

                seller_info = d['seller_name'] or d['location_district'] or 'فروشنده'
                target_store = 'torob' if d['torob_min_price_toman'] > 0 else 'digikala'

                arb_inserts.append((
                    d['canonical_key'], d['title_fa'], d['source_store'], target_store,
                    buy_price, ref_price, spread, discount_pct, d['condition'],
                    deal_type, d['item_url'], d['image_url'], seller_info
                ))

            if arb_inserts:
                cursor.executemany("""
                    INSERT INTO arbitrage_opportunities (
                        canonical_key, title_fa, source_store, target_store,
                        buy_price_toman, market_ref_price_toman, profit_spread_toman,
                        discount_percent, condition, deal_type, item_url, image_url,
                        seller_info, detected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, arb_inserts)

            conn.commit()

        logger.info(f"Arbitrage scan completed: {len(per_key)} products updated, {len(arb_inserts)} distinct verified deals saved.")
        return {
            "products_scanned": len(per_key),
            "opportunities_found": len(arb_inserts)
        }

arbitrage_engine = ArbitrageOpportunityEngine()
