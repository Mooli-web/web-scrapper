# -*- coding: utf-8 -*-
"""
🩺 اسکریپت وضعیت فعال‌سازی — health_check.py
==============================================
یک دستور → گزارش کامل: چی فعاله، چی نیست، و دقیقاً برای فعال کردن هر مورد
چیکار کنی. بخش‌ها:
  ۱) محلی: .env (کلیدها/زمان‌بند)، سرور هاب (status/scheduler/آمار AI)
  ۲) ریموت: هر سرویس Render — فیلتر خزنده (mode/آمار) + سلامت رله Groq

اجرا (پوشه 5_unified_local_hub — هاب روشن یا خاموش):
    python health_check.py
"""

import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ pip install requests")
    sys.exit(1)

HUB = Path(__file__).resolve().parent
LOCAL = "http://localhost:7000"


def env_map():
    env = {}
    f = HUB / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def get(url, timeout=8):
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code, (r.json() if "json" in r.headers.get("content-type", "") else None)
    except Exception as e:
        return 0, str(e)[:60]


def main():
    env = env_map()
    ok, warn, todo = [], [], []

    print("=" * 62)
    print("🩺 گزارش وضعیت فعال‌سازی پروژه")
    print("=" * 62)

    # ---------------- محلی: .env ----------------
    print("\n—— ۱) تنظیمات محلی (.env) ——")
    keys = [k for k in env if k.startswith("GROQ_API_KEY")]
    keys += [k for k in env.get("GROQ_API_KEYS", "").replace(",", " ").split() if k.startswith("gsk_")]
    if keys:
        ok.append(f"کلید Groq: {len(keys)} عدد")
    else:
        todo.append("کلید Groq نیست → GROQ_API_KEY=gsk_... در .env")
    relay = env.get("GROQ_BASE_URL", "")
    if "/ai-relay/" in relay:
        ok.append(f"رله Groq فعال: {relay}")
    else:
        warn.append("GROQ_BASE_URL روی رله تنظیم نیست (اگر 403 می‌گیری، تنظیمش کن)")
    interval = env.get("AUTO_SYNC_INTERVAL_MINUTES", "360")
    daily = env.get("AUTO_SYNC_DAILY_AT", "")
    sched_desc = f"روزی یک‌بار {daily}" if daily else f"هر {interval} دقیقه"
    ok.append(f"زمان‌بند خودکار: {sched_desc}")

    # ---------------- محلی: سرور هاب ----------------
    print("\n—— ۲) سرور هاب (محلی) ——")
    code, st = get(f"{LOCAL}/api/status")
    if code == 200:
        ok.append(f"هاب آنلاین — {st['total_store_listings']:,} آگهی | پاکی {st['data_purity_percent']}٪")
        code2, sch = get(f"{LOCAL}/api/sync/scheduler")
        if code2 == 200:
            ok.append(f"زمان‌بند: {sch['mode']} | آخرین چرخه: {sch.get('last_run_at') or 'هنوز اجرا نشده'}"
                      f" | صف AI: {sch.get('ai_pending', 0):,}")
        code3, ps = get(f"{LOCAL}/api/audit/purification-stats")
        if code3 == 200 and ps.get("groq"):
            g = ps["groq"]
            ok.append(f"Groq: {g['keys_count']} کلید | مدل {g['model']} | {g['tokens_used']:,} توکن")
    else:
        todo.append("هاب خاموش است → run_windows.bat را اجرا کن و دوباره این اسکریپت را بزن")

    # ---------------- ریموت: خزنده‌ها ----------------
    print("\n—— ۳) سرویس‌های Render (خزنده‌ها) ——")
    services = [
        ("دیوار", env.get("DIVAR_RENDER_URL", "https://wall-crawler.onrender.com")),
        ("ایسام", env.get("ESAM_RENDER_URL", "https://ec-fjpk.onrender.com")),
        ("دیجی‌کالا", env.get("DIGIKALA_RENDER_URL", "https://dcp-s1y4.onrender.com")),
    ]
    for name, base in services:
        if not base:
            continue
        code, jf = get(f"{base}/api/junk-filter/stats", timeout=20)
        if code == 200 and isinstance(jf, dict):
            c = jf.get("counters", {})
            if jf.get("mode") == "active":
                ok.append(f"{name}: فیلتر چرت فعال ✅ ({c.get('dropped', 0):,} حذف در لحظه)")
            else:
                todo.append(f"{name}: فیلتر در حالت {jf.get('mode')} — "
                            f"{c.get('candidates', 0):,} کاندیدا تاکنون → بعد از بررسی نمونه‌ها فعالش کن")
        else:
            warn.append(f"{name}: endpoint فیلتر جواب نداد (کد {code}) — کد جدید دیپلوی شده؟")
        code_r, _ = get(f"{base}/ai-relay/v1/health", timeout=20)
        if code_r == 200:
            ok.append(f"{name}: رله Groq زنده ✅")

    # ---------------- چند-شهری ----------------
    print("\n—— ۴) چند-شهری دیوار ——")
    cities = env.get("DIVAR_CITIES", "")  # فقط در Render معنا دارد؛ محلی صرفاً یادآور
    if cities:
        ok.append(f"DIVAR_CITIES (محلی) = {cities}")
    todo.append("DIVAR_CITIES را در Render → سرویس دیوار → Environment بگذار "
                "(مثلاً tehran,karaj,isfahan) — از محلی قابل تنظیم نیست")

    # ---------------- جمع‌بندی ----------------
    print("\n" + "=" * 62)
    print("✅ فعال/سالم:")
    for x in ok:
        print(f"   • {x}")
    if warn:
        print("\n⚠️ هشدار:")
        for x in warn:
            print(f"   • {x}")
    if todo:
        print("\n📋 کارهای باقی‌مانده:")
        for i, x in enumerate(todo, 1):
            print(f"   {i}. {x}")
    print("\n💡 تست‌ها:  python -m pytest tests/ -v")
    print("=" * 62)


if __name__ == "__main__":
    main()
