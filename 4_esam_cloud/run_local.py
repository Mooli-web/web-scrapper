import os
import sys
import subprocess
import webbrowser
import time

def main():
    print("==========================================================")
    print("  سامانه پایش هوشمند ایسام (Esam Cloud / Local Engine)   ")
    print("==========================================================")
    
    # Check dependencies
    try:
        import fastapi
        import uvicorn
        import requests
        import bs4
    except ImportError:
        print("📦 در حال نصب پیش‌نیازهای پایتون...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    print("🚀 در حال راه‌اندازی سرور FastAPI روی پورت 8000...")
    
    # Try opening browser after a brief delay
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:8000")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
