from datetime import datetime, timezone
from unittest.mock import AsyncMock

from app.domain.provider import Provider
from app.services.provider_service import ProviderService


def test_to_response_includes_extra_headers():
    service = ProviderService(AsyncMock())
    provider = Provider(
        id=1,
        name="p1",
        base_url="http://p1",
        protocol="openai",
        api_type="chat",
        api_key="sk-test",
        extra_headers={"X-Test": "1"},
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    resp = service._to_response(provider)

    assert resp.extra_headers == {"X-Test": "1"}

