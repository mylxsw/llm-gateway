import copy
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.common.time import utc_now
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.proxy_service import ProxyService


ERROR = "Requests ending with a model turn are not supported."


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    "scenario,expected_calls",
    [
        ("repair", ["first", "first"]),
        ("repair_fails", ["first", "first", "fallback"]),
        ("other_error", ["first", "fallback"]),
        ("pending_tool", ["first", "fallback"]),
        ("user_tail", ["first", "fallback"]),
        ("success", ["first"]),
    ],
)
async def test_proxy_repairs_converted_body_and_logs_each_attempt(
    stream, scenario, expected_calls
):
    now = utc_now()
    mapping = ModelMapping(
        requested_model="writer",
        strategy="priority",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    candidates = [
        CandidateProvider(
            provider_id=index,
            provider_name=name,
            base_url="https://example.com",
            protocol="openai",
            api_key="test",
            target_model=name,
            priority=index,
        )
        for index, name in enumerate(("first", "fallback"), 1)
    ]
    service = ProxyService(
        model_repo=AsyncMock(), provider_repo=AsyncMock(), log_repo=AsyncMock()
    )
    service._resolve_candidates = AsyncMock(
        return_value=(mapping, candidates, 0, "openai", {})
    )
    tail = {"role": "assistant", "content": None, "reasoning": "Keep the constraints."}
    if scenario == "pending_tool":
        tail["tool_calls"] = [
            {
                "id": "c2",
                "type": "function",
                "function": {"name": "validate", "arguments": "{}"},
            }
        ]
    elif scenario == "user_tail":
        tail = {"role": "user", "content": "Please continue."}
    body = {
        "model": "writer",
        "stream": stream,
        "messages": [
            {"role": "user", "content": "Create a cover"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "inspect", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "Constraints"},
            tail,
        ],
    }
    original = copy.deepcopy(body)
    calls, closed = [], []
    error_body = json.dumps(
        {
            "error": {
                "message": "Provider returned error",
                "metadata": {
                    "raw": json.dumps(
                        {
                            "error": {
                                "message": ERROR
                                if scenario != "other_error"
                                else "Invalid tools"
                            }
                        }
                    ),
                },
            }
        }
    ).encode()
    success_body = b'{"id":"ok","choices":[],"usage":{"completion_tokens":2}}'

    def response(kwargs):
        if stream and calls:
            assert len(closed) == len(calls)
        calls.append(copy.deepcopy(kwargs))
        success = (
            scenario == "success"
            or kwargs["target_model"] == "fallback"
            or (scenario == "repair" and len(calls) == 2)
        )
        return ProviderResponse(
            status_code=200 if success else 400,
            headers={
                "content-type": "text/event-stream"
                if stream and success
                else "application/json"
            },
            body=success_body if success else error_body,
        )

    async def forward(**kwargs):
        return response(kwargs)

    async def forward_stream(**kwargs):
        upstream_response = response(kwargs)
        try:
            yield (
                (
                    b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                    if upstream_response.is_success
                    else error_body
                ),
                upstream_response,
            )
            if upstream_response.is_success:
                yield b"data: [DONE]\n\n", upstream_response
        finally:
            closed.append(kwargs["target_model"])

    client = AsyncMock()
    client.forward = AsyncMock(side_effect=forward)
    client.forward_stream = forward_stream
    request = dict(
        api_key_id=1,
        api_key_name="test",
        request_protocol="openai",
        path="/v1/chat/completions",
        request_url="/v1/chat/completions",
        method="POST",
        headers={},
        body=body,
    )
    with patch("app.services.proxy_service.get_provider_client", return_value=client):
        if stream:
            result, output, metadata = await service.process_request_stream(**request)
            chunks = [chunk async for chunk in output]
            assert b"Provider returned error" not in b"".join(chunks)
            assert b"ok" in b"".join(chunks)
        else:
            result, metadata = await service.process_request(**request)
            assert result.body == success_body
    assert result.status_code == 200
    assert [call["target_model"] for call in calls] == expected_calls
    assert body == original
    assert metadata["retry_count"] == len(expected_calls) - 1
    for index, call in enumerate(calls):
        repaired = index == 1 and scenario in ("repair", "repair_fails")
        expected = original["messages"] + (
            [{"role": "user", "content": "Please continue."}] if repaired else []
        )
        assert call["body"]["messages"] == expected
    final_log = service.log_repo.update.await_args.args[1]
    assert final_log.converted_request_body == calls[-1]["body"]
    assert final_log.request_body == original
    failure_logs = [call.args[0] for call in service.log_repo.create.await_args_list]
    assert len(failure_logs) == len(calls) - 1
    for index, log in enumerate(failure_logs):
        assert log.converted_request_body == calls[index]["body"]
