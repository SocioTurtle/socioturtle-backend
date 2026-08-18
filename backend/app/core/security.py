from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.config import get_settings

settings = get_settings()

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(subject: str | int, token_type: TokenType) -> tuple[str, int]:
    if token_type == "access":
        ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    else:
        ttl = timedelta(days=settings.refresh_token_ttl_days)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, int(ttl.total_seconds())


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return payload
