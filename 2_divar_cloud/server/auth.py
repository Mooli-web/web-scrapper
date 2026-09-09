import os
import hmac
import hashlib
import time
from typing import Optional
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

ADMIN_USERNAME = os.getenv("DASHBOARD_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("DASHBOARD_ADMIN_PASS", "admin123")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")
JWT_SECRET = os.getenv("JWT_SECRET", "divar-cloud-secret-key-2026")

security = HTTPBearer(auto_error=False)

def create_access_token(username: str) -> str:
    timestamp = int(time.time()) + 86400 * 7 # 7 days
    payload = f"{username}:{timestamp}"
    signature = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"

def verify_credentials(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> str:
    if not AUTH_ENABLED:
        return "admin"

    if not credentials:
        raise HTTPException(status_code=401, detail="توکن احراز هویت الزامی است.")

    token = credentials.credentials
    parts = token.split(":")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="فرمت توکن نامعتبر است.")

    username, exp_str, signature = parts
    payload = f"{username}:{exp_str}"
    expected_sig = hmac.new(JWT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status_code=401, detail="امضای توکن نامعتبر است.")

    if int(exp_str) < int(time.time()):
        raise HTTPException(status_code=401, detail="توکن منقضی شده است.")

    return username
