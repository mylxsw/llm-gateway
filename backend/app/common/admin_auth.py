"""
Admin Authentication

When ADMIN_USERNAME and ADMIN_PASSWORD are set, admin API endpoints require an admin token:
Authorization: Bearer <token>

The token is a stateless signed token and does not depend on external storage.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


_TOKEN_VERSION = 1


def is_admin_auth_enabled(admin_username: str | None, admin_password: str | None) -> bool:
    return bool(admin_username and admin_password)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def _signing_key(admin_username: str, admin_password: str) -> bytes:
    material = f"{admin_username}\0{admin_password}".encode("utf-8")
    return hashlib.sha256(material).digest()


def create_admin_token(
    *,
    admin_username: str,
    admin_password: str,
    ttl_seconds: int,
    now: int | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    expires_at = issued_at + int(ttl_seconds)

    payload = {
        "v": _TOKEN_VERSION,
        "sub": admin_username,
        "iat": issued_at,
        "exp": expires_at,
        "nonce": secrets.token_urlsafe(16),
    }

    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_b64 = _b64url_encode(payload_bytes)

    signature = hmac.new(
        _signing_key(admin_username, admin_password),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{payload_b64}.{signature_b64}"


def verify_admin_token(
    *,
    token: str,
    admin_username: str,
    admin_password: str,
    now: int | None = None,
) -> dict[str, Any] | None:
    """
    Verify and parse admin token.

    Returns:
        dict: payload (Verification passed)
        None: Verification failed
    """
    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError:
        return None

    try:
        expected_sig = hmac.new(
            _signing_key(admin_username, admin_password),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_sig = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None

    if payload.get("v") != _TOKEN_VERSION:
        return None
    if payload.get("sub") != admin_username:
        return None

    current_time = int(time.time() if now is None else now)
    exp = payload.get("exp")
    if not isinstance(exp, int):
        return None
    if current_time >= exp:
        return None

    return payload