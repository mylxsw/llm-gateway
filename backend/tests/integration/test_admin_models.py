import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db
from app.config import get_settings
from app.main import app


@pytest.mark.asyncio
async def test_admin_create_model_allows_missing_matching_rules(db_session, monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": "gpt-4o-admin-test",
                "strategy": "round_robin",
                "is_active": True,
            },
        )

    assert resp.status_code == 201, resp.text
    payload = resp.json()
    assert payload["requested_model"] == "gpt-4o-admin-test"
    assert payload.get("matching_rules") is None

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_admin_get_model_supports_slash_in_name(db_session, monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    app.dependency_overrides[get_db] = lambda: db_session

    requested_model = "coding/kimi"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_resp = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": requested_model,
                "strategy": "round_robin",
                "is_active": True,
            },
        )
        assert create_resp.status_code == 201, create_resp.text

        get_resp = await ac.get("/api/admin/models/coding%2Fkimi")

    assert get_resp.status_code == 200, get_resp.text
    payload = get_resp.json()
    assert payload["requested_model"] == requested_model

    app.dependency_overrides = {}
