import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
CRAWLER_DELAY_SEC = float(os.getenv("CRAWLER_DELAY_SEC", "1.8"))
CRAWLER_TIMEOUT_SEC = int(os.getenv("CRAWLER_TIMEOUT_SEC", "15"))
MAX_RETRIES = int(os.getenv("CRAWLER_MAX_RETRIES", "3"))
CONTINUOUS_MODE = os.getenv("CONTINUOUS_MODE", "true").lower() in ("true", "1", "yes")

USER_AGENT = os.getenv(
    "CRAWLER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 DivarMonitor/2.0"
)
