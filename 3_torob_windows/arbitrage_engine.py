from typing import Dict, Any, List

def compute_arbitrage(digi_product: Dict[str, Any], torob_match: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates exact price arbitrage between Digikala and Torob.
    """
    digi_price = int(digi_product.get("selling_price_toman", 0) or 0)
    torob_price = int(torob_match.get("torob_price_toman", 0) or 0)

    if digi_price <= 0 or torob_price <= 0:
        return {}

    diff_toman = digi_price - torob_price
    diff_percent = round((abs(diff_toman) / min(digi_price, torob_price)) * 100.0, 1)

    if diff_toman < -50000:
        # Digikala is significantly cheaper than Torob free market
        arbitrage_type = "DIGIKALA_CHEAPER"
        verdict = "فرصت طلایی خرید از دیجی‌کالا"
        cheaper_store = "دیجی‌کالا"
        profit_toman = abs(diff_toman)
    elif diff_toman > 50000:
        # Free market (Torob) is cheaper than Digikala
        arbitrage_type = "TOROB_CHEAPER"
        verdict = "بازار آزاد ارزان‌تر است"
        cheaper_store = "ترب (بازار آزاد)"
        profit_toman = diff_toman
    else:
        arbitrage_type = "EQUAL"
        verdict = "قیمت هم‌تراز با بازار"
        cheaper_store = "هر دو یکسان"
        profit_toman = 0

    return {
        "product_id": digi_product.get("product_id"),
        "title_fa": digi_product.get("title_fa"),
        "brand": digi_product.get("brand"),
        "category_name": digi_product.get("category_name"),
        "image_url": digi_product.get("image_url"),
        "digi_price": digi_price,
        "digi_seller": digi_product.get("seller_name", "دیجی‌کالا"),
        "digi_url": digi_product.get("product_url") or f"https://www.digikala.com/product/dkp-{digi_product.get('product_id')}/",
        "torob_title": torob_match.get("torob_title"),
        "torob_price": torob_price,
        "torob_num_shops": torob_match.get("num_shops", 1),
        "torob_url": torob_match.get("torob_url"),
        "match_score": torob_match.get("match_score"),
        "diff_toman": diff_toman,
        "diff_percent": diff_percent,
        "arbitrage_type": arbitrage_type,
        "verdict": verdict,
        "cheaper_store": cheaper_store,
        "profit_toman": profit_toman
    }
