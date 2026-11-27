import copy
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.common.time import utc_now
from app.domain.log import RequestLogModel
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.proxy_service import ProxyService

SCHEMA = {
    "type": "object",
    "properties": {
        "translation": {"type": "string"},
        "kind": {"enum": ["word", "text"]},
    },
    "required": ["translation", "kind"],
    "additionalProperties": False,
}
CARD = {"translation": "investment expert", "kind": "word"}
DEEPSEEK_ERROR = "This response_format type is unavailable now (request_id: test)"


def make_proxy(candidates, protocol="openai"):
    now = utc_now()
    mapping = ModelMapping(
        requested_model="dictionary",
        strategy="priority",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    proxy = ProxyService(
        model_repo=AsyncMock(), provider_repo=AsyncMock(), log_repo=AsyncMock()
    )
    proxy._resolve_candidates = AsyncMock(
        return_value=(mapping, candidates, 0, protocol, {})
    )
    return proxy


def candidate(name, protocol, index=1):
    return CandidateProvider(
        provider_id=index,
        provider_name=name,
        base_url="https://example.com",
        protocol=protocol,
        api_key="test",
        target_model=name,
        priority=index,
    )


def request_body(kind, stream, strict=True):
    body = {
        "model": "dictionary",
        "messages": [{"role": "user", "content": "投资专家"}],
        "stream": stream,
    }
    if kind is not None:
        body["response_format"] = {"type": kind}
    if kind == "json_schema":
        body["response_format"]["json_schema"] = {
            "name": "word_card",
            "schema": SCHEMA,
            "strict": strict,
        }
    return body


def upstream_error(message, status=400):
    error = json.dumps({"error": {"message": message}}).encode()
    return ProviderResponse(status_code=status, body=error)


def chat_success(content):
    return {
        "id": "chatcmpl_test",
        "model": "dictionary",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 6, "total_tokens": 16},
    }


async def run_proxy(proxy, body, forward, protocol="openai"):
    stream_closed = []

    async def forward_stream(**kwargs):
        try:
            outcome = forward(**kwargs)
            if not outcome.is_success:
                yield outcome.body or b"", outcome
                return
            data = (
                json.loads(outcome.body)
                if isinstance(outcome.body, bytes)
                else outcome.body
            )
            choice = data["choices"][0]
            content = choice["message"]["content"]
            for part in (content[:6], content[6:]):
                event = {"choices": [{"index": 0, "delta": {"content": part}}]}
                yield ("data: " + json.dumps(event) + "\n\n").encode(), outcome
            yield (
                b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
                outcome,
            )
            yield b"data: [DONE]\n\n", outcome
        finally:
            stream_closed.append(kwargs["target_model"])

    path = "/v1/responses" if protocol == "openai_responses" else "/v1/chat/completions"
    with patch("app.services.proxy_service.get_provider_client") as get_client:
        get_client.return_value.forward = AsyncMock(side_effect=forward)
        get_client.return_value.forward_stream = forward_stream
        request = {
            "api_key_id": 1,
            "api_key_name": "test",
            "request_protocol": protocol,
            "path": path,
            "request_url": path,
            "method": "POST",
            "headers": {},
            "body": body,
        }
        if body["stream"]:
            response, chunks, metadata = await proxy.process_request_stream(**request)
            output = b"".join([chunk async for chunk in chunks])
        else:
            response, metadata = await proxy.process_request(**request)
            output = (
                json.loads(response.body)
                if isinstance(response.body, bytes)
                else response.body
            )
    return response, output, metadata, stream_closed


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize(
    ("name", "protocol", "kind", "errors", "expected"),
    [
        (
            "deepseek-flash",
            "deepseek",
            "json_schema",
            [],
            ["json_object"],
        ),
        (
            "glm-5",
            "zhipu",
            "json_schema",
            [],
            ["json_object"],
        ),
        (
            "deepseek-flash",
            "openai",
            "json_schema",
            [DEEPSEEK_ERROR],
            ["json_schema", "json_object"],
        ),
        (
            "deepseek-flash",
            "deepseek",
            "json_schema",
            ["response_format.type must be one of text"],
            ["json_object", None],
        ),
        ("deepseek-flash", "deepseek", "json_object", [], ["json_object"]),
        ("glm-5", "zhipu", "text", [], ["text"]),
        ("deepseek-v4.1-flash", "aliyun", "json_schema", [], ["json_schema"]),
        (
            "qwen-thinking",
            "aliyun",
            "json_schema",
            [
                "Unknown format of response_format",
                "Json mode response is not supported when enable_thinking is true",
            ],
            ["json_schema", "json_object", None],
        ),
        (
            "claude-sonnet",
            "openai",
            "json_object",
            [
                "response_format accepts only json_schema with strict: true",
            ],
            ["json_object", None],
        ),
        (
            "claude-sonnet",
            "openai",
            "text",
            [
                "response_format accepts only json_schema with strict: true",
            ],
            ["text", None],
        ),
        (
            "claude-sonnet",
            "openai",
            "json_schema",
            [
                "response_format accepts only json_schema with strict: true",
            ],
            ["json_schema", "json_schema"],
        ),
        ("kimi", "moonshot", "json_schema", [], ["json_schema"]),
        ("doubao", "ark", "json_schema", [], ["json_schema"]),
        ("openai", "openai", "json_schema", [], ["json_schema"]),
        ("unstructured", "openai", None, [], [None]),
    ],
)
async def test_adapts_rejected_formats_before_any_output(
    stream, name, protocol, kind, errors, expected
):
    proxy = make_proxy([candidate(name, protocol)])
    body = request_body(kind, stream, strict=name != "claude-sonnet")
    original = copy.deepcopy(body)
    calls = []

    def forward(**kwargs):
        outbound = kwargs["body"]
        calls.append(outbound)
        if len(calls) <= len(errors):
            return upstream_error(errors[len(calls) - 1])
        return ProviderResponse(
            status_code=200, body=json.dumps(chat_success(json.dumps(CARD))).encode()
        )

    response, output, metadata, closed = await run_proxy(proxy, body, forward)
    assert response.status_code == 200
    assert metadata["retry_count"] == len(errors)
    assert [
        (call.get("response_format") or {}).get("type") for call in calls
    ] == expected
    assert body == original
    if stream:
        assert b"[DONE]" in output
        assert b"investment expert" in output
        assert len(closed) == len(calls)
    else:
        assert json.loads(output["choices"][0]["message"]["content"]) == CARD
    if kind == "json_schema":
        for outbound, mode in zip(calls, expected, strict=True):
            if mode != "json_schema":
                assert "JSON Schema" in outbound["messages"][0]["content"]
                assert "additionalProperties" in outbound["messages"][0]["content"]
        if errors and expected[-1] == "json_schema":
            assert calls[-1]["response_format"]["json_schema"]["strict"] is True
    assert calls[-1]["messages"][-1] == body["messages"][-1]


@pytest.mark.parametrize("sent_mode", ["json_schema", "json_object", None])
async def test_rebuild_preserves_the_chat_format_actually_sent(sent_mode):
    provider = candidate("deepseek-flash", "deepseek")
    proxy = make_proxy([provider])
    proxy.provider_repo.get_by_id.return_value = provider
    original = copy.deepcopy(request_body("json_schema", False))
    description = "Describe the original entry in detail. " * 100
    original["response_format"]["json_schema"]["schema"]["description"] = description
    sent_body = {"messages": [{"role": "system", "content": "...[truncated]"}]}
    if sent_mode is not None:
        sent_body["response_format"] = {"type": sent_mode}
    log = RequestLogModel(
        id=1,
        request_time=utc_now(),
        provider_id=provider.provider_id,
        request_protocol="openai",
        supplier_protocol="openai",
        request_path="/v1/chat/completions",
        target_model=provider.target_model,
        request_body=original,
        converted_request_body=sent_body,
    )

    rebuilt = (await proxy.rebuild_converted_request(log))["converted_request_body"]

    assert (rebuilt.get("response_format") or {}).get("type") == sent_mode
    if sent_mode == "json_schema":
        assert rebuilt["messages"] == original["messages"]
    else:
        assert description in rebuilt["messages"][0]["content"]
        assert rebuilt["messages"][1:] == original["messages"]


@pytest.mark.parametrize("stream", [False, True])
async def test_invalid_recovered_json_is_never_forwarded_to_client(stream):
    first = candidate("first", "openai")
    second = candidate("second", "openai", 2)
    proxy = make_proxy([first, second])
    body = request_body("json_schema", stream)
    calls = []

    def forward(**kwargs):
        model = kwargs["target_model"]
        kind = kwargs["body"]["response_format"]["type"]
        calls.append((model, kind))
        if model == "first" and kind == "json_schema":
            return upstream_error(DEEPSEEK_ERROR)
        content = (
            {"translation": "wrong", "kind": "invalid"} if model == "first" else CARD
        )
        return ProviderResponse(
            status_code=200, body=json.dumps(chat_success(json.dumps(content))).encode()
        )

    with patch("app.services.retry_handler.get_settings") as settings:
        settings.return_value.RETRY_MAX_ATTEMPTS = 1
        settings.return_value.RETRY_DELAY_MS = 0
        response, output, _, _ = await run_proxy(proxy, body, forward)
    assert response.status_code == 200
    assert calls == [
        ("first", "json_schema"),
        ("first", "json_object"),
        ("second", "json_schema"),
    ]
    if stream:
        assert b"wrong" not in output
    else:
        assert json.loads(output["choices"][0]["message"]["content"]) == CARD


@pytest.mark.parametrize("stream", [False, True])
async def test_unrelated_400_does_not_change_format(stream):
    proxy = make_proxy([candidate("provider", "openai")])
    calls = []

    def forward(**kwargs):
        calls.append(kwargs["body"])
        return upstream_error("messages.0.role is invalid")

    response, _, _, _ = await run_proxy(
        proxy, request_body("json_schema", stream), forward
    )
    assert response.status_code == 400
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("supplier_protocol", "error"),
    [
        (
            "anthropic",
            "output_config.format: structured outputs are not supported with this model",
        ),
        ("gemini", "generationConfig.responseSchema is not supported with this model"),
        (
            "openai_responses",
            "text.format: json_schema is not supported with this model",
        ),
    ],
)
async def test_recovery_for_other_upstream_protocols(supplier_protocol, error):
    proxy = make_proxy([candidate("provider", supplier_protocol)])
    calls = []

    def forward(**kwargs):
        calls.append(kwargs["body"])
        if len(calls) == 1:
            return upstream_error(error)
        content = json.dumps(CARD)
        if supplier_protocol == "anthropic":
            body = {
                "type": "message",
                "role": "assistant",
                "model": "provider",
                "content": [{"type": "text", "text": content}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 6, "output_tokens": 5},
            }
        elif supplier_protocol == "gemini":
            body = {
                "candidates": [
                    {
                        "content": {"role": "model", "parts": [{"text": content}]},
                        "finishReason": "STOP",
                    }
                ],
            }
        else:
            body = {
                "status": "completed",
                "model": "provider",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": content}],
                    },
                ],
            }
        return ProviderResponse(status_code=200, body=body)

    response, output, metadata, _ = await run_proxy(
        proxy, request_body("json_schema", False), forward
    )
    assert response.status_code == 200
    assert metadata["retry_count"] == 1
    assert json.loads(output["choices"][0]["message"]["content"]) == CARD
    first, second = calls
    if supplier_protocol == "anthropic":
        assert first["output_config"]["format"] == {
            "type": "json_schema",
            "schema": SCHEMA,
        }
        assert "output_config" not in second
        assert "JSON Schema" in second["system"][-1]["text"]
    elif supplier_protocol == "gemini":
        assert first["generationConfig"]["responseJsonSchema"] == SCHEMA
        assert second["generationConfig"]["responseMimeType"] == "application/json"
        assert "responseSchema" not in second["generationConfig"]
        assert "responseJsonSchema" not in second["generationConfig"]
        assert "JSON Schema" in second["systemInstruction"]["parts"][-1]["text"]
    else:
        assert first["text"]["format"]["schema"] == SCHEMA
        assert second["text"]["format"] == {"type": "json_object"}
        assert "JSON Schema" in second["instructions"]


@pytest.mark.parametrize("stream", [False, True])
async def test_responses_client_through_chat_format_recovery(stream):
    proxy = make_proxy([candidate("model", "openai")], protocol="openai_responses")
    body = {
        "model": "dictionary",
        "input": "投资专家",
        "stream": stream,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "word_card",
                "schema": SCHEMA,
                "strict": True,
            }
        },
    }
    calls = []

    def forward(**kwargs):
        calls.append(kwargs["body"])
        if len(calls) == 1:
            error = {
                "detail": [
                    {
                        "loc": ["body", "response_format", "type"],
                        "msg": "Input should be 'text' or 'json_object'",
                    }
                ]
            }
            return ProviderResponse(status_code=422, body=json.dumps(error).encode())
        return ProviderResponse(status_code=200, body=chat_success(json.dumps(CARD)))

    result, output, metadata, _ = await run_proxy(
        proxy, body, forward, protocol="openai_responses"
    )
    assert result.status_code == 200
    assert metadata["retry_count"] == 1
    assert calls[0]["response_format"]["json_schema"]["schema"] == SCHEMA
    assert calls[1]["response_format"] == {"type": "json_object"}
    if stream:
        assert b"response.completed" in output
        assert b"investment expert" in output
    else:
        assert json.loads(output["output"][0]["content"][0]["text"]) == CARD
