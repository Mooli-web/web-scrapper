"""
AI Relay — Groq API forwarder for the local hub (بایپس تحریم/بلاک منطقه‌ای).

چرا این ماژول؟ هاب لوکال (روی کامپیوتر شخصی در ایران) گاهی نمی‌تواند مستقیم به
api.groq.com وصل شود (403/Connection Reset). این endpoint روی Render (IP خارجی
تمیز) اجرا می‌شود و درخواست‌ها را همان‌جا به Groq می‌فرستد.

تنظیم هاب (فایل .env هاب، نه اینجا):
    GROQ_BASE_URL=https://<آدرس-این-سرویس>.onrender.com/ai-relay/v1
    GROQ_API_KEY=gsk_...        # کلید از هاب عبور می‌کند، اینجا ذخیره نمی‌شود

نکته امنیتی: این رله کلید Groq را ذخیره نمی‌کند؛ فقط درخواست‌هایی را قبول
می‌کند که هدر Authorization معتبر (شروع‌شونده با gsk_) داشته باشند — کلیدهای
نامعتبر را خودِ Groq رد می‌کند.
"""

import time
import logging

import requests
from fastapi import APIRouter, Request, Response, HTTPException

logger = logging.getLogger("server.ai_relay")

router = APIRouter(prefix="/ai-relay")

# NOTE: بدون /v1 — چون مسیر ورودی خودش /v1/... دارد و مستقیم به این پایه می‌چسبد
GROQ_BASE = "https://api.groq.com/openai"
UPSTREAM_TIMEOUT = 90  # با احتساب cold-start رایگان Render و دسته‌های بزرگ

# فقط این هدرها به Groq پاس داده می‌شوند
FORWARDED_HEADERS = {"authorization", "content-type", "accept", "user-agent"}


@router.api_route("/v1/models", methods=["GET"])
@router.api_route("/v1/chat/completions", methods=["POST"])
async def relay_to_groq(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer gsk_"):
        raise HTTPException(
            status_code=401,
            detail="Missing/invalid Groq key. Expected header: Authorization: Bearer gsk_...",
        )

    # مسیر واقعی بعد از حذف پیشوند /ai-relay  →  /v1/chat/completions یا /v1/models
    path = request.url.path
    if path.startswith("/ai-relay"):
        path = path[len("/ai-relay"):]
    target = f"{GROQ_BASE}{path}"

    body = await request.body()
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() in FORWARDED_HEADERS}

    t0 = time.perf_counter()
    try:
        upstream = requests.request(
            method=request.method,
            url=target,
            headers=fwd_headers,
            data=body,
            timeout=UPSTREAM_TIMEOUT,
        )
    except Exception as e:
        logger.warning(f"AI relay upstream error for {path}: {e}")
        raise HTTPException(status_code=502, detail=f"Relay could not reach Groq: {e}")

    logger.info(
        f"AI relay {request.method} {path} -> {upstream.status_code} "
        f"({round((time.perf_counter() - t0) * 1000)} ms, {len(body)} bytes from hub)"
    )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


@router.get("/v1/health")
async def relay_health():
    """بررسی سلامت رله (بدون تماس با Groq) — از مرورگر هم قابل بازدید است."""
    return {"status": "ok", "service": "groq-relay", "upstream": GROQ_BASE}
