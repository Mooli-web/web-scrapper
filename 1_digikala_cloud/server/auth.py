import os
import time
import hmac
import hashlib
import base64
import json
from typing import Optional
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

ADMIN_USERNAME = os.getenv("DASHBOARD_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("DASHBOARD_ADMIN_PASS", "admin123")
AUTH_SECRET = os.getenv("AUTH_SECRET", "digikala-market-intelligence-2026")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")

security = HTTPBearer(auto_error=False)

def create_access_token(username: str) -> str:
    """Creates a lightweight signed JWT access token."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": username,
        "exp": int(time.time()) + (86400 * 7) # 7 days validity
    }).encode()).decode().rstrip("=")
    
    signature = hmac.new(
        AUTH_SECRET.encode(),
        f"{header}.{payload}".encode(),
        hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{header}.{payload}.{sig_b64}"

def verify_token(token: str) -> Optional[str]:
    """Verifies signature and expiration of token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        
        expected_sig = hmac.new(
            AUTH_SECRET.encode(),
            f"{header}.{payload}".encode(),
            hashlib.sha256
        ).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        
        if not hmac.compare_digest(sig, expected_b64):
            return None
            
        payload_padded = payload + "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload_padded.encode()).decode())
        
        if data.get("exp", 0) < time.time():
            return None
            
        return data.get("sub")
    except Exception:
        return None

def verify_credentials(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[str]:
    """FastAPI Dependency for route protection."""
    if not AUTH_ENABLED:
        return "admin"
        
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="احراز هویت الزامی است (توکن یافت نشد)",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user = verify_token(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نشست کاری شما منقضی شده است. لطفاً دوباره وارد شوید.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
