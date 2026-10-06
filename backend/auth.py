"""
JWT authentication utilities.
Passwords: argon2 via passlib.
Tokens: HS256 JWT via python-jose.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from backend.config.settings import get_settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any]) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    s = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=s.access_token_expire_minutes)
    payload = {**data, "exp": expire, "iat": datetime.now(UTC)}
    token = jwt.encode(payload, s.secret_key, algorithm="HS256")
    return token, s.access_token_expire_minutes * 60


def decode_token(token: str) -> dict[str, Any]:
    s = get_settings()
    return jwt.decode(token, s.secret_key, algorithms=["HS256"])
