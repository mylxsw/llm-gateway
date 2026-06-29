"""Failure-path coverage for initial request logs."""

from unittest.mock import AsyncMock, patch

import pytest

from app.common.errors import ServiceError
from app.common.time import utc_now
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.active_requests import active_requests
from app.services.proxy_service import ProxyService


def _service_with_resolution_failure() -> ProxyService:
    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
    )
    service.log_repo.create_initial.return_value = 42
    service._resolve_candidates = AsyncMock(  # type: ignore[method-assign]
        side_effect=ServiceError("No providers", code="no_available_provider")
    )
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_resolution_failure_completes_initial_log(stream):
    service = _service_with_resolution_failure()
    method = (
        service.process_request_stream if stream else service.process_request
    )

    with pytest.raises(ServiceError):
        await method(
            api_key_id=1,
            api_key_name="key",
            request_protocol="openai",
            path="/v1/chat/completions",
            request_url="/v1/chat/completions",
            method="POST",
            headers={},
            body={"model": "test-model", "messages": []},
        )

    service.log_repo.create_initial.assert_awaited_once()
    service.log_repo.update.assert_awaited_once()
    log_id, log_data = service.log_repo.update.await_args.args
    assert log_id == 42
    assert log_data.is_completed is True
    assert log_data.response_status == 503
    assert log_data.error_info == "No providers"
    assert await active_requests.is_active(42) is False


@pytest.mark.asyncio
async def test_all_provider_failures_still_complete_initial_log():
    class RetrySettings:
        RETRY_MAX_ATTEMPTS = 1
        RETRY_DELAY_MS = 0

    now = utc_now()
    mapping = ModelMapping(
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
        provider_name="broken-provider",
        base_url="https://example.com",
        protocol="openai",
        api_key="test-key",
        target_model="target-model",
        priority=0,
        weight=1,
    )
    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
    )
    service.log_repo.create_initial.return_value = 43
    service._resolve_candidates = AsyncMock(  # type: ignore[method-assign]
        return_value=(mapping, [candidate], 0, "openai", {})
    )
    client = AsyncMock()
    client.forward.return_value = ProviderResponse(
        status_code=503,
        error="upstream unavailable",
    )

    with (
        patch(
            "app.services.retry_handler.get_settings",
            return_value=RetrySettings(),
        ),
        patch(
            "app.services.proxy_service.convert_request_for_supplier",
            return_value=("/v1/chat/completions", {"model": "target-model"}),
        ),
        patch(
            "app.services.proxy_service.get_provider_client",
            return_value=client,
        ),
    ):
        response, _ = await service.process_request(
            api_key_id=1,
            api_key_name="key",
            request_protocol="openai",
            path="/v1/chat/completions",
            request_url="/v1/chat/completions",
            method="POST",
            headers={},
            body={"model": "test-model", "messages": []},
        )

    assert response.status_code == 503
    service.log_repo.update.assert_awaited_once()
    log_id, log_data = service.log_repo.update.await_args.args
    assert log_id == 43
    assert log_data.is_completed is True
    assert log_data.response_status == 503
    assert log_data.error_info == "upstream unavailable"
    assert await active_requests.is_active(43) is False
