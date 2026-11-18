import copy
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.model_turn_repair import ModelTurnRepair
from app.services.tool_reasoning_recovery import ToolReasoningRecovery, is_tool_reasoning_error
from app.services.retry_handler import RetryHandler
from app.services.strategy import PriorityStrategy

ERROR = ("Function tools with reasoning_effort are not supported for gpt-6.1-sol "
         "in /v1/chat/completions. To use function tools, use /v1/responses "
         "or set reasoning_effort to 'none'.")
BODY = {"model": "test", "messages": [{"role": "user", "content": "hi"}],
        "reasoning_effort": "high", "tools": [{"type": "function", "function": {
            "name": "lookup", "parameters": {"type": "object", "properties": {}}}}]}


def candidate(index=1):
    return CandidateProvider(provider_id=index, provider_name="test", base_url="https://test/v1",
                            protocol="openai", api_key=None, target_model="test", priority=1)


@pytest.mark.parametrize("form", ["dict", "str", "bytes", "nested", "escaped"])
def test_error_formats(form):
    value = {"error": {"message": ERROR}}
    if form == "escaped":
        value["error"]["message"] = ERROR.upper().replace("_", "\\_")
    elif form == "nested":
        value = {"error": {"metadata": {"raw": json.dumps(value)}}}
    elif form in ("str", "bytes"):
        value = json.dumps(value)
        if form == "bytes":
            value = value.encode()
    assert is_tool_reasoning_error(ProviderResponse(status_code=400, body=value))


@pytest.mark.parametrize("body,status", [
    ({"request": {"message": ERROR}}, 400),
    ({"previous_errors": [{"message": ERROR}]}, 400),
    ({"error": {"message": ERROR}}, 500),
    ({"error": {"message": "reasoning_effort is invalid"}}, 400),
    ({"error": {"message": "function tools are not supported"}}, 400),
    (None, 400),
])
def test_rejects_unrelated_errors(body, status):
    assert not is_tool_reasoning_error(ProviderResponse(status_code=status, body=body))


@pytest.mark.parametrize("no_suffix", [False, True])
def test_bounded_recovery_and_isolation(no_suffix):
    recovery = ToolReasoningRecovery()
    first, other = candidate(), candidate(2)
    original = copy.deepcopy(BODY)
    recovery.prepare(first, "/v1/chat/completions", BODY, "openai", no_suffix=no_suffix)
    error = ProviderResponse(status_code=400, body={"error": {"message": ERROR}})
    assert not recovery.try_repair(other, error)
    assert recovery.try_repair(first, error)
    if not no_suffix:
        path, body, protocol = recovery.prepare(first, "/v1/chat/completions", BODY, "openai")
        assert path == "/v1/responses" and protocol == "openai_responses"
        assert body["reasoning"]["effort"] == "high"
        assert body["tools"][0]["name"] == "lookup"
        assert recovery.try_repair(first, ProviderResponse(status_code=502, error="connection failed"))
    path, body, protocol = recovery.prepare(first, "/v1/chat/completions", BODY, "openai")
    assert path == ("" if no_suffix else "/v1/chat/completions")
    assert body["reasoning_effort"] == "none" and protocol == "openai"
    assert not recovery.try_repair(first, error)
    assert not recovery.try_repair(first, ProviderResponse(status_code=200))
    assert BODY == original


@pytest.mark.parametrize("path,protocol,tools", [
    ("/v1/responses", "openai_responses", BODY["tools"]),
    ("/v1/embeddings", "openai", BODY["tools"]),
    ("/v1/chat/completions", "openai", []),
    ("/v1/chat/completions", "openai", [{"type": "web_search"}]),
    ("/v1/chat/completions", "openai", None),
])
def test_only_function_chat_requests_are_eligible(path, protocol, tools):
    recovery = ToolReasoningRecovery()
    provider = candidate()
    recovery.prepare(provider, path, {**BODY, "tools": tools}, protocol)
    assert not recovery.try_repair(provider, ProviderResponse(status_code=400, error=ERROR))


def test_conversion_failure_advances_and_model_repair_is_preserved():
    recovery = ToolReasoningRecovery()
    provider = candidate()
    model_repair = ModelTurnRepair()
    callback = recovery.repair(model_repair)
    with patch.object(model_repair, "try_repair", return_value=True) as repair:
        assert callback(provider, ProviderResponse(status_code=400, error="model turn"))
        repair.assert_called_once()
    recovery.prepare(provider, "/v1/chat/completions", BODY, "openai")
    assert callback(provider, ProviderResponse(status_code=400, error=ERROR))
    assert recovery.protocol(provider, "openai") == "openai_responses"
    with patch("app.services.tool_reasoning_recovery.convert_request_for_supplier", side_effect=ValueError("unsupported")):
        with pytest.raises(ValueError):
            recovery.prepare(provider, "/v1/chat/completions", BODY, "openai")
    assert callback(provider, ProviderResponse(status_code=400, error="unsupported"))
    assert recovery.protocol(provider, "openai") == "openai"
    assert not callback(provider, ProviderResponse(status_code=400, error=ERROR))


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_retry_handler_enforces_repair_budget(stream):
    handler = RetryHandler(PriorityStrategy())
    handler.max_retries = 1
    repair = Mock(return_value=True)
    error = ProviderResponse(status_code=400, error=ERROR)
    forward = AsyncMock(return_value=error)
    closed = []

    async def forward_stream(provider):
        result = await forward(provider)
        try:
            yield b"error", result
        finally:
            closed.append(True)

    kwargs = dict(candidates=[candidate()], requested_model="test",
                  repair_request=repair, max_repair_attempts=2)
    if stream:
        output = [item async for item in handler.execute_with_retry_stream(
            **kwargs, forward_stream_fn=forward_stream)]
        assert output[-1][1].status_code == 400
        assert len(closed) == 3
    else:
        result = await handler.execute_with_retry(**kwargs, forward_fn=forward)
        assert not result.success
    assert forward.await_count == 3
    assert repair.call_count == 2


@pytest.mark.asyncio
async def test_stream_never_replays_after_successful_output():
    handler = RetryHandler(PriorityStrategy())
    repair = Mock(return_value=True)
    calls = []

    async def forward_stream(provider):
        calls.append(provider)
        yield b"data: hello\n\n", ProviderResponse(status_code=200)
        yield b"", ProviderResponse(status_code=400, error=ERROR)

    chunks = [item async for item in handler.execute_with_retry_stream(
        candidates=[candidate(), candidate(2)], requested_model="test",
        forward_stream_fn=forward_stream, repair_request=repair, max_repair_attempts=2)]
    assert chunks[0][0] == b"data: hello\n\n"
    assert len(calls) == 1
    repair.assert_not_called()
