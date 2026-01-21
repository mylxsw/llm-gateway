from app.common.time import utc_now
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.proxy_service import ProxyService


@pytest.mark.asyncio
async def test_process_request_same_protocol_response_body_passthrough_bytes():
    now = utc_now()
    model_mapping = ModelMapping(
        requested_model="test-model",
        strategy="round_robin",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    candidate = CandidateProvider(
        provider_id=1,
        provider_name="p-openai",
        base_url="https://example.com",
        protocol="openai",
        api_key="sk-test",
        target_model="gpt-4o-mini",
        priority=0,
        weight=1,
    )

    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
    )
    service._resolve_candidates = AsyncMock(return_value=(model_mapping, [candidate], 0, "openai", {}))  # type: ignore[method-assign]

    async def forward(*, response_mode: str = "parsed", **kwargs):
        assert response_mode == "raw"
        return ProviderResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body=b'{"id":"raw","usage":{"completion_tokens":12}}',
        )

    fake_client = AsyncMock()
    fake_client.forward = AsyncMock(side_effect=forward)

    with patch("app.services.proxy_service.get_provider_client", return_value=fake_client):
        with patch(
            "app.services.proxy_service.convert_request_for_supplier",
            return_value=("/v1/chat/completions", {"model": "gpt-4o-mini", "messages": []}),
        ):
            with patch(
                "app.services.proxy_service.convert_response_for_user",
                side_effect=AssertionError("convert_response_for_user should be skipped for same protocol"),
            ):
                response, _ = await service.process_request(
                    api_key_id=1,
                    api_key_name="k",
                    request_protocol="openai",
                    path="/v1/chat/completions",
                    method="POST",
                    headers={},
                    body={"model": "test-model", "messages": []},
                )

    assert response.status_code == 200
    assert response.body == b'{"id":"raw","usage":{"completion_tokens":12}}'
    service.log_repo.create.assert_awaited()

    log_data = service.log_repo.create.await_args.args[0]
    assert log_data.output_tokens == 12
