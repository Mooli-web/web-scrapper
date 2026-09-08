import os
import re
import time
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(".env")
    if not env_file.exists():
        env_file = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_file)
except ImportError:
    pass

logger = logging.getLogger("hub.ai.groq")

DEFAULT_GROQ_BASE = "https://api.groq.com/openai/v1"

def _api_base() -> str:
    """
    NEW: the API base URL is now configurable via GROQ_BASE_URL in .env.
    - Default: direct Groq API.
    - If Groq blocks your region (HTTP 403 Forbidden), point this to any
      OpenAI-compatible relay (e.g. a tiny proxy deployed on your Render
      services in the US/EU) and everything works without code changes:
        GROQ_BASE_URL=https://your-relay.onrender.com/v1
    """
    return (os.getenv("GROQ_BASE_URL") or DEFAULT_GROQ_BASE).strip().rstrip("/")

def _completions_url() -> str:
    return f"{_api_base()}/chat/completions"

def _models_url() -> str:
    return f"{_api_base()}/models"

def extract_message_text(choice_dict: Dict[str, Any]) -> str:
    msg = choice_dict.get("message", {})
    text = msg.get("content") or msg.get("reasoning_content") or ""
    if not text and isinstance(msg, dict):
        text = json.dumps(msg, ensure_ascii=False)
    return str(text).strip()

def parse_json_from_ai_response(raw_text: str) -> Dict[str, Any]:
    if not raw_text:
        return {}
    try:
        return json.loads(raw_text)
    except Exception:
        pass
    
    json_match = re.search(r'(\{[\s\S]*\})', raw_text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except Exception:
            pass
            
    return {}

class GroqAIClient:
    """
    High-Speed Groq Cloud AI Engine with Support for Reasoning & Standard LLMs.
    """
    def __init__(self):
        self.reload_api_key()
        self.total_tokens_consumed = 0
        self.total_api_calls = 0
        self.last_http_status = 0  # NEW: برای تشخیص 429 در لایه بازبینی
        self.active_model = "openai/gpt-oss-20b"

    def reload_api_key(self):
        try:
            from dotenv import load_dotenv
            env_f = Path(".env")
            if not env_f.exists():
                env_f = Path(__file__).resolve().parent.parent / ".env"
            load_dotenv(dotenv_path=env_f, override=True)
        except Exception:
            pass

        # NEW: پشتیبانی از چند کلید Groq برای ضرب‌شدن سهمیه‌ی نرخ (TPM).
        # ترتیب خواندن: GROQ_API_KEY + GROQ_API_KEYS (جدا با کاما) + GROQ_API_KEY_2 تا GROQ_API_KEY_10
        candidates = [os.getenv("GROQ_API_KEY", "")]
        candidates += [os.getenv("GROQ_API_KEYS", "")]
        candidates += [os.getenv(f"GROQ_API_KEY_{i}", "") for i in range(2, 11)]
        keys: List[str] = []
        for c in candidates:
            for k in re.split(r"[,\s]+", str(c).strip()):
                k = k.strip()
                if k.startswith("gsk_") and k not in keys:
                    keys.append(k)
        self.api_keys = keys
        if not hasattr(self, "_key_index") or self._key_index >= len(keys):
            self._key_index = 0
        # کلید فعال (برای سازگاری با متدهای قدیمی که self.api_key می‌خوانند)
        self.api_key = keys[self._key_index] if keys else ""
        self.active_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()

    def _rotate_to_next_key(self):
        """NEW: بعد از 429 به کلید بعدی می‌رود؛ سهمیه‌ی هر کلید مستقل است."""
        if len(self.api_keys) > 1:
            self._key_index = (self._key_index + 1) % len(self.api_keys)
            self.api_key = self.api_keys[self._key_index]
            logger.info(f"Groq key rotated → key #{self._key_index + 1}/{len(self.api_keys)}")

    def masked_active_key(self) -> str:
        """NEW: کلید فعال به‌صورت ماسک‌شده برای نمایش در آمار."""
        k = self.api_key
        return f"{k[:9]}...{k[-4:]}" if len(k) > 16 else (k or "—")

    def is_configured(self) -> bool:
        self.reload_api_key()
        return len(self.api_keys) > 0

    def chat_json(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> Optional[Dict[str, Any]]:
        """
        NEW: generic JSON-mode chat call used by the AI review layer (ai_reviewer).
        Returns a parsed dict, or None on any failure (caller decides to skip/retry).
        """
        if not self.is_configured():
            return None

        payload = {
            "model": self.active_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1
        }
        # NEW: مدل‌های استدلالی (gpt-oss) توکن را صرف «فکر کردن» می‌کنند و
        # ممکن است content خالی برگردانند — استدلال کم برای بازبینی داده کافی است.
        if "gpt-oss" in self.active_model:
            payload["reasoning_effort"] = "low"

        try:
            # NEW: چرخش بین کلیدها — اگر کلیدی 429 (پر شدن سهمیه) داد، همان
            # درخواست بی‌درنگ با کلید بعدی تکرار می‌شود؛ فقط وقتی «همه» کلیدها
            # 429 بدهند None برمی‌گردد تا لایه‌ی بازبینی ۳۰ ثانیه صبر کند.
            for _attempt in range(max(1, len(self.api_keys))):
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                # NOTE: timeout بالا به‌خاطر cold-start رله رایگان Render است
                resp = requests.post(_completions_url(), headers=headers, json=payload, timeout=120)
                self.last_http_status = resp.status_code  # NEW: برای تشخیص 429
                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {})
                    self.total_tokens_consumed += usage.get("total_tokens", 0)
                    self.total_api_calls += 1
                    text = extract_message_text(data["choices"][0])
                    return parse_json_from_ai_response(text)
                if resp.status_code == 429 and len(self.api_keys) > 1:
                    self._rotate_to_next_key()
                    continue
                logger.warning(f"Groq chat_json HTTP {resp.status_code}: {resp.text[:200]}")
                return None
            logger.warning(f"Groq: all {len(self.api_keys)} keys hit rate limit (429).")
            return None
        except Exception as e:
            logger.warning(f"Groq chat_json note: {e}")
        return None

    def get_available_chat_models(self, key_override: Optional[str] = None) -> List[str]:
        key = (key_override or self.api_key).strip()
        if not key or not key.startswith("gsk_"):
            return []

        headers = {"Authorization": f"Bearer {key}"}
        try:
            resp = requests.get(_models_url(), headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for m in data.get("data", []):
                    m_id = m.get("id", "")
                    if not any(x in m_id.lower() for x in ["whisper", "guard", "vision"]):
                        models.append(m_id)
                return models
        except Exception:
            pass
        return []

    def test_connection(self, key_override: Optional[str] = None) -> Dict[str, Any]:
        key = (key_override or self.api_key).strip()
        if not key or not key.startswith("gsk_"):
            return {
                "success": False,
                "error": "کلید وارد نشده است یا با gsk_ شروع نمی‌شود."
            }

        available = self.get_available_chat_models(key)
        preferred_order = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "groq/compound"]
        target_model = None
        for pref in preferred_order:
            if pref in available:
                target_model = pref
                break
        if not target_model and available:
            target_model = available[0]
        if not target_model:
            target_model = self.active_model or "openai/gpt-oss-20b"

        t0 = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": "You are a fast market intelligence AI."},
                {"role": "user", "content": "پاسخ کوتاه ۵ کلمه‌ای بده: وضعیت اتصال به هوش مصنوعی Groq چگونه است؟"}
            ],
            "max_tokens": 200
        }

        try:
            resp = requests.post(_completions_url(), headers=headers, json=payload, timeout=12)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                content = extract_message_text(data["choices"][0])
                self.active_model = target_model
                
                return {
                    "success": True,
                    "model": target_model,
                    "available_models": available,
                    "latency_ms": elapsed_ms,
                    "response_sample": content or "اتصال به Groq کاملاً برقرار و آماده است.",
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "tokens_per_second": round((usage.get("completion_tokens", 20) / max(elapsed_ms / 1000, 0.05)), 1)
                }
            else:
                return {
                    "success": False,
                    "http_code": resp.status_code,
                    "error": resp.text[:250],
                    "available_models": available
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"خطای اتصال به سرور Groq: {e}"
            }

    def classify_ambiguous_listing(self, title: str, price: int, category: str) -> Dict[str, Any]:
        self.reload_api_key()
        if not self.is_configured():
            return {"success": False, "error": "Groq API key not configured"}

        prompt = f"""You are a data validation AI for Iranian marketplace listings.
Evaluate this listing title and price. Determine if this is a GENUINE DEVICE or just an ACCESSORY/BOX/BROKEN PART:
Title: "{title}"
Price: {price:,} Toman
Category: {category}

Respond ONLY in valid JSON format:
{{"is_real_device": true, "category": "device_type", "confidence_percent": 95, "reason_fa": "دلیل کوتاه فارسی"}}"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.active_model or "openai/gpt-oss-20b",
            "messages": [
                {"role": "system", "content": "You output strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 400
        }

        t0 = time.perf_counter()
        try:
            resp = requests.post(_completions_url(), headers=headers, json=payload, timeout=12)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                usage = data.get("usage", {})
                tokens_used = usage.get("total_tokens", 80)
                self.total_tokens_consumed += tokens_used
                self.total_api_calls += 1

                raw_text = extract_message_text(data["choices"][0])
                parsed = parse_json_from_ai_response(raw_text)

                return {
                    "success": True,
                    "engine": f"groq_{self.active_model}",
                    "is_real_device": parsed.get("is_real_device", True),
                    "confidence_score": float(parsed.get("confidence_percent", 90)),
                    "reason": parsed.get("reason_fa", "تایید توسط هوش مصنوعی Groq"),
                    "tokens_used": tokens_used,
                    "elapsed_ms": elapsed_ms
                }
            else:
                logger.warning(f"Groq classification returned HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"Groq classification error: {e}")

        return {"success": False, "error": "Groq request failed"}

    def expand_search_taxonomy(self, category_name: str) -> List[str]:
        self.reload_api_key()
        if not self.is_configured():
            return []

        prompt = f"""برای دسته‌بندی «{category_name}» در بازار دیجیتال ایران (دیوار، ترب، ایسام و دیجی‌کالا)، ۵۰ کلیدواژه و اصطلاح عامیانه تولید کن.
پاسخ در قالب JSON: {{"keywords": ["کلمه ۱", "کلمه ۲"]}}"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.active_model or "openai/gpt-oss-20b",
            "messages": [
                {"role": "system", "content": "You output strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 700
        }

        try:
            resp = requests.post(_completions_url(), headers=headers, json=payload, timeout=18)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = extract_message_text(data["choices"][0])
                parsed = parse_json_from_ai_response(raw_text)
                return parsed.get("keywords", [])
        except Exception as e:
            logger.error(f"Groq taxonomy expansion error: {e}")
        return []

groq_client = GroqAIClient()
