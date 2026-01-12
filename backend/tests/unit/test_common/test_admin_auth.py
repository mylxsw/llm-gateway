import time

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin_auth
from app.common.admin_auth import create_admin_token, is_admin_auth_enabled, verify_admin_token
from app.config import get_settings


def test_is_admin_auth_enabled():
    assert is_admin_auth_enabled(None, None) is False
    assert is_admin_auth_enabled("u", None) is False
    assert is_admin_auth_enabled(None, "p") is False
    assert is_admin_auth_enabled("u", "p") is True


def test_create_and_verify_token_roundtrip():
    token = create_admin_token(
        admin_username="admin",
        admin_password="secret",
        ttl_seconds=60,
        now=1000,
    )
    payload = verify_admin_token(
        token=token,
        admin_username="admin",
        admin_password="secret",
        now=1001,
    )
    assert payload is not None
    assert payload["sub"] == "admin"


def test_verify_token_expired():
    token = create_admin_token(
        admin_username="admin",
        admin_password="secret",
        ttl_seconds=1,
        now=1000,
    )
    assert (
        verify_admin_token(
            token=token,
            admin_username="admin",
            admin_password="secret",
            now=1001,
        )
        is None
    )


@pytest.mark.asyncio
async def test_require_admin_auth_disabled_allows(monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    await require_admin_auth(authorization=None, x_admin_token=None)


@pytest.mark.asyncio
async def test_require_admin_auth_enabled_requires_token(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as excinfo:
        await require_admin_auth(authorization=None, x_admin_token=None)
    assert excinfo.value.status_code == 401

    token = create_admin_token(
        admin_username="admin",
        admin_password="secret",
        ttl_seconds=60,
        now=int(time.time()),
    )
    await require_admin_auth(authorization=f"Bearer {token}", x_admin_token=None)