"""Unit tests for security functions — no HTTP, no DB."""
import time
import pytest
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)


def test_password_hash_and_verify():
    pwd = "mysecretpassword"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_access_token_decode():
    token = create_access_token("user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert payload["exp"] > time.time()


def test_refresh_token_decode():
    token = create_refresh_token("user-456")
    payload = decode_token(token)
    assert payload["sub"] == "user-456"
    assert payload["type"] == "refresh"


def test_expired_token_raises():
    # Manually create a token with past expiry
    import json, base64, hmac, hashlib
    from app.core.config import settings
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body_data = {"sub": "user-x", "exp": int(time.time()) - 10, "type": "access"}
    body = base64.urlsafe_b64encode(json.dumps(body_data).encode()).rstrip(b"=").decode()
    sig_bytes = hmac.new(settings.SECRET_KEY.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()
    expired_token = f"{header}.{body}.{sig}"
    with pytest.raises(ValueError, match="expired"):
        decode_token(expired_token)


def test_tampered_token_raises():
    token = create_access_token("user-789")
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.invalidsignature"
    with pytest.raises(ValueError, match="signature"):
        decode_token(tampered)


# ── SSRF Protection ───────────────────────────────────────────────────────────

from fastapi import HTTPException
from app.core.ssrf import validate_url_not_private


def test_ssrf_localhost_blocked():
    with pytest.raises(HTTPException) as exc_info:
        validate_url_not_private("http://localhost/internal")
    assert exc_info.value.status_code == 422


def test_ssrf_127_blocked():
    with pytest.raises(HTTPException) as exc_info:
        validate_url_not_private("http://127.0.0.1/api")
    assert exc_info.value.status_code == 422


def test_ssrf_private_10_blocked():
    with pytest.raises(HTTPException) as exc_info:
        validate_url_not_private("http://10.0.0.1/internal")
    assert exc_info.value.status_code == 422


def test_ssrf_private_192_blocked():
    with pytest.raises(HTTPException) as exc_info:
        validate_url_not_private("http://192.168.1.1/router")
    assert exc_info.value.status_code == 422


def test_ssrf_invalid_scheme_blocked():
    with pytest.raises(HTTPException) as exc_info:
        validate_url_not_private("ftp://somehost.com/file")
    assert exc_info.value.status_code == 422


def test_ssrf_public_url_allowed():
    # A well-known public hostname — should not raise
    # We use example.com which resolves to a public IP
    # If DNS resolution fails in CI, this is OK (unreachable ≠ private)
    try:
        validate_url_not_private("https://example.com/page")
    except HTTPException as e:
        # Only acceptable failure is DNS resolution error
        assert "Cannot resolve" in e.detail or "private" not in e.detail
