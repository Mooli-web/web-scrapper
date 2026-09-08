import re
import math
import json
import logging
import requests
from typing import Dict, Any, List, Tuple, Optional
from database.db_manager import db
from core.normalizer import clean_persian_text

logger = logging.getLogger("hub.ai_classifier")

# Semantic Anchor Concepts for Vector-like Cosine Scoring
ACCESSORY_ANCHORS = [
    "قاب", "گلس", "کاور", "بند", "کارتن", "جعبه", "پوکه", "کابل", "شارژر",
    "محافظ", "استند", "پایه", "اسکین", "استیکر", "کیف", "دسته", "بازی", "اکانت"
]

DEVICE_ANCHORS = [
    "گوشی", "موبایل", "لپتاپ", "لپ تاپ", "نوت بوک", "مک بوک", "کنسول", "پلی استیشن",
    "ایکس باکس", "گرافیک", "کارت گرافیک", "پردازنده", "سی پی یو", "مانیتور", "تبلت"
]

def text_to_vector(text: str, vocab: List[str]) -> List[float]:
    t = text.lower()
    return [1.0 if word in t else 0.0 for word in vocab]

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)

class LocalSemanticAIClassifier:
    """
    Local AI Semantic Classifier & Ollama Bridge.
    Runs fast on-device semantic classification and connects to local Ollama if active.
    """
    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.ollama_host = ollama_host
        self.vocab = list(set(ACCESSORY_ANCHORS + DEVICE_ANCHORS))

    def check_ollama_status(self) -> Dict[str, Any]:
        """Probes local Ollama instance on port 11434."""
        try:
            resp = requests.get(f"{self.ollama_host}/api/tags", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "connected": True,
                    "host": self.ollama_host,
                    "available_models": models,
                    "active_model": models[0] if models else "None"
                }
        except Exception:
            pass
        return {
            "connected": False,
            "host": self.ollama_host,
            "error": "Ollama در پورت ۱۱۴۳۴ در حال اجرا نیست (از مدل سبک پایتون استفاده می‌شود)"
        }

    def classify_with_local_vectors(self, title: str, price: int, category: str) -> Dict[str, Any]:
        """
        Fast on-device mathematical & vector semantic scoring.
        """
        clean_t = clean_persian_text(title)
        v_title = text_to_vector(clean_t, self.vocab)
        v_acc = text_to_vector(" ".join(ACCESSORY_ANCHORS), self.vocab)
        v_dev = text_to_vector(" ".join(DEVICE_ANCHORS), self.vocab)

        sim_acc = cosine_similarity(v_title, v_acc)
        sim_dev = cosine_similarity(v_title, v_dev)

        # Price-to-Text discrepancy heuristic
        is_accessory = sim_acc > sim_dev or (sim_acc > 0.35 and price < 3_000_000)
        confidence = round(max(sim_acc, sim_dev, 0.75) * 100.0, 1)

        return {
            "engine": "local_vector_ai",
            "is_real_device": not is_accessory,
            "semantic_label": "ACCESSORY_OR_PART" if is_accessory else "REAL_DEVICE",
            "accessory_similarity": round(sim_acc, 3),
            "device_similarity": round(sim_dev, 3),
            "confidence_score": confidence,
            "reason": "تشخیص شباهت برداری با مفاهیم لوازم جانبی/قاب/جعبه" if is_accessory else "انطباق معنایی با کالای اصلی"
        }

    def classify_with_ollama(self, title: str, price: int, model: str = "llama3") -> Optional[Dict[str, Any]]:
        """
        Sends deep reasoning prompt to local Ollama LLM if available.
        """
        prompt = f"""You are a data validation AI for an Iranian electronics marketplace.
Analyze this listing title and price to determine if it is a REAL WHOLE DEVICE (laptop, phone, console, GPU) or just an ACCESSORY, EMPTY BOX, SPARE PART, or BROKEN ITEM.
Title: "{title}"
Price: {price:,} Toman

Return ONLY a valid JSON object with format:
{{"is_real_device": true/false, "category": "phone/laptop/console/gpu/accessory/junk", "reason_fa": "توضیح کوتاه فارسی", "confidence": 0.95}}"""

        try:
            resp = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_out = data.get("response", "")
                parsed = json.loads(raw_out)
                return {
                    "engine": f"ollama_{model}",
                    "is_real_device": parsed.get("is_real_device", True),
                    "category": parsed.get("category", "unknown"),
                    "confidence_score": round(float(parsed.get("confidence", 0.9)) * 100.0, 1),
                    "reason": parsed.get("reason_fa", "")
                }
        except Exception as e:
            logger.debug(f"Ollama generation note: {e}")
        return None

    def get_stratified_samples(self, per_category: int = 25) -> Dict[str, Any]:
        """
        Stratified Random Sampling (100 sample audit across Mobiles, Laptops, Consoles, Hardware).
        """
        categories = [
            {"key": "mobile", "name": "گوشی‌های موبایل (اپل، سامسونگ، شیائومی)"},
            {"key": "laptop", "name": "لپ‌تاپ‌ها (مک‌بوک، ایسوس، لنوو)"},
            {"key": "console", "name": "کنسول‌های بازی (PS5، PS4، Xbox)"},
            {"key": "gpu", "name": "قطعات سخت‌افزار و کارت گرافیک"}
        ]

        samples_by_cat = {}
        total_samples = 0
        verified_count = 0

        with db.get_connection() as conn:
            cursor = conn.cursor()

            for cat in categories:
                cat_key = cat["key"]
                cursor.execute("""
                    SELECT
                        l.id, l.canonical_key, l.store_key, l.item_id, l.title_fa,
                        l.price_toman, l.condition, l.is_verified, l.quality_status, l.confidence_score,
                        c.brand, c.category_key,
                        COALESCE(NULLIF(c.torob_min_price_toman, 0), c.digikala_price_toman, 0) as market_ref_price
                    FROM store_listings l
                    JOIN canonical_products c ON l.canonical_key = c.canonical_key
                    WHERE c.category_key LIKE ? OR l.canonical_key LIKE ?
                    ORDER BY RANDOM()
                    LIMIT ?;
                """, (f"%{cat_key}%", f"%{cat_key}%", per_category))
                
                rows = cursor.fetchall()
                sample_items = [dict(r) for r in rows]
                samples_by_cat[cat_key] = {
                    "category_name": cat["name"],
                    "items": sample_items,
                    "count": len(sample_items)
                }
                total_samples += len(sample_items)
                verified_count += sum(1 for s in sample_items if s.get("is_verified") == 1)

        accuracy_rate = round((verified_count / total_samples) * 100.0, 1) if total_samples > 0 else 100.0

        return {
            "total_sampled": total_samples,
            "verified_in_sample": verified_count,
            "sample_accuracy_rate": accuracy_rate,
            "categories": samples_by_cat
        }

local_ai = LocalSemanticAIClassifier()
