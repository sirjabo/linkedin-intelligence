"""Security utilities: password hashing and JWT using stdlib only.

Uses HMAC-SHA256 for JWT signing — no cffi/cryptography dependency.
Uses pbkdf2_sha256 for passwords — pure Python, no bcrypt/cffi needed.
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Any

from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Minimal JWT (HS256) via stdlib ────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (padding % 4))


def _sign(header_payload: str, secret: str) -> str:
    sig = hmac.new(secret.encode(), header_payload.encode(), hashlib.sha256).digest()
    return _b64url_encode(sig)


def _make_token(payload: dict[str, Any]) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(payload).encode())
    sig = _sign(f"{header}.{body}", settings.SECRET_KEY)
    return f"{header}.{body}.{sig}"


def _verify_token(token: str) -> dict[str, Any]:
    """Raises ValueError on invalid/expired tokens."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    header, body, sig = parts
    expected_sig = _sign(f"{header}.{body}", settings.SECRET_KEY)
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Invalid token signature")
    payload = json.loads(_b64url_decode(body))
    if payload.get("exp", 0) < time.time():
        raise ValueError("Token expired")
    return payload


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    if extra:
        payload.update(extra)
    return _make_token(payload)


def create_refresh_token(subject: str) -> str:
    expire = int(time.time()) + settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    return _make_token({"sub": subject, "exp": expire, "type": "refresh"})


def decode_token(token: str) -> dict[str, Any]:
    """Raises ValueError on invalid or expired tokens."""
    return _verify_token(token)
