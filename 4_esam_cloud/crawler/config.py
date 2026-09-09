import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

ESAM_BASE_URL = os.getenv("ESAM_BASE_URL", "https://esam.ir")

# Polite rate-limiting
CRAWLER_DELAY_SEC = float(os.getenv("CRAWLER_DELAY_SEC", "2.0"))
CRAWLER_TIMEOUT_SEC = int(os.getenv("CRAWLER_TIMEOUT_SEC", "15"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Optional Proxy for cloud environments (if Esam CDN enforces Iran-only IP routing)
HTTP_PROXY = os.getenv("HTTP_PROXY", "")
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")

# Realistic desktop User-Agent
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Admin credentials
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET", "esam_commodity_secret_token_2026_safe")

PORT = int(os.getenv("PORT", "8000"))
