
import pytest
from httpx import ASGITransport, AsyncClient
from app.api.deps import get_db, require_admin_auth
from app.main import app

@pytest.mark.asyncio
async def test_admin_pagination_limit(db_session):
    # Override dependencies
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_admin_auth] = lambda: None

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

    # Clean up overrides
    app.dependency_overrides = {}
