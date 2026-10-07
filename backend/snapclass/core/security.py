"""Passwords, tokens and signed media URLs."""

import hashlib
import hmac
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import bcrypt
import jwt

from snapclass.core.config import settings

BCRYPT_COST = 12
JWT_ALGORITHM = "HS256"


# ---------- Passwords ----------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_COST)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# A real hash we can check against when the email does not exist. This makes
# "unknown email" and "wrong password" take the same time, so attackers cannot
# discover which emails are registered by timing the response.
DUMMY_PASSWORD_HASH = hash_password("not-a-real-password")


# ---------- Access tokens (JWT, short lived) ----------


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Return the token payload, or None if the token is invalid or expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload


# ---------- Refresh tokens (random, stored only as a hash) ----------


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # SHA-256 is fine here (unlike passwords) because the token is long and random.
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- Signed media URLs (like S3 presigned GET URLs) ----------


def _media_signature(key: str, expires: int) -> str:
    message = f"{key}:{expires}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def signed_media_url(key: str | None) -> str | None:
    if not key:
        return None
    expires = int(time.time()) + settings.signed_url_seconds
    signature = _media_signature(key, expires)
    return f"/api/v1/media/{quote(key)}?exp={expires}&sig={signature}"


def verify_media_signature(key: str, expires: int, signature: str) -> bool:
    if expires < int(time.time()):
        return False
    expected = _media_signature(key, expires)
    # compare_digest takes the same time for every input (no timing leak).
    return hmac.compare_digest(expected, signature)
