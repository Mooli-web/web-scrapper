import json
import re
import logging
from typing import List, Dict, Any
from core.normalizer import generate_canonical_key, clean_persian_text, extract_storage_and_specs, normalize_brand, PERSIAN_TO_ENGLISH_DIGITS
from database.db_manager import db

logger = logging.getLogger("hub.sync.esam")

def parse_price(val: Any) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    if not val:
        return 0
    t = str(val)
    for p, e in PERSIAN_TO_ENGLISH_DIGITS.items():
        t = t.replace(p, e)
    digits = re.findall(r'\d+', t.replace(',', '').replace('،', '').replace('٬', ''))
    return int(''.join(digits)) if digits else 0

def ingest_esam_items(items: List[Dict[str, Any]]) -> int:
    """
    Ingests Esam listings with seller rating, return warranty, and auction timers.
    """
    if not items:
        return 0

    canonical_dict = {}
    listings = []
    history = []
    processed_ids = set()

    for it in items:
        try:
            item_id = str(it.get('item_id') or it.get('id') or '')
            title = it.get('title_fa') or it.get('title') or ''
            if not item_id or not title or item_id in processed_ids:
                continue

            price = parse_price(it.get('selling_price_toman') or it.get('price') or it.get('selling_price'))
            if price <= 0:
                continue

            clean_title = clean_persian_text(title)
            category = it.get('category_key', 'digital')
            brand = it.get('brand', '')
            condition = it.get('condition') or 'دست دوم'
            is_auction = 1 if it.get('is_auction') else 0
            bids_count = int(it.get('bids_count') or 0)
            seller = it.get('seller_name') or 'فروشنده معتبر ایسام'
            score = it.get('seller_score') or '۱۰۰٪ رضایت'
            city = it.get('seller_city') or 'ایران'
            desc = str(it.get('description') or it.get('time_remaining') or '')
            url = it.get('url') or f"https://esam.ir"
            img = it.get('image_url') or ''

            c_key, detected_brand, _ = generate_canonical_key(clean_title, category)
            final_brand = normalize_brand(brand, detected_brand)  # FIX: Persian brands ('سامسونگ') now map to standard keys

            specs = extract_storage_and_specs(clean_title)
            specs_str = json.dumps(specs, ensure_ascii=False)

            if c_key not in canonical_dict:
                canonical_dict[c_key] = (c_key, clean_title, final_brand, category, specs_str)

            listings.append((
                c_key, 'esam', item_id, clean_title, price,
                condition, is_auction, bids_count, seller, score, 'ضمانت بازگشت وجه ایسام',
                city, desc, specs_str, 5.0 if '100' in score else 4.5, bids_count, url, img, 0
            ))

            history.append((c_key, 'esam', price, condition))
            processed_ids.add(item_id)
        except Exception as e:
            logger.debug(f"Esam item parse note: {e}")

    with db.get_connection() as conn:
        cursor = conn.cursor()

        if canonical_dict:
            cursor.executemany("""
                INSERT INTO canonical_products (canonical_key, title_fa, brand, category_key, specs_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(canonical_key) DO UPDATE SET last_synced_at = CURRENT_TIMESTAMP;
            """, list(canonical_dict.values()))

        if listings:
            cursor.executemany("""
                INSERT INTO store_listings (
                    canonical_key, store_key, item_id, title_fa, price_toman,
                    condition, is_auction, bids_count, seller_name, seller_score, warranty,
                    location_district, description, specs_json, rating_score, reviews_count, url, image_url, rrp_price_toman
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(store_key, item_id) DO UPDATE SET
                    price_toman = excluded.price_toman,
                    condition = excluded.condition,
                    is_auction = excluded.is_auction,
                    bids_count = excluded.bids_count,
                    observed_at = CURRENT_TIMESTAMP;
            """, listings)

        if history:
            cursor.executemany("""
                INSERT INTO price_history (canonical_key, store_key, price_toman, condition)
                VALUES (?, ?, ?, ?);
            """, history)

        conn.commit()

    logger.info(f"✅ [ایسام] ثبت دسته‌ای {len(listings)} کالا با اطلاعات تکمیلی انجام شد.")
    return len(listings)
