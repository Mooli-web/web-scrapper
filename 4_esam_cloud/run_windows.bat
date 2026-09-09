@echo off
chcp 65001 > nul
echo ==========================================================
echo   سامانه هوش و پایش قیمت ایسام (Esam Intelligence)
echo ==========================================================
echo.

if not exist venv (
    echo [1/3] در حال ساخت محیط مجازی پایتون (venv)...
    python -m venv venv
)

echo [2/3] فعال‌سازی محیط مجازی و نصب وابستگی‌ها...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo [3/3] اجرای سرور محلی ایسام روی پورت 8000...
start http://localhost:8000
python run_local.py

pause
