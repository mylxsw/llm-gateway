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


@pytest.mark.asyncio
async def test_admin_bulk_upgrade_model_providers(db_session, monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        provider_resp = await ac.post(
            "/api/admin/providers",
            json={
                "name": "bulk-upgrade-provider",
                "base_url": "https://example.com",
                "protocol": "openai",
                "api_type": "chat",
                "is_active": True,
            },
        )
        assert provider_resp.status_code == 201, provider_resp.text
        provider_id = provider_resp.json()["id"]

        for requested_model in ["bulk-a", "bulk-b"]:
            create_model_resp = await ac.post(
                "/api/admin/models",
                json={
                    "requested_model": requested_model,
                    "strategy": "round_robin",
                    "is_active": True,
                },
            )
            assert create_model_resp.status_code == 201, create_model_resp.text

            create_mapping_resp = await ac.post(
                "/api/admin/model-providers",
                json={
                    "requested_model": requested_model,
                    "provider_id": provider_id,
                    "target_model_name": "old-model",
                    "billing_mode": "token_flat",
                    "input_price": 1,
                    "output_price": 2,
                },
            )
            assert create_mapping_resp.status_code == 201, create_mapping_resp.text

        bulk_upgrade_resp = await ac.post(
            "/api/admin/model-providers/bulk-upgrade",
            json={
                "provider_id": provider_id,
                "current_target_model_name": "old-model",
                "new_target_model_name": "new-model",
                "billing_mode": "per_request",
                "per_request_price": 0.0021,
            },
        )
        assert bulk_upgrade_resp.status_code == 200, bulk_upgrade_resp.text
        assert bulk_upgrade_resp.json()["updated_count"] == 2

        list_resp = await ac.get(f"/api/admin/model-providers?provider_id={provider_id}")
        assert list_resp.status_code == 200, list_resp.text
        items = list_resp.json()["items"]
        assert len(items) == 2
        for item in items:
            assert item["target_model_name"] == "new-model"
            assert item["billing_mode"] == "per_request"
            assert item["per_request_price"] == 0.0021

    app.dependency_overrides = {}
