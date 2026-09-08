import os
import sys
import subprocess
import webbrowser
import time
import threading
from pathlib import Path

def _detect_port() -> int:
    """
    FIX: the port was hardcoded to 3000 here while README.md and the .env
    written by the settings page both say 7000. Now PORT is read from the
    environment / .env file with a single consistent default (7000).
    """
    try:
        from dotenv import load_dotenv
        env_file = Path(".env")
        if not env_file.exists():
            env_file = Path(__file__).resolve().parent / ".env"
        load_dotenv(dotenv_path=env_file)
    except ImportError:
        pass
    try:
        return int(os.getenv("PORT", "7000"))
    except ValueError:
        return 7000

def main():
    print("==================================================================")
    print("  🚀 هاب مرکزی پایش و آربیتراژ چهار بازاری (Quad-Market Local Hub) ")
    print("  دیجی‌کالا | ترب | دیوار | ایسام + دیتابیس مشترک + موتور هوش مصنوعی  ")
    print("==================================================================")
    print()

    # Check dependencies
    try:
        import fastapi
        import uvicorn
    except ImportError:
        print("📦 در حال نصب پیش‌نیازهای پایتون...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    port = _detect_port()

    def open_browser():
        time.sleep(2)
        url = f"http://localhost:{port}"
        print(f"🌐 در حال باز کردن داشبورد تحلیلی در مرورگر: {url}")
        webbrowser.open(url)

    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    main()
