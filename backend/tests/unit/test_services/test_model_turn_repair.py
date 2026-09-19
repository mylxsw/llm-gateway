import copy
import json
from dataclasses import replace

import pytest

from app.providers.base import ProviderResponse
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
