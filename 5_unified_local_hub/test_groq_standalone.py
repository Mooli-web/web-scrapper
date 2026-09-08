import os
import sys
import time
import json
import requests
from pathlib import Path

env_file = Path(".env")
if not env_file.exists():
    env_file = Path(__file__).resolve().parent / ".env"

if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_file, override=True)
    except ImportError:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k.strip()] = v.strip()

def extract_message_text(choice_dict):
    msg = choice_dict.get("message", {})
    text = msg.get("content") or msg.get("reasoning_content") or ""
    if not text and isinstance(msg, dict):
        text = json.dumps(msg, ensure_ascii=False)
    return str(text).strip()

def main():
    print("=" * 65)
    print("  🧪 اسکریپت تست اختصاصی و مستقل اتصال به هوش مصنوعی Groq API")
    print("=" * 65)
    print()

    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        print("⚠️ کلید GROQ_API_KEY در فایل .env یافت نشد!")
        print("لطفاً کلید خود را که با gsk_ شروع می‌شود وارد کرده و Enter بزنید:")
        api_key = input("کلید Groq API Key: ").strip()

    if not api_key.startswith("gsk_"):
        print("❌ فرمت کلید نامعتبر است! کلید رسمی Groq باید با gsk_ شروع شود.")
        return

    print(f"🔑 کلید شناسایی شد: {api_key[:8]}...{api_key[-4:]}")
    print()

    # Step 1: Query Available Models from Groq
    print("[1/2] در حال دریافت لیست مدل‌های فعال از سرورهای Groq...")
    models_url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    active_models = []
    try:
        t0 = time.time()
        resp = requests.get(models_url, headers=headers, timeout=12)
        elapsed = round((time.time() - t0) * 1000, 1)

        if resp.status_code == 200:
            data = resp.json()
            for m in data.get("data", []):
                m_id = m.get("id", "")
                if not any(x in m_id.lower() for x in ["whisper", "guard", "vision"]):
                    active_models.append(m_id)

            print(f"✅ اتصال به سرور برقرار است! (تاخیر: {elapsed} ms)")
            print(f"📋 لیست تمام مدل‌های چت فعال روی اکانت شما:")
            for m in active_models:
                print(f"   • {m}")
        elif resp.status_code == 401:
            print("❌ خطای احراز هویت (401 Unauthorized): کلید واردشده نامعتبر یا منقضی است.")
            print("پاسخ سرور:", resp.text)
            return
        else:
            print(f"⚠️ سرور کد {resp.status_code} بازگرداند: {resp.text}")
            return
    except Exception as e:
        print(f"❌ خطای ارتباط شبکه: {e}")
        return

    print()
    print("-" * 65)

    # Step 2: Auto-Pick Best Active Chat Model
    preferred_order = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "groq/compound"]
    chosen_model = None
    for pref in preferred_order:
        if pref in active_models:
            chosen_model = pref
            break
    if not chosen_model and active_models:
        chosen_model = active_models[0]

    print(f"[2/2] ارسال پرامپت تستی به مدل انتخابی: {chosen_model} ...")
    chat_url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": "You are a fast market intelligence AI. Answer concisely in Persian."},
            {"role": "user", "content": "سلام! وضعیت اتصال به هوش مصنوعی Groq چگونه است و سرعت چقدر است؟"}
        ],
        "max_tokens": 150,
        "temperature": 0.2
    }

    try:
        t0 = time.time()
        resp = requests.post(chat_url, headers=headers, json=payload, timeout=15)
        elapsed_sec = round(time.time() - t0, 3)

        if resp.status_code == 200:
            data = resp.json()
            reply = extract_message_text(data["choices"][0])
            usage = data.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            comp_tokens = usage.get("completion_tokens", 0)
            speed = round(comp_tokens / max(elapsed_sec, 0.05), 1)

            print("🎉 تست با موفقیت ۱۰۰٪ انجام شد!")
            print(f"💬 پاسخ هوش مصنوعی ({chosen_model}):\n{reply.strip()}\n")
            print("📊 آمار عملکرد و مصرف توکن:")
            print(f"   • مدل استفاده‌شده: {chosen_model}")
            print(f"   • زمان پاسخ‌دهی کل: {elapsed_sec} ثانیه ({int(elapsed_sec * 1000)} ms)")
            print(f"   • سرعت تولید: {speed} توکن بر ثانیه")
            print(f"   • کل توکن‌های مصرف‌شده در این تست: {total_tokens} توکن")
            print(f"   • هزینه برای شما: صفر تومان (سهمیه ۱۰۰٪ رایگان)")
        else:
            print(f"❌ خطا در پردازش چت (کد {resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"❌ خطا در ارسال درخواست: {e}")

    print("=" * 65)

if __name__ == "__main__":
    main()
