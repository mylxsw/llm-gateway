import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db, require_admin_auth
from app.config import get_settings
from app.main import app


@pytest.mark.asyncio
async def test_auth_status_returns_enable_view_api_keys_flag(monkeypatch):
    monkeypatch.setenv("ENABLE_VIEW_API_KEYS", "true")
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/auth/status")

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["enable_view_api_keys"] is True

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_auth_status_fail_closed_when_admin_credentials_missing(monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("ALLOW_UNAUTHENTICATED_ADMIN", "false")
    get_settings.cache_clear()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/auth/status")
        protected_resp = await ac.get("/api/admin/providers")

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["enabled"] is True
    assert payload["authenticated"] is False
    assert protected_resp.status_code == 401, protected_resp.text

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_api_key_raw_endpoint_respects_enable_view_api_keys(db_session, monkeypatch):
    monkeypatch.setenv("ENABLE_VIEW_API_KEYS", "false")
    get_settings.cache_clear()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin_auth] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_resp = await ac.post(
            "/api/admin/api-keys",
            json={"key_name": "raw-view-flag-test"},
        )
        assert create_resp.status_code == 201, create_resp.text
        key_id = create_resp.json()["id"]

        blocked_resp = await ac.get(f"/api/admin/api-keys/{key_id}/raw")
        assert blocked_resp.status_code == 403, blocked_resp.text
        assert blocked_resp.json()["error"]["code"] == "api_key_view_disabled"

        monkeypatch.setenv("ENABLE_VIEW_API_KEYS", "true")
        get_settings.cache_clear()

        allowed_resp = await ac.get(f"/api/admin/api-keys/{key_id}/raw")
        assert allowed_resp.status_code == 200, allowed_resp.text
        assert isinstance(allowed_resp.json().get("key_value"), str)
        assert len(allowed_resp.json()["key_value"]) > 0

    app.dependency_overrides = {}
    get_settings.cache_clear()
