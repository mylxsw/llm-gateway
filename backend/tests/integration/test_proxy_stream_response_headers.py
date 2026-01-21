import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_api_key, get_db, get_proxy_service
from app.common.time import utc_now
from app.domain.api_key import ApiKeyModel
from app.main import app
from app.providers.base import ProviderResponse


class _DummyProxyService:
    async def process_request_stream(self, *args, **kwargs):
        async def gen():
            yield b"data: hello\n\n"

        # Simulate a buggy upstream provider that returns both headers.
        initial = ProviderResponse(
            status_code=200,
            headers={
                "Content-Type": "text/event-stream",
                "Content-Length": "123",
                "Transfer-Encoding": "chunked",
            },
            body=None,
        )
        return initial, gen(), {}


@pytest.mark.asyncio
async def test_streaming_proxy_does_not_forward_content_length_header(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_proxy_service] = lambda: _DummyProxyService()

    mock_api_key = ApiKeyModel(
        id=1,
        key_name="test-key",
        key_value="sk-test...",
        is_active=True,
        created_at=utc_now(),
        last_used_at=None,
    )
    app.dependency_overrides[get_current_api_key] = lambda: mock_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/v1/chat/completions", json={"model": "gpt-test", "stream": True})

    assert resp.status_code == 200
    assert "content-length" not in resp.headers
    assert "transfer-encoding" not in resp.headers

    app.dependency_overrides = {}

