
import pytest
from httpx import ASGITransport, AsyncClient
from app.api.deps import get_db, require_admin_auth
from app.main import app


@pytest.mark.asyncio
async def test_admin_pagination_limit(db_session):
    # Override dependencies
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin_auth] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Test models pagination
            resp = await ac.get("/api/admin/models?page=1&page_size=1000")
            assert resp.status_code == 200, f"Models pagination failed: {resp.text}"

            # Test api-keys pagination
            resp = await ac.get("/api/admin/api-keys?page=1&page_size=1000")
            assert resp.status_code == 200, f"API Keys pagination failed: {resp.text}"

            # Test providers pagination
            resp = await ac.get("/api/admin/providers?page=1&page_size=1000")
            assert resp.status_code == 200, f"Providers pagination failed: {resp.text}"

            # Test limit exceeded (should fail if I set le=1000)
            resp = await ac.get("/api/admin/models?page=1&page_size=1001")
            assert resp.status_code == 422, f"Should fail for page_size > 1000: {resp.text}"
    finally:
        app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_provider_names_are_not_paginated_and_sorted(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin_auth] = lambda: None

    names = [f"provider-{index:02d}" for index in range(25, 0, -1)]

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for name in names:
                resp = await ac.post(
                    "/api/admin/providers",
                    json={
                        "name": name,
                        "base_url": "https://example.com",
                        "protocol": "openai",
                        "api_type": "chat",
                        "is_active": True,
                    },
                )
                assert resp.status_code == 201, resp.text

            list_resp = await ac.get("/api/admin/providers")
            assert list_resp.status_code == 200, list_resp.text
            assert len(list_resp.json()["items"]) == 20

            names_resp = await ac.get("/api/admin/providers/names")
            assert names_resp.status_code == 200, names_resp.text

        payload = names_resp.json()
        payload_names = [item["name"] for item in payload]

        assert len(payload) == 25
        assert payload_names == sorted(names)
        assert set(payload[0].keys()) == {"id", "name", "protocol", "is_active"}
    finally:
        app.dependency_overrides = {}
