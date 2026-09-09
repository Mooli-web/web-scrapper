import sys
import os
import socket
import json
import platform
import subprocess
import time
from typing import Dict, Any

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  🔍 {title}")
    print("=" * 70)

def print_result(name: str, passed: bool, details: str = ""):
    icon = "✅ [PASSED]" if passed else "❌ [FAILED]"
    print(f"{icon} {name}")
    if details:
        print(f"   └── {details}")

# ==============================================================================
# TEST 1: System & Environment Variables Inspection
# ==============================================================================
def test_environment() -> Dict[str, Any]:
    print_header("۱. بررسی متغیرهای محیطی و پروکسی‌های سیستمی ویندوز")
    env_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy"]
    proxy_found = {}
    for var in env_vars:
        val = os.environ.get(var)
        if val:
            proxy_found[var] = val

    if proxy_found:
        print_result("بررسی متغیرهای پروکسی محیطی", False, f"پروکسی‌های فعال یافت شدند: {proxy_found}")
    else:
        print_result("بررسی متغیرهای پروکسی محیطی", True, "هیچ متغیر پروکسی فعالی در محیط ویندوز ست نشده است.")

    # Check Windows Registry Proxy (WinINet)
    reg_proxy = None
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if proxy_enable:
                proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
                reg_proxy = proxy_server
                print_result("پروکسی سیستمی ویندوز (Windows Settings)", False, f"پروکسی ویندوز فعال است: {proxy_server}")
            else:
                print_result("پروکسی سیستمی ویندوز (Windows Settings)", True, "پروکسی سیستمی ویندوز خاموش است.")
    except Exception as e:
        print_result("بررسی ریجستری ویندوز", True, f"بررسی انجام شد ({e})")

    return {"env_proxies": proxy_found, "win_proxy": reg_proxy}

# ==============================================================================
# TEST 2: Raw TCP Socket & DNS Resolution
# ==============================================================================
def test_dns_and_sockets():
    print_header("۲. تست لایه پایه سوکت و ترجمه DNS (Raw TCP Socket)")
    targets = [
        ("Google DNS", "8.8.8.8", 53),
        ("Cloudflare DNS", "1.1.1.1", 53),
        ("Digikala Web", "api.digikala.com", 443),
        ("Torob Web", "torob.com", 443),
        ("Torob API", "api.torob.com", 443)
    ]

    for label, host, port in targets:
        # DNS Resolution
        try:
            ip = socket.gethostbyname(host)
            dns_ok = True
        except Exception as e:
            ip = "ناموفق"
            dns_ok = False

        # Socket Connect
        sock_ok = False
        err_msg = ""
        if dns_ok:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4.0)
            try:
                s.connect((ip, port))
                sock_ok = True
                s.close()
            except Exception as ex:
                err_msg = str(ex)

        if dns_ok and sock_ok:
            print_result(f"اتصال سوکت TCP به {label} ({host}:{port})", True, f"IP: {ip} | وضعیت: متصل")
        elif not dns_ok:
            print_result(f"ترجمه DNS دامنه {host}", False, f"خطای DNS: {ip}")
        else:
            print_result(f"اتصال سوکت TCP به {label} ({host}:{port})", False, f"IP: {ip} | خطای سوکت: {err_msg}")

# ==============================================================================
# TEST 3: Python HTTP/HTTPS Client (Requests / urllib)
# ==============================================================================
def test_http_requests():
    print_header("۳. تست درخواست‌های HTTP/HTTPS در پایتون")
    import requests

    endpoints = [
        ("سایت عمومی (ipify)", "https://api.ipify.org?format=json"),
        ("دیجی‌کالا", "https://api.digikala.com/v1/search/?q=samsung&page=1"),
        ("صفحه اصلی ترب", "https://torob.com/"),
        ("جستجوی ترب", "https://api.torob.com/v4/base-product/search/?q=test&page=0&size=1")
    ]

    for label, url in endpoints:
        try:
            t0 = time.perf_counter()
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=7)
            latency = round((time.perf_counter() - t0) * 1000, 1)
            if r.status_code in [200, 301, 302]:
                print_result(f"ارسال درخواست HTTP به {label}", True, f"کد وضعیت: {r.status_code} | زمان پاسخ: {latency}ms")
            else:
                print_result(f"ارسال درخواست HTTP به {label}", False, f"کد وضعیت: {r.status_code} (خطای پاسخ سرور)")
        except Exception as e:
            print_result(f"ارسال درخواست HTTP به {label}", False, f"خطای ارتباط: {e}")

# ==============================================================================
# TEST 4: Playwright Subprocess & Network Channel Tests
# ==============================================================================
def test_playwright_channels():
    print_header("۴. تست اختصاصی مرورگرهای Playwright در ویندوز")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print_result("کتابخانه Playwright", False, "کتابخانه Playwright نصب نیست. اجرای `pip install playwright` لازم است.")
        return

    configs = [
        ("مرورگر پیش‌فرض Playwright Chromium", None, []),
        ("مرورگر Chromium با غیرفعال‌سازی سندباکس شبکه", None, ["--disable-features=NetworkServiceSandbox,NetworkService", "--no-sandbox"]),
        ("مرورگر سیستمی Microsoft Edge", "msedge", ["--no-sandbox"]),
        ("مرورگر سیستمی Google Chrome", "chrome", ["--no-sandbox"])
    ]

    for label, channel, custom_args in configs:
        print(f"\n▶ تست: {label}...")
        p = None
        browser = None
        try:
            p = sync_playwright().start()
            launch_kwargs = {
                "headless": True,
                "args": custom_args + ["--disable-gpu", "--disable-dev-shm-usage"]
            }
            if channel:
                launch_kwargs["channel"] = channel

            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            # Test 1: Navigation to external neutral site
            try:
                page.goto("https://example.com", timeout=10000)
                ex_ok = True
            except Exception as e:
                ex_ok = False
                ex_err = str(e)

            # Test 2: Navigation to Torob
            torob_ok = False
            torob_err = ""
            if ex_ok:
                try:
                    page.goto("https://torob.com/", timeout=15000)
                    torob_ok = True
                except Exception as e:
                    torob_err = str(e)

            if ex_ok and torob_ok:
                print_result(f"{label}", True, "باز کردن example.com و torob.com کاملاً موفقیت‌آمیز بود.")
            elif not ex_ok:
                print_result(f"{label}", False, f"حتی example.com نیز باز نشد! خطای ویندوز: {ex_err}")
            else:
                print_result(f"{label}", False, f"سایت example.com باز شد ولی torob.com ارور داد: {torob_err}")

        except Exception as e:
            print_result(f"راه‌اندازی {label}", False, f"خطای لانچ مرورگر: {e}")
        finally:
            try:
                if browser:
                    browser.close()
                if p:
                    p.stop()
            except Exception:
                pass

# ==============================================================================
# SUMMARY & FINAL DIAGNOSIS
# ==============================================================================
def main():
    print("\n" + "#" * 70)
    print("  🛠️ اسکریپت تشخیص دقیق و قطعی شبکه ویندوز (Diagnostic Tool)")
    print(f"  سیستم‌عامل: {platform.system()} {platform.release()} (Architecture: {platform.machine()})")
    print(f"  نسخه پایتون: {sys.version.split()[0]}")
    print("#" * 70)

    test_environment()
    test_dns_and_sockets()
    test_http_requests()
    test_playwright_channels()

    print("\n" + "=" * 70)
    print("  📋 تحلیل و نتیجه نهایی آماده است.")
    print("  لطفاً تمام خروجی این صفحه را در چت کپی و ارسال کنید.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
