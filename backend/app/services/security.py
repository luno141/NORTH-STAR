from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_api_key(api_key: str) -> str:
    payload = f"{settings.api_key_pepper}:{api_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate_api_key(prefix: str = "ps13") -> str:
    token = secrets.token_urlsafe(24)
    return f"{prefix}_{token}"


def create_access_token(subject: dict[str, Any], expires_minutes: int | None = None) -> str:
    minutes = expires_minutes or settings.jwt_expire_minutes
    now = utcnow()
    payload = {
        **subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid access token") from exc
