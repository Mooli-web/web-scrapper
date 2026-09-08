@echo off
chcp 65001 > nul
echo ==================================================================
echo   🚀 هاب مرکزی پایش و آربیتراژ چهار بازاری (Quad-Market Local Hub)
echo ==================================================================
echo.

if not exist venv (
    echo [1/3] در حال ساخت محیط مجازی پایتون (venv)...
    python -m venv venv
)

echo [2/3] فعال‌سازی محیط مجازی و نصب وابستگی‌ها...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo [3/3] اجرای سرور هاب مشترک روی پورت 7000...
start http://localhost:7000
python run_local.py

pause
