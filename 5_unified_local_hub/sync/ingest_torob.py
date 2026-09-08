import json
import re
import logging
from typing import List, Dict, Any
from core.normalizer import generate_canonical_key, clean_persian_text, extract_storage_and_specs, normalize_brand, PERSIAN_TO_ENGLISH_DIGITS
from database.db_manager import db

logger = logging.getLogger("hub.sync.torob")

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

def ingest_torob_items(items: List[Dict[str, Any]]) -> int:
    """
    Ingests Torob market floor items with multi-shop competitor data.
    """
    if not items:
        return 0

    canonical_dict = {}
    listings = []
    history = []
    canonical_updates = []
    processed_ids = set()

    for it in items:
        try:
            item_id = str(it.get('key') or it.get('random_key') or it.get('product_id') or it.get('id') or '')
            title = it.get('title') or it.get('name1') or it.get('title_fa') or it.get('name') or ''
            if not title:
                continue

            price = parse_price(it.get('price') or it.get('selling_price_toman') or it.get('selling_price') or it.get('price_text'))
            if price <= 0:
                continue

            if not item_id:
                # FIX: hash() is process-randomized -> unstable item_id across runs.
                import hashlib
                item_id = f"torob_{hashlib.md5(title.strip().lower().encode('utf-8')).hexdigest()[:10]}"

            if item_id in processed_ids:
                continue

            clean_title = clean_persian_text(title)
            category = it.get('category_key', 'digital')
            brand = it.get('brand', '')
            
            raw_shops = it.get('num_shops') or it.get('shops_count') or it.get('shops') or 1
            try:
                shops_count = int(raw_shops)
            except Exception:
                shops_count = 1

            url = it.get('url') or it.get('more_info_url') or (f"https://torob.com{it.get('web_client_absolute_url')}" if it.get('web_client_absolute_url') else "https://torob.com")
            img = it.get('image_url') or it.get('image') or ''

            c_key, detected_brand, _ = generate_canonical_key(clean_title, category)
            final_brand = normalize_brand(brand, detected_brand)  # FIX: Persian brands ('سامسونگ') now map to standard keys

            specs = extract_storage_and_specs(clean_title)
            specs_str = json.dumps(specs, ensure_ascii=False)

            if c_key not in canonical_dict:
                canonical_dict[c_key] = (c_key, clean_title, final_brand, category, specs_str)

            listings.append((
                c_key, 'torob', item_id, clean_title, price,
                'نو (کف بازار آزاد)', 0, 0, f"{shops_count} فروشگاه اینترنتی", 'رقابت سراسری', 'گارانتی اصالت فروشگاه‌ها',
                'ایران', f"کف قیمت رقابتی بین {shops_count} فروشگاه اینترنتی در ترب", specs_str, 4.8, shops_count, url, img, 0
            ))

            history.append((c_key, 'torob', price, 'نو'))
            canonical_updates.append((shops_count, c_key))
            processed_ids.add(item_id)
        except Exception as e:
            logger.debug(f"Torob item parse note: {e}")

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
                    seller_name = excluded.seller_name,
                    observed_at = CURRENT_TIMESTAMP;
            """, listings)

        if history:
            cursor.executemany("""
                INSERT INTO price_history (canonical_key, store_key, price_toman, condition)
                VALUES (?, ?, ?, ?);
            """, history)

        if canonical_updates:
            cursor.executemany("""
                UPDATE canonical_products SET
                    torob_shops_count = ?
                WHERE canonical_key = ?;
            """, canonical_updates)

        conn.commit()

    logger.info(f"✅ [ترب] ثبت دسته‌ای {len(listings)} کالا با اطلاعات تکمیلی انجام شد.")
    return len(listings)
