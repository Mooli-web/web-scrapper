import sys
import os
import json
import time
import re
import requests

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  🔍 {title}")
    print("=" * 70)

def main():
    print("\n" + "#" * 70)
    print("  🛠️ کالبدشکافی عمیق ساختار HTML و تگ‌های صفحه وب دیوار")
    print("#" * 70)

    web_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8",
        "Referer": "https://divar.ir/"
    }

    url = "https://divar.ir/s/tehran/mobile-phones"
    print(f"در حال دریافت HTML از: {url}...")
    try:
        t0 = time.perf_counter()
        resp = requests.get(url, headers=web_headers, timeout=12)
        latency = round((time.perf_counter() - t0) * 1000, 1)
        print(f"✅ کد وضعیت: {resp.status_code} ({latency}ms) | حجم HTML: {len(resp.text)} کاراکتر")

        html = resp.text

        # 1. Check all embedded script tags
        print_header("۱. اسکریپت‌های جیسون تعبیه‌شده در صفحه (Embedded Scripts)")
        scripts = re.findall(r'<script([^>]*)>(.*?)</script>', html, re.DOTALL)
        print(f"تعداد کل تگ‌های script در صفحه: {len(scripts)}")
        
        found_data_script = False
        for attr, content in scripts:
            if "type=\"application/json\"" in attr or "type='application/json'" in attr or "__" in content or "INITIAL" in content or "state" in content.lower():
                print(f"\n🔹 تگ اسکریپت با ویژگی: <script {attr.strip()}>")
                print(f"   محتوای اولیه: {content.strip()[:250]}...")
                found_data_script = True

        if not found_data_script:
            print("هیچ اسکریپت JSON اختصاصی با فرمت‌های شناخته‌شده یافت نشد.")

        # 2. Check HTML Post Cards & Links (a href="/v/...")
        print_header("۲. استخراج مستقیم کارت‌های آگهی از کدهای HTML (Post Links & Cards)")
        
        # Search for post tokens / URLs like href="/v/..."
        post_links = re.findall(r'href=["\'](/v/[^"\']+)["\']', html)
        # Unique preserve order
        unique_links = list(dict.fromkeys(post_links))
        print(f"تعداد لینک‌های آگهی (/v/...) یافت شده در HTML: {len(unique_links)}")

        if unique_links:
            print(f"نمونه ۵ لینک آگهی اول:")
            for l in unique_links[:5]:
                print(f"   • https://divar.ir{l}")

        # Search for post cards with titles and prices in HTML
        # Look for article tags or div cards
        cards = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        print(f"\nتعداد تگ‌های <article> (کارت آگهی): {len(cards)}")
        if not cards:
            cards = re.findall(r'<a[^>]*class=["\'][^"\']*(?:kt-post-card|post-card)[^"\']*["\'][^>]*>(.*?)</a>', html, re.DOTALL)
            print(f"تعداد تگ‌های با کلاس post-card: {len(cards)}")

        if cards:
            first_card = cards[0]
            # Strip tags to see clean text
            clean_text = re.sub(r'<[^>]+>', ' | ', first_card)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            print(f"متن استخراج‌شده از اولین کارت آگهی:\n   {clean_text[:200]}")

    except Exception as e:
        print(f"❌ خطای دریافت: {e}")

    print("\n" + "=" * 70)
    print("  📋 تحلیل به پایان رسید. لطفاً خروجی را در چت ارسال کنید.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
