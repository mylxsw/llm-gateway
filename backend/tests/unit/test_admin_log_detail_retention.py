import json
from datetime import datetime, timezone

import pytest
from starlette.requests import Request

from app.api.admin.logs import get_log, retry_log
from app.domain.log import RequestLogModel


def _make_log(detail_available: bool) -> RequestLogModel:
    return RequestLogModel(
        id=1,
        request_time=datetime.now(timezone.utc),
        api_key_id=123,
        api_key_name="test-key",
        requested_model="gpt-4",
        target_model="gpt-4",
        provider_id=1,
        provider_name="OpenAI",
        retry_count=0,
        matched_provider_count=1,
        first_byte_delay_ms=100,
        total_time_ms=500,
        input_tokens=10,
        output_tokens=20,
        total_cost=0.1,
        input_cost=0.04,
        output_cost=0.06,
        response_status=200,
        trace_id="trace-1",
        is_stream=False,
        request_path="/v1/chat/completions",
        request_method="POST",
        request_headers=None,
        response_headers=None,
        request_body=None,
        response_body=None,
        detail_available=detail_available,
    )


class _StubLogService:
    def __init__(self, log: RequestLogModel):
        self.log = log

    async def get_by_id(self, _: int) -> RequestLogModel:
        return self.log


class _UnusedApiKeyService:
    async def get_raw_key_value(self, _: int) -> str:
        raise AssertionError("get_raw_key_value should not be called when detail is expired")


@pytest.mark.asyncio
async def test_get_log_returns_detail_available_false_when_detail_expired():
    log = _make_log(detail_available=False)
    response = await get_log(1, _StubLogService(log))

    assert response.detail_available is False
    assert response.request_body is None
    assert response.response_body is None


@pytest.mark.asyncio
async def test_retry_log_rejects_when_detail_expired():
    log = _make_log(detail_available=False)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/admin/logs/1/retry",
            "headers": [],
            "app": object(),
        }
    )

    response = await retry_log(
        1,
        request,
        _StubLogService(log),
        _UnusedApiKeyService(),
    )

    assert response.status_code == 422
    payload = json.loads(response.body)
    assert payload["error"]["code"] == "retry_log_detail_expired"
