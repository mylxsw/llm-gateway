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
async def test_admin_creates_and_updates_alias_for_real_model(db_session, monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        real_resp = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": "gpt-4o",
                "model_type": "chat",
                "disable_thinking": True,
            },
        )
        assert real_resp.status_code == 201, real_resp.text

        alias_resp = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": "gpt-latest",
                "model_type": "alias",
                "alias_target_model": "gpt-4o",
                "is_active": False,
                "disable_thinking": False,
            },
        )
        assert alias_resp.status_code == 201, alias_resp.text
        assert alias_resp.json()["alias_target_model"] == "gpt-4o"
        assert alias_resp.json()["is_active"] is True
        assert alias_resp.json()["disable_thinking"] is True

        fallback_resp = await ac.post(
            "/api/admin/models",
            json={"requested_model": "gpt-4o-mini", "model_type": "chat"},
        )
        assert fallback_resp.status_code == 201, fallback_resp.text
        convert_target_resp = await ac.put(
            "/api/admin/models/gpt-4o",
            json={"model_type": "alias", "alias_target_model": "gpt-4o-mini"},
        )
        assert convert_target_resp.status_code == 409, convert_target_resp.text
        assert convert_target_resp.json()["error"]["code"] == "model_referenced_by_alias"

        delete_target_resp = await ac.delete("/api/admin/models/gpt-4o")
        assert delete_target_resp.status_code == 409, delete_target_resp.text
        assert delete_target_resp.json()["error"]["code"] == "model_referenced_by_alias"

        update_resp = await ac.put(
            "/api/admin/models/gpt-latest",
            json={"is_active": False},
        )
        assert update_resp.status_code == 200, update_resp.text
        assert update_resp.json()["model_type"] == "alias"
        assert update_resp.json()["alias_target_model"] == "gpt-4o"
        assert update_resp.json()["is_active"] is True
        assert update_resp.json()["disable_thinking"] is True

        disable_target_resp = await ac.put(
            "/api/admin/models/gpt-4o",
            json={"is_active": False},
        )
        assert disable_target_resp.status_code == 200, disable_target_resp.text

        alias_detail_resp = await ac.get("/api/admin/models/gpt-latest")
        assert alias_detail_resp.status_code == 200, alias_detail_resp.text
        assert alias_detail_resp.json()["is_active"] is False
        assert alias_detail_resp.json()["disable_thinking"] is True

        inactive_list_resp = await ac.get("/api/admin/models?is_active=false")
        assert inactive_list_resp.status_code == 200, inactive_list_resp.text
        inactive_names = {
            item["requested_model"] for item in inactive_list_resp.json()["items"]
        }
        assert {"gpt-4o", "gpt-latest"} <= inactive_names

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_admin_rejects_alias_targeting_an_alias(db_session, monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/admin/models",
            json={"requested_model": "real-model", "model_type": "chat"},
        )
        first_alias = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": "first-alias",
                "model_type": "alias",
                "alias_target_model": "real-model",
            },
        )
        assert first_alias.status_code == 201, first_alias.text

        chained_alias = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": "second-alias",
                "model_type": "alias",
                "alias_target_model": "first-alias",
            },
        )

    assert chained_alias.status_code == 422, chained_alias.text
    assert chained_alias.json()["error"]["code"] == "invalid_alias_target"
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_admin_lists_lightweight_alias_targets(db_session, monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for name, model_type in (("target-chat", "chat"), ("target-image", "images")):
            response = await ac.post(
                "/api/admin/models",
                json={"requested_model": name, "model_type": model_type},
            )
            assert response.status_code == 201, response.text
        alias_response = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": "target-alias",
                "model_type": "alias",
                "alias_target_model": "target-chat",
            },
        )
        assert alias_response.status_code == 201, alias_response.text

        response = await ac.get("/api/admin/models/alias-targets")

    assert response.status_code == 200, response.text
    assert response.json() == [
        {"requested_model": "target-chat", "model_type": "chat", "is_active": True},
        {"requested_model": "target-image", "model_type": "images", "is_active": True},
    ]
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


@pytest.mark.asyncio
async def test_admin_create_model_provider_allows_null_cache_billing_enabled(
    db_session, monkeypatch
):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        provider_resp = await ac.post(
            "/api/admin/providers",
            json={
                "name": "null-cache-billing-provider",
                "base_url": "https://example.com",
                "protocol": "openai",
                "api_type": "chat",
                "is_active": True,
            },
        )
        assert provider_resp.status_code == 201, provider_resp.text
        provider_id = provider_resp.json()["id"]

        model_resp = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": "null-cache-billing-model",
                "strategy": "round_robin",
                "is_active": True,
            },
        )
        assert model_resp.status_code == 201, model_resp.text

        create_mapping_resp = await ac.post(
            "/api/admin/model-providers",
            json={
                "requested_model": "null-cache-billing-model",
                "provider_id": provider_id,
                "target_model_name": "qwen3-max",
                "priority": 0,
                "weight": 1,
                "is_active": True,
                "billing_mode": "inherit_model_default",
                "cache_billing_enabled": None,
            },
        )
        assert create_mapping_resp.status_code == 201, create_mapping_resp.text
        payload = create_mapping_resp.json()
        assert payload["cache_billing_enabled"] is False

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_admin_match_model_includes_multiple_mappings_for_same_provider(
    db_session, monkeypatch
):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    get_settings.cache_clear()

    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        provider_resp = await ac.post(
            "/api/admin/providers",
            json={
                "name": "same-provider-multi-target",
                "base_url": "https://example.com",
                "protocol": "openai",
                "api_type": "chat",
                "is_active": True,
            },
        )
        assert provider_resp.status_code == 201, provider_resp.text
        provider_id = provider_resp.json()["id"]

        model_resp = await ac.post(
            "/api/admin/models",
            json={
                "requested_model": "match-multi-target",
                "strategy": "round_robin",
                "is_active": True,
            },
        )
        assert model_resp.status_code == 201, model_resp.text

        mapping_a = await ac.post(
            "/api/admin/model-providers",
            json={
                "requested_model": "match-multi-target",
                "provider_id": provider_id,
                "target_model_name": "provider-model-a",
                "priority": 0,
                "billing_mode": "token_flat",
                "input_price": 1,
                "output_price": 2,
            },
        )
        assert mapping_a.status_code == 201, mapping_a.text

        mapping_b = await ac.post(
            "/api/admin/model-providers",
            json={
                "requested_model": "match-multi-target",
                "provider_id": provider_id,
                "target_model_name": "provider-model-b",
                "priority": 1,
                "billing_mode": "token_flat",
                "input_price": 1,
                "output_price": 2,
            },
        )
        assert mapping_b.status_code == 201, mapping_b.text

        match_resp = await ac.post(
            "/api/admin/models/match-multi-target/match",
            json={
                "input_tokens": 128,
            },
        )
        assert match_resp.status_code == 200, match_resp.text
        items = match_resp.json()
        assert len(items) == 2
        assert {item["provider_id"] for item in items} == {provider_id}
        assert {item["target_model_name"] for item in items} == {
            "provider-model-a",
            "provider-model-b",
        }

    app.dependency_overrides = {}
