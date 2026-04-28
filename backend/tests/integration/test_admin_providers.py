import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db, require_admin_auth
from app.main import app


@pytest.mark.asyncio
async def test_update_provider_can_clear_extra_headers(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin_auth] = lambda: None

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            create_resp = await ac.post(
                "/api/admin/providers",
                json={
                    "name": "clear-extra-headers-provider",
                    "base_url": "https://example.com",
                    "protocol": "openai",
                    "api_type": "chat",
                    "is_active": True,
                    "extra_headers": {"X-Test": "1"},
                },
            )
            assert create_resp.status_code == 201, create_resp.text

            provider = create_resp.json()
            update_resp = await ac.put(
                f"/api/admin/providers/{provider['id']}",
                json={
                    "name": provider["name"],
                    "base_url": provider["base_url"],
                    "protocol": provider["protocol"],
                    "is_active": provider["is_active"],
                    "extra_headers": {},
                },
            )
            assert update_resp.status_code == 200, update_resp.text
            assert update_resp.json()["extra_headers"] == {}

            get_resp = await ac.get(f"/api/admin/providers/{provider['id']}")
            assert get_resp.status_code == 200, get_resp.text
            assert get_resp.json()["extra_headers"] == {}
    finally:
        app.dependency_overrides = {}
