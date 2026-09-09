@echo off
chcp 65001 > nul
title Local Torob Undetected Chrome & Arbitrage Engine
echo ==============================================================================
echo 🚀 سامانه محلی هوش بازار و آربیتراژ قیمت (Undetected Chrome Engine)
echo ==============================================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [خطا] پایتون روی سیستم شما یافت نشد!
    echo لطفاً Python را نصب کرده و مطمئن شوید تیک Add to PATH را زده‌اید.
    pause
    exit /b 1
)

:: 2. Create venv if needed
if not exist venv (
    echo [1/3] در حال ایجاد محیط مجازی پایتون (venv)...
    python -m venv venv
    if errorlevel 1 (
        echo [خطا] در ساخت venv مشکلی پیش آمد.
        pause
        exit /b 1
    )
)

:: 3. Install packages
echo [2/3] بررسی و نصب پکیج‌های پایتون (undetected-chromedriver, selenium, fastapi)...
call venv\Scripts\activate.bat
pip install -r requirements.txt

:: 4. Run local server
echo.
echo [3/3] در حال راه‌اندازی سرور محلی و باز کردن خودکار داشبورد...
echo.
echo ==============================================================================
echo 🌐 آدرس داشبورد: http://localhost:5000
echo ==============================================================================
echo.

python local_server.py

pause
