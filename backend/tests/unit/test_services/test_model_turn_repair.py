import copy
import json
from dataclasses import replace

import pytest
import httpx

from app.providers.base import ProviderResponse
from app.providers.openai_client import OpenAIClient
from app.rules.models import CandidateProvider
from app.services.model_turn_repair import (
    ModelTurnRepair,
    append_user_turn,
    is_model_turn_error,
)
from app.services.retry_handler import RetryHandler
from app.services.strategy import PriorityStrategy


ERROR = "Requests ending with a model turn are not supported."


def candidate(provider_id=1):
    return CandidateProvider(
        provider_id=provider_id,
        provider_name="test",
        base_url="https://example.com",
        api_key="test",
        protocol="openai",
        target_model="writer",
        priority=provider_id,
    )


@pytest.mark.parametrize(
    "body",
    [
        ERROR,
        ERROR.encode(),
        {"error": {"message": ERROR}},
        json.dumps({"error": {"message": ERROR}}).encode(),
        {"error": {"metadata": {"raw": json.dumps({"error": {"message": ERROR}})}}},
        {"message": "MODEL  TURN rejected: requests ENDING\nWITH this role"},
        json.dumps(json.dumps({"error": ERROR})),
    ],
)
def test_error_formats(body):
    assert is_model_turn_error(ProviderResponse(status_code=400, body=body))


@pytest.mark.parametrize(
    "response",
    [
        ProviderResponse(status_code=500, error=ERROR),
        ProviderResponse(status_code=200, body=ERROR),
        ProviderResponse(
            status_code=400, body={"error": {"message": "INVALID_ARGUMENT"}}
        ),
        ProviderResponse(status_code=400, body={"request": {"message": ERROR}}),
        ProviderResponse(
            status_code=400,
            body={"error": {"metadata": {"previous_errors": [{"message": ERROR}]}}},
        ),
        ProviderResponse(
            status_code=400,
            body={
                "error": {"message": "model turn", "metadata": {"raw": "ending with"}}
            },
        ),
        ProviderResponse(
            status_code=400, body={"error": "model turn"}, error="ending with"
        ),
        ProviderResponse(status_code=400, body=[ERROR]),
        ProviderResponse(status_code=400, body=42),
        ProviderResponse(status_code=400, body=b"\xff"),
    ],
)
def test_nonmatching_errors(response):
    assert not is_model_turn_error(response)


def test_error_field_and_depth_limit():
    assert is_model_turn_error(ProviderResponse(status_code=400, error=ERROR))
    nested = ERROR
    for _ in range(20):
        nested = {"error": nested}
    assert not is_model_turn_error(ProviderResponse(status_code=400, body=nested))


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"messages": []},
        {"messages": "invalid"},
        {"messages": [None]},
        {"messages": [{"role": "user", "content": "hello"}]},
        {"messages": [{"role": "assistant", "tool_calls": [{"id": "call_1"}]}]},
        {"messages": [{"role": "assistant", "tool_calls": [None]}]},
        {"messages": [{"role": "assistant", "tool_calls": 1}]},
        {"messages": [{"role": "assistant", "function_call": {"name": "lookup"}}]},
        {"messages": [{"role": "assistant", "function_call": "invalid"}]},
        {"messages": [{"role": "assistant", "content": [None]}]},
        {
            "messages": [
                {"role": "assistant", "content": [{"type": "tool_use", "id": "c1"}]}
            ]
        },
        {"messages": [{"role": "assistant", "content": [{"type": "tool_use"}]}]},
        {
            "contents": [
                {"role": "model", "parts": [{"functionCall": {"name": "lookup"}}]}
            ]
        },
        {"contents": [{"role": "model", "parts": [{"functionCall": None}]}]},
        {
            "messages": [
                {"role": "assistant", "tool_calls": [{"id": "missing"}]},
                {"role": "assistant", "content": "continue"},
            ]
        },
    ],
)
def test_unrepairable_requests(body):
    assert append_user_turn(body) is None


@pytest.mark.parametrize(
    "history",
    [
        [{"role": "user", "content": "hello"}],
        [
            {"role": "assistant", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "tool_call_id": "c1", "content": "ok"},
        ],
        [
            {"role": "assistant", "function_call": {"name": "lookup"}},
            {"role": "function", "name": "lookup", "content": "ok"},
        ],
        [
            {"role": "assistant", "content": [{"type": "tool_use", "id": "c1"}]},
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "c1", "content": "ok"}
                ],
            },
        ],
    ],
)
def test_append_preserves_messages_and_fields(history):
    body = {
        "model": "writer",
        "messages": history
        + [{"role": "assistant", "content": None, "reasoning": "thinking"}],
        "tools": [{"name": "lookup"}],
    }
    original = copy.deepcopy(body)
    repaired = append_user_turn(body)
    assert body == original
    assert repaired["messages"][:-1] == original["messages"]
    assert repaired["messages"][-1] == {"role": "user", "content": "Please continue."}
    repaired["tools"][0]["name"] = "changed"
    assert body == original


def test_native_gemini_tool_results_and_signatures():
    body = {
        "contents": [
            {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {"name": "lookup"},
                        "thoughtSignature": "signature",
                    }
                ],
            },
            {
                "role": "user",
                "parts": [
                    {"functionResponse": {"name": "lookup", "response": {"ok": True}}}
                ],
            },
            {"role": "model", "parts": [{"text": "thinking", "thought": True}]},
        ]
    }
    repaired = append_user_turn(body)
    assert repaired["contents"][:-1] == body["contents"]
    assert repaired["contents"][-1] == {
        "role": "user",
        "parts": [{"text": "Please continue."}],
    }


def test_state_isolation_and_single_repair():
    state = ModelTurnRepair()
    first = candidate()
    second = replace(first, target_model="other-model")
    body = {"messages": [{"role": "assistant", "content": "partial"}]}
    error = ProviderResponse(status_code=400, error=ERROR)
    assert not state.try_repair(first, error)
    assert state.prepare(first, body) == body
    assert not state.try_repair(first, ProviderResponse(status_code=400, error="bad"))
    assert state.try_repair(first, error)
    assert not state.try_repair(first, error)
    assert len(state.prepare(first, body)["messages"]) == 2
    assert state.prepare(second, body) == body
    assert state.prepare(replace(first, provider_mapping_id=99), body) == body
    assert ModelTurnRepair().prepare(first, body) == body


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("repair_succeeds", [False, True])
async def test_retry_records_attempts_and_closes_failed_stream(stream, repair_succeeds):
    handler = RetryHandler(PriorityStrategy())
    handler.max_retries = (
        1  # Corrective attempt is independent of server-error retries.
    )
    state = ModelTurnRepair()
    bodies, failures, closed = [], [], []
    providers = [candidate(), candidate(2)]

    def response_for(provider):
        prepared = state.prepare(
            provider, {"messages": [{"role": "assistant", "content": "partial"}]}
        )
        bodies.append((provider.provider_id, copy.deepcopy(prepared)))
        if stream and len(bodies) > 1:
            assert len(closed) == len(bodies) - 1
        if provider.provider_id == 2 or (repair_succeeds and len(bodies) == 2):
            return ProviderResponse(status_code=200, body={"ok": True})
        return ProviderResponse(status_code=400, error=ERROR)

    async def forward(provider):
        return response_for(provider)

    async def forward_stream(provider):
        response = response_for(provider)
        try:
            yield b"ok" if response.is_success else b"failure", response
        finally:
            closed.append(provider.provider_id)

    async def log_failure(attempt):
        failures.append((attempt.attempt_index, copy.deepcopy(bodies[-1])))

    kwargs = dict(on_failure_attempt=log_failure, repair_request=state.try_repair)
    if stream:
        output = [
            item
            async for item in handler.execute_with_retry_stream(
                providers, "writer", forward_stream, **kwargs
            )
        ]
        assert len(output) == 1
        assert output[0][0] == b"ok"
        retry_count = output[0][3]
    else:
        result = await handler.execute_with_retry(
            providers, "writer", forward, **kwargs
        )
        assert result.success
        assert len(result.attempts) == (2 if repair_succeeds else 3)
        retry_count = result.retry_count
    assert retry_count == (1 if repair_succeeds else 2)
    assert [provider for provider, _ in bodies] == (
        [1, 1] if repair_succeeds else [1, 1, 2]
    )
    assert [len(body["messages"]) for _, body in bodies] == (
        [1, 2] if repair_succeeds else [1, 2, 1]
    )
    assert [index for index, _ in failures] == ([0] if repair_succeeds else [0, 1])


@pytest.mark.asyncio
async def test_stream_exception_after_output_never_replays():
    handler = RetryHandler(PriorityStrategy())
    calls = []

    async def forward(provider):
        calls.append(provider.provider_id)
        yield b"first", ProviderResponse(status_code=200)
        raise RuntimeError("stream interrupted")

    def repair(*_):
        pytest.fail("Cannot repair after output starts")

    output = handler.execute_with_retry_stream(
        [candidate(), candidate(2)], "writer", forward, repair_request=repair
    )
    assert (await anext(output))[0] == b"first"
    with pytest.raises(RuntimeError, match="stream interrupted"):
        await anext(output)
    assert calls == [1]


@pytest.mark.parametrize(
    "result",
    [
        {"role": "assistant", "tool_call_id": "lookup", "content": "Not a tool result"},
        {"role": "function", "name": "lookup", "content": "Wrong call format"},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "lookup"}]},
    ],
)
def test_tool_result_must_match_role_and_call_format(result):
    body = {
        "messages": [
            {"role": "assistant", "tool_calls": [{"id": "lookup"}]},
            result,
            {"role": "assistant", "content": "Continue"},
        ]
    }
    assert append_user_turn(body) is None


def test_anthropic_tool_result_in_assistant_turn_does_not_resolve_call():
    body = {
        "messages": [
            {"role": "assistant", "content": [{"type": "tool_use", "id": "c1"}]},
            {
                "role": "assistant",
                "content": [{"type": "tool_result", "tool_use_id": "c1"}],
            },
        ]
    }
    assert append_user_turn(body) is None


@pytest.mark.parametrize(
    "result_ids,repairable", [(["a", "b"], True), (["a", "a"], False)]
)
def test_native_parallel_calls_match_ids_not_just_names(result_ids, repairable):
    body = {
        "contents": [
            {
                "role": "model",
                "parts": [
                    {"functionCall": {"id": identifier, "name": "lookup"}}
                    for identifier in ["a", "b"]
                ],
            },
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": identifier,
                            "name": "lookup",
                            "response": {},
                        }
                    }
                    for identifier in result_ids
                ],
            },
            {"role": "model", "parts": [{"text": "Continue"}]},
        ]
    }
    assert (append_user_turn(body) is not None) == repairable


@pytest.mark.asyncio
@pytest.mark.parametrize("repair_enabled", [False, True])
async def test_stream_cleanup_error_preserves_upstream_error_and_retry_policy(
    repair_enabled,
):
    handler = RetryHandler(PriorityStrategy())
    handler.retry_delay_ms = 0
    state = ModelTurnRepair()
    calls, failures = [], []

    async def forward(provider):
        body = state.prepare(
            provider, {"messages": [{"role": "assistant", "content": "partial"}]}
        )
        calls.append((provider.provider_id, len(body["messages"])))
        response = ProviderResponse(status_code=400, body={"error": {"message": ERROR}})
        try:
            yield b"original error", response
        finally:
            raise RuntimeError("connection close failed")

    async def log_failure(attempt):
        failures.append(attempt.response.status_code)

    results = [
        item
        async for item in handler.execute_with_retry_stream(
            [candidate()],
            "writer",
            forward,
            on_failure_attempt=log_failure,
            repair_request=state.try_repair if repair_enabled else None,
        )
    ]
    assert calls == ([(1, 1), (1, 2)] if repair_enabled else [(1, 1)])
    assert failures == ([400, 400] if repair_enabled else [400])
    assert results[-1][1].status_code == 400
    assert results[-1][0] == b"original error"


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_real_openai_client_recovers_openrouter_error(monkeypatch, stream):
    """Exercise actual HTTP error decoding and SSE forwarding, not a fake client."""
    requests = []

    def transport(request):
        body = json.loads(request.content)
        requests.append(body)
        if len(requests) == 1:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Provider returned error",
                        "metadata": {
                            "raw": json.dumps({"error": {"message": ERROR}}),
                        },
                    }
                },
            )
        assert body["messages"][-1] == {"role": "user", "content": "Please continue."}
        if stream:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"choices":[]}\n\ndata: [DONE]\n\n',
            )
        return httpx.Response(200, json={"choices": []})

    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(transport), **kwargs
        ),
    )
    client = OpenAIClient()
    state = ModelTurnRepair()
    handler = RetryHandler(PriorityStrategy())
    original = {
        "messages": [{"role": "assistant", "content": None, "reasoning": "thinking"}],
        "stream": stream,
    }

    def forward(provider):
        kwargs = dict(
            base_url=provider.base_url,
            api_key=provider.api_key,
            path="/v1/chat/completions",
            method="POST",
            headers={},
            target_model=provider.target_model,
            body=state.prepare(provider, original),
        )
        if stream:
            return client.forward_stream(**kwargs)
        return client.forward(**kwargs, response_mode="raw")

    if stream:
        result = [
            item
            async for item in handler.execute_with_retry_stream(
                [candidate()], "writer", forward, repair_request=state.try_repair
            )
        ]
        assert all(item[1].status_code == 200 for item in result)
        assert b"[DONE]" in b"".join(item[0] for item in result)
    else:
        result = await handler.execute_with_retry(
            [candidate()], "writer", forward, repair_request=state.try_repair
        )
        assert result.success
        assert json.loads(result.response.body) == {"choices": []}
    assert len(requests) == 2
    assert len(original["messages"]) == 1
