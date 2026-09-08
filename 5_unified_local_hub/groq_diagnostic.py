# -*- coding: utf-8 -*-
"""
🩺 تشخیص مستقل مشکل اتصال به Groq — groq_diagnostic.py
========================================================
این فایل هیچ ربطی به هاب ندارد؛ مستقل اجرا می‌شود و مرحله‌به‌مرحله می‌گوید
مشکل اتصال به api.groq.com دقیقاً کجاست: IP؟ کلید؟ DNS؟ اثر انگشت TLS؟

اجرا (داخل پوشه 5_unified_local_hub):

    python groq_diagnostic.py
    python groq_diagnostic.py --socks 127.0.0.1:1819
    python groq_diagnostic.py --proxy http://127.0.0.1:8080
    python groq_diagnostic.py --relay https://your-service.onrender.com/ai-relay/v1
    python groq_diagnostic.py --key gsk_xxx --socks 127.0.0.1:1819 --relay https://...

کلید به‌ترتیب از: پارامتر --key → فایل .env (GROQ_API_KEY) خوانده می‌شود.

⚠️ مهم — دو سناریو را جدا تست کن:
  A) وقتی Proxifier روشن است و قانون python.exe فعال
  B) وقتی Proxifier روی Pause است (Profile → Pause Proxification) و فقط Windscribe روشن است
خروجی IP هر سناریو را مقایسه کن — این‌طوری معلوم می‌شود ترافیک پایتون واقعاً از کجا خارج می‌شود.
"""

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ پکیج requests نصب نیست:  pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------- تنظیمات
HUB_ENV = Path(__file__).resolve().parent / ".env"
DEFAULT_BASE = "https://api.groq.com/openai/v1"
BROWSER_LIKE_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
IP_SERVICES = ["https://ipinfo.io/json", "https://api.ipify.org?format=json"]

RESULTS = []  # (نام تست، وضعیت، توضیح)


def load_env_key():
    key = os.getenv("GROQ_API_KEY", "").strip()
    if key:
        return key
    if HUB_ENV.exists():
        for line in HUB_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def record(name, ok, detail):
    mark = "PASS ✅" if ok is True else ("FAIL ❌" if ok is False else "SKIP ⏭️")
    RESULTS.append((name, mark, detail))
    print(f"  [{mark}] {name}: {detail}")


def make_session(proxy=None, socks=None, trust_env=False, browser_ua=True):
    s = requests.Session()
    s.trust_env = trust_env  # False → متغیرهای محیطی HTTPS_PROXY نادیده گرفته شوند
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    if socks:
        s.proxies = {"http": f"socks5h://{socks}", "https": f"socks5h://{socks}"}
    if browser_ua:
        s.headers["User-Agent"] = BROWSER_LIKE_UA
    return s


def my_exit_ip(sess, label):
    """IP و کشور خروجی همین Session را نشان می‌دهد."""
    for url in IP_SERVICES:
        try:
            r = sess.get(url, timeout=10)
            if r.status_code == 200:
                d = r.json()
                ip = d.get("ip") or d.get("query") or "?"
                country = d.get("country") or d.get("countryCode") or "?"
                city = d.get("city") or ""
                return f"{ip} ({country} {city})"
        except Exception as e:
            continue
    return f"نامشخص (خطا در سرویس IP: {label})"


def test_route(label, sess, base, key, do_chat=True):
    """یک مسیر کامل را تست می‌کند: IP → models → chat"""
    print(f"\n———— مسیر: {label} ————")
    ip = my_exit_ip(sess, label)
    print(f"  🌍 IP خروجی این مسیر: {ip}")
    is_ir = "(IR" in ip or " Iran" in ip
    record(f"IP خروجی [{label}]", None if "نامشخص" in ip else (not is_ir),
           ip + ("  ⚠️ ایران! ترافیک از پروکسی رد نمی‌شود" if is_ir else ""))

    headers = {"Authorization": f"Bearer {key}"} if key else {}
    if not key:
        record(f"کلید [{label}]", False, "GROQ_API_KEY پیدا نشد (.env یا --key)")
        return

    # مرحله models
    models_ok = False
    try:
        t0 = time.perf_counter()
        r = sess.get(f"{base}/models", headers=headers, timeout=20)
        ms = round((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            try:
                n = len(r.json().get("data", []))
                record(f"GET /models [{label}]", True, f"{n} مدل در دسترس ({ms}ms) — کلید و IP سالم!")
                models_ok = True
            except ValueError:
                snippet = r.text[:70].replace("\n", " ")
                record(f"GET /models [{label}]", False,
                       "پاسخ 200 اما HTML/غیرJSON ⇒ کد رله روی سرور نیست! "
                       "(فایل‌ها push نشده یا دیپلوی Render تمام نشده) — پاسخ سرور: " + snippet)
        elif r.status_code == 401:
            record(f"GET /models [{label}]", False, "401 → کلید نامعتبر/حذف‌شده")
        elif r.status_code == 403:
            record(f"GET /models [{label}]", False,
                   "403 → IP یا اثر انگشت TLS بلاک است (کلید ممکن است سالم باشد)")
        elif r.status_code == 404:
            record(f"GET /models [{label}]", False,
                   "404 → این مسیر روی سرور وجود ندارد؛ رله دیپلوی نشده یا آدرس غلط است")
        else:
            record(f"GET /models [{label}]", False, f"HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        record(f"GET /models [{label}]", False, f"اتصال برقرار نشد: {type(e).__name__}: {e}")
        return

    # مرحله چت
    if do_chat and models_ok:
        try:
            r = sess.post(
                f"{base}/chat/completions",
                headers=headers,
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": "فقط بنویس: سلام"}],
                    "max_tokens": 20,
                },
                timeout=60,
            )
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"].get("content", "")
                record(f"POST /chat [{label}]", True, f"پاسخ دریافت شد: «{str(txt)[:40]}»")
            elif r.status_code == 403:
                record(f"POST /chat [{label}]", False, "403 → این مدل/IP اجازه چت ندارد")
            elif r.status_code == 404:
                record(f"POST /chat [{label}]", False,
                       "404 → مدل پیدا نشد؛ نام مدل را در /models چک کن")
            else:
                record(f"POST /chat [{label}]", False, f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            record(f"POST /chat [{label}]", False, f"{type(e).__name__}: {e}")


def dns_check():
    print("\n———— تست DNS ————")
    try:
        ips = sorted({ai[4][0] for ai in socket.getaddrinfo("api.groq.com", 443)})
        record("DNS api.groq.com", True, f" resolve شد: {', '.join(ips[:3])}")
        bad = [ip for ip in ips if ip.startswith(("10.", "127.", "0.0", "185.201.", "10.10"))]
        if bad:
            record("DNS مشکوک", False, f"IP جعلی/بلاک‌شده احتمالی: {bad} (DNS poisoning?)")
    except Exception as e:
        record("DNS api.groq.com", False, f"{type(e).__name__}: {e}")


def curl_cffi_test(base, key):
    """تست با اثر انگشت TLS کروم — اگر این پاس شد یعنی مشکل TLS fingerprint است."""
    print("\n———— مسیر: مستقیم با اثر انگشت TLS مرورگر (curl_cffi) ————")
    try:
        from curl_cffi import requests as creq
    except ImportError:
        record("curl_cffi", None, "نصب نیست — برای تست:  pip install curl_cffi")
        return
    if not key:
        record("curl_cffi", None, "کلید نداریم")
        return
    try:
        r = creq.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"},
                     impersonate="chrome", timeout=25)
        if r.status_code == 200:
            record("curl_cffi (شبیه کروم)", True,
                   "پاسخ گرفت! ⇒ مشکل «اثر انگشت TLS پایتون» است، نه IP/کلید")
        elif r.status_code == 403:
            record("curl_cffi (شبیه کروم)", False,
                   "باز هم 403 ⇒ احتمالاً IP خروجی بن است، نه TLS")
        else:
            record("curl_cffi (شبیه کروم)", False, f"HTTP {r.status_code}")
    except Exception as e:
        record("curl_cffi (شبیه کروم)", False, f"{type(e).__name__}: {e}")


def summarize():
    print("\n" + "=" * 62)
    print("📊 خلاصه نتایج")
    print("=" * 62)
    for name, mark, detail in RESULTS:
        print(f"  [{mark}] {name}")
    print()
    print("🧭 راهنمای تصمیم (اولین موردی که صدق می‌کند):")
    print("""
  1. «IP خروجی ... (IR)» در مسیری که فکر می‌کردی پروکسی است
     ⇒ ترافیک پایتون اصلاً از پروکسی رد نمی‌شود.
     حل: در Proxifier قانون python.exe را چک کن (یا Windscribe را در حالت
     سیستم/کامل روشن کن و Proxifier را Pause کن) و دوباره تست بگیر.

  2. مستقیم 403 + مرورگر باز می‌کند + curl_cffi پاس شد
     ⇒ Groq پایتون را از «اثر انگشت TLS» تشخیص می‌دهد (نه از IP).
     حل (قطعی): رله Render (ai_relay.py) — درخواست از سرور خارجی می‌رود.
     حل (جایگزین): pip install curl_cffi و استفاده از آن در groq_client.

  3. همه مسیرها 403 + curl_cffi هم 403
     ⇒ IP خروجی (سرور پروکسی/VPN) توسط Groq بن شده است.
     حل: تغییر سرور/لوکیشن VPN، یا کلید جدید با IP تمیز، یا رله Render.

  4. 401 در همه جا
     ⇒ کلید نامعتبر/حذف‌شده است. با IP خارجی وارد console.groq.com شو و
     کلید تازه بساز (Create API Key).

  5. /models پاس شد ولی /chat نه (404)
     ⇒ نام مدل اشتباه است؛ مدل درست را از پاسخ /models بردار و در .env
     بگذار:  GROQ_MODEL=openai/gpt-oss-20b

  6. مسیر رله (relay) PASS شد
     ⇒ راه‌حل آماده است! در .env هاب بگذار:
        GROQ_BASE_URL=<همان آدرس relay>/ai-relay/v1
     و دیگر هیچ VPN/پروکسی لازم نیست.""")


def main():
    ap = argparse.ArgumentParser(description="تشخیص مشکل اتصال Groq")
    ap.add_argument("--key", help="کلید gsk_...")
    ap.add_argument("--base", default=DEFAULT_BASE, help="پایه API (پیش‌فرض Groq مستقیم)")
    ap.add_argument("--proxy", help="پروکسی HTTP، مثل http://127.0.0.1:8080")
    ap.add_argument("--socks", help="پروکسی SOCKS، مثل 127.0.0.1:1819")
    ap.add_argument("--relay", help="آدرس رله Render، مثل https://x.onrender.com/ai-relay/v1")
    ap.add_argument("--no-chat", action="store_true", help="فقط /models، بدون تست چت")
    ap.add_argument("--no-cffi", action="store_true", help="بدون تست curl_cffi")
    args = ap.parse_args()

    key = args.key or load_env_key()
    print("=" * 62)
    print("🩺 تشخیص مستقل اتصال به Groq")
    print("=" * 62)
    print(f"  کلید: {'موجود (' + key[:10] + '...)' if key else '❌ پیدا نشده!'}")
    print(f"  پایه API: {args.base}")
    print("  نکته: این اسکریپت متغیر HTTPS_PROXY محیط را نادیده می‌گیرد"
          " تا مسیرها واقعاً جدا تست شوند.")

    dns_check()

    # ۱) مستقیم — بدون هیچ پروکسی
    test_route("مستقیم (بدون پروکسی)", make_session(), args.base, key, not args.no_chat)

    # ۲) HTTP/S پروکسی
    if args.proxy:
        test_route(f"پروکسی HTTP {args.proxy}", make_session(proxy=args.proxy),
                   args.base, key, not args.no_chat)

    # ۳) SOCKS
    if args.socks:
        try:
            import socks  # noqa: F401  — بررسی PySocks
            test_route(f"SOCKS {args.socks}", make_session(socks=args.socks),
                       args.base, key, not args.no_chat)
        except ImportError:
            record(f"SOCKS {args.socks}", None,
                   "پکیج PySocks نصب نیست →  pip install pysocks requests[socks]")

    # ۴) رله Render
    if args.relay:
        test_route(f"رله Render {args.relay}", make_session(), args.relay.rstrip("/"),
                   key, not args.no_chat)

    # ۵) اثر انگشت TLS مرورگر
    if not args.no_cffi:
        curl_cffi_test(args.base, key)

    summarize()


if __name__ == "__main__":
    main()
