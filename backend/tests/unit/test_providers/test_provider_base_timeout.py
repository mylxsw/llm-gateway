from typing import Any, AsyncGenerator, Optional

import pytest

from app.domain.provider import DEFAULT_RESPONSE_TIMEOUT_SECONDS
from app.providers.base import ProviderClient, ProviderResponse


class DummyProviderClient(ProviderClient):
    async def forward(
        self,
        base_url: str,
        api_key: Optional[str],
        path: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
        target_model: str,
        response_mode: str = "parsed",
        extra_headers: Optional[dict[str, str]] = None,
        proxy_config: Optional[dict[str, str]] = None,
        response_timeout_seconds: Optional[int] = None,
    ) -> ProviderResponse:
        return ProviderResponse(status_code=200)

    async def list_models(
        self,
        base_url: str,
        api_key: Optional[str],
        extra_headers: Optional[dict[str, str]] = None,
        proxy_config: Optional[dict[str, str]] = None,
    ) -> ProviderResponse:
        return ProviderResponse(status_code=200)

    async def forward_stream(
        self,
        base_url: str,
        api_key: Optional[str],
        path: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
        target_model: str,
        extra_headers: Optional[dict[str, str]] = None,
        proxy_config: Optional[dict[str, str]] = None,
        response_timeout_seconds: Optional[int] = None,
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        if False:
            yield b"", ProviderResponse(status_code=200)


def test_resolve_timeout_uses_provider_default_when_no_client_timeout_exists():
    client = DummyProviderClient()

    assert client._resolve_timeout(None) == DEFAULT_RESPONSE_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 1),
        (7, 7),
    ],
)
def test_resolve_timeout_clamps_explicit_values(value, expected):
    client = DummyProviderClient()

    assert client._resolve_timeout(value) == expected
