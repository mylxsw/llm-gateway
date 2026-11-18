import copy
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.common.time import utc_now
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.proxy_service import ProxyService
from tests.unit.test_services.test_tool_reasoning_recovery import BODY, ERROR


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("scenario", ["responses", "none", "failover", "unrelated", "success", "no_suffix", "conversion_error", "timeout", "model_turn"])
async def test_proxy_recovery_chain(stream, scenario):
    now = utc_now()
    mapping = ModelMapping(requested_model="test", strategy="priority", matching_rules=None,
                           capabilities=None, is_active=True, created_at=now, updated_at=now)
    candidates = [CandidateProvider(provider_id=i, provider_name=name, base_url="https://example.com/v1",
                                   protocol="openai", api_key="key", target_model=name, priority=i,
                                   provider_options={"no_suffix": True} if scenario == "no_suffix" else None)
                  for i, name in enumerate(("first", "fallback"), 1)]
    service = ProxyService(model_repo=AsyncMock(), provider_repo=AsyncMock(), log_repo=AsyncMock())
    service._resolve_candidates = AsyncMock(return_value=(mapping, candidates, 0, "openai", {}))
    body = {**copy.deepcopy(BODY), "stream": stream}
    if scenario == "model_turn":
        body["messages"].append({"role": "assistant", "content": "thinking"})
    original = copy.deepcopy(body)
    calls, closed = [], []
    success = {"id": "ok", "object": "chat.completion", "choices": [{"index": 0,
               "message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
               "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}}
    responses_success = {"id": "resp_ok", "object": "response", "status": "completed", "model": "first",
                         "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "hello"}]}],
                         "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}}

    def response(kwargs):
        if stream:
            assert len(closed) == len(calls)
        calls.append(copy.deepcopy(kwargs))
        is_responses = kwargs["path"] == "/v1/responses"
        is_none = kwargs["body"].get("reasoning_effort") == "none"
        ok = (scenario == "success" or kwargs["target_model"] == "fallback"
              or (scenario == "responses" and is_responses)
              or (scenario in ("none", "no_suffix", "conversion_error", "timeout", "model_turn") and is_none))
        if ok:
            return ProviderResponse(status_code=200, body=responses_success if is_responses else json.dumps(success).encode())
        if is_responses and scenario == "timeout":
            return ProviderResponse(status_code=504, error="Request timeout", interrupted=True)
        error = "invalid tools" if scenario == "unrelated" else ERROR
        if scenario == "model_turn" and len(calls) == 1:
            error = "Requests ending with a model turn are not supported."
        return ProviderResponse(status_code=404 if is_responses else 400,
                                body=json.dumps({"error": {"message": error}}).encode())

    async def forward(**kwargs):
        return response(kwargs)

    async def forward_stream(**kwargs):
        result = response(kwargs)
        try:
            if not result.is_success:
                yield result.body or b"", result
            elif kwargs["path"] == "/v1/responses":
                yield b'data: {"type":"response.output_text.delta","delta":"hello"}\n\n', result
                yield ('data: ' + json.dumps({"type": "response.completed", "response": responses_success}) + '\n\n').encode(), result
            else:
                yield b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n', result
                yield b'data: [DONE]\n\n', result
        finally:
            closed.append(kwargs["path"])

    client = AsyncMock()
    client.forward = AsyncMock(side_effect=forward)
    client.forward_stream = forward_stream
    request = dict(api_key_id=1, api_key_name="test", request_protocol="openai", path="/v1/chat/completions",
                   request_url="/v1/chat/completions", method="POST", headers={}, body=body)
    from app.services.tool_reasoning_recovery import convert_request_for_supplier
    with patch("app.services.proxy_service.get_provider_client", return_value=client), patch(
        "app.services.tool_reasoning_recovery.convert_request_for_supplier",
        side_effect=ValueError("cannot convert") if scenario == "conversion_error" else convert_request_for_supplier,
    ):
        if stream:
            result, output, metadata = await service.process_request_stream(**request)
            output = b"".join([chunk async for chunk in output])
            assert b"hello" in output and ERROR.encode() not in output
            assert b"response.output_text.delta" not in output
            assert len(closed) == len(calls)
        else:
            result, metadata = await service.process_request(**request)
            value = json.loads(result.body) if isinstance(result.body, bytes) else result.body
            assert value["choices"][0]["message"]["content"] == "hello"
            assert value["usage"]["total_tokens"] == 5
    assert result.status_code == 200
    assert body == original
    expected_paths = {
        "responses": ["/v1/chat/completions", "/v1/responses"],
        "none": ["/v1/chat/completions", "/v1/responses", "/v1/chat/completions"],
        "failover": ["/v1/chat/completions", "/v1/responses", "/v1/chat/completions", "/v1/chat/completions"],
        "unrelated": ["/v1/chat/completions", "/v1/chat/completions"],
        "success": ["/v1/chat/completions"],
        "no_suffix": ["", ""],
        "conversion_error": ["/v1/chat/completions", "/v1/chat/completions"],
        "timeout": ["/v1/chat/completions", "/v1/responses", "/v1/chat/completions"],
        "model_turn": ["/v1/chat/completions", "/v1/chat/completions", "/v1/responses", "/v1/chat/completions"],
    }[scenario]
    assert [call["path"] for call in calls] == expected_paths
    if scenario in ("none", "no_suffix", "conversion_error", "timeout", "model_turn"):
        assert calls[-1]["body"]["reasoning_effort"] == "none"
    if scenario == "failover":
        assert calls[-1]["body"]["reasoning_effort"] == "high"
    expected_attempts = len(calls) + (scenario == "conversion_error")
    assert metadata["retry_count"] == expected_attempts - 1
    failed_logs = [call.args[0] for call in service.log_repo.create.await_args_list]
    assert len(failed_logs) == expected_attempts - 1
    if scenario in ("none", "failover", "timeout", "conversion_error"):
        assert failed_logs[1].supplier_protocol == "openai_responses"
        assert failed_logs[1].upstream_url.endswith("/responses")
    final_log = service.log_repo.update.await_args.args[1]
    assert final_log.supplier_protocol == ("openai_responses" if scenario == "responses" else "openai")
