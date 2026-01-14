import json

import pytest

from app.common.protocol_conversion import (
    convert_request_for_supplier,
    convert_response_for_user,
    convert_stream_for_user,
)
from app.common.stream_usage import SSEDecoder


@pytest.mark.asyncio
async def test_convert_request_openai_to_anthropic_messages():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hi"},
            ],
            "temperature": 0.2,
            "max_tokens": 16,
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    assert isinstance(out_body.get("messages"), list)
    assert len(out_body["messages"]) > 0


@pytest.mark.asyncio
async def test_convert_request_anthropic_to_openai_chat_completions():
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai",
        path="/v1/messages",
        body={
            "model": "any",
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "metadata": {"user_id": "u1"},
        },
        target_model="gpt-4o-mini",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "gpt-4o-mini"
    assert out_body.get("user") == "u1"
    assert isinstance(out_body.get("messages"), list)
    assert out_body["messages"][0]["role"] == "system"


def test_convert_request_openai_legacy_functions_normalizes_to_tools():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "functions": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
                }
            ],
            "function_call": {"name": "get_weather"},
        },
        target_model="gpt-4o-mini",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "gpt-4o-mini"
    assert isinstance(out_body.get("tools"), list)
    assert out_body["tools"][0]["type"] == "function"
    assert out_body["tools"][0]["function"]["name"] == "get_weather"
    assert out_body.get("tool_choice") == {"type": "function", "function": {"name": "get_weather"}}


@pytest.mark.asyncio
async def test_convert_request_openai_to_anthropic_preserves_tools():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "get_weather"}},
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    assert isinstance(out_body.get("tools"), list)
    assert out_body["tools"][0]["name"] == "get_weather"


@pytest.mark.asyncio
async def test_convert_request_anthropic_to_openai_preserves_tools():
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai",
        path="/v1/messages",
        body={
            "model": "any",
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
                }
            ],
            "tool_choice": {"type": "tool", "name": "get_weather"},
        },
        target_model="gpt-4o-mini",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "gpt-4o-mini"
    assert isinstance(out_body.get("tools"), list)
    assert out_body["tools"][0]["type"] == "function"
    assert out_body["tools"][0]["function"]["name"] == "get_weather"
    assert out_body.get("tool_choice") == {"type": "function", "function": {"name": "get_weather"}}


def test_convert_response_openai_to_anthropic():
    converted = convert_response_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        target_model="claude-3-5-sonnet",
        body={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 1,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        },
    )

    assert converted["type"] == "message"
    assert converted["role"] == "assistant"
    assert isinstance(converted["content"], list)
    assert converted["content"][0]["type"] == "text"


def test_convert_response_anthropic_to_openai():
    converted = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="anthropic",
        target_model="gpt-4o-mini",
        body={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet",
            "content": [{"type": "text", "text": "Hello"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 2},
        },
    )

    assert converted["object"] == "chat.completion"
    assert converted["choices"][0]["message"]["content"] == "Hello"
    assert converted["usage"]["prompt_tokens"] == 1
    assert converted["usage"]["completion_tokens"] == 2


def test_convert_request_anthropic_to_anthropic_injects_default_max_tokens():
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="anthropic",
        path="/v1/messages",
        body={
            "model": "any",
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hi"}],
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    assert out_body["max_tokens"] == 4096


def test_convert_request_anthropic_to_anthropic_maps_max_completion_tokens():
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="anthropic",
        path="/v1/messages",
        body={
            "model": "any",
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_completion_tokens": 33,
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    assert out_body["max_tokens"] == 33


async def _agen(chunks):
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_convert_stream_openai_to_anthropic():
    chunk_1 = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}],
    }
    chunk_2 = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "gpt-4o-mini",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    upstream = _agen(
        [
            f"data: {json.dumps(chunk_1)}\n\n".encode(),
            f"data: {json.dumps(chunk_2)}\n\n".encode(),
            b"data: [DONE]\n\n",
        ]
    )

    out = b""
    async for c in convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        upstream=upstream,
        model="claude-3-5-sonnet",
    ):
        out += c

    decoder = SSEDecoder()
    payloads = decoder.feed(out)
    events = [json.loads(p)["type"] for p in payloads if p.strip() != "[DONE]"]
    assert events[:2] == ["message_start", "content_block_start"]
    assert "content_block_delta" in events
    assert events[-1] == "message_stop"


@pytest.mark.asyncio
async def test_convert_stream_anthropic_to_openai():
    upstream_events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": "claude-3-5-sonnet",
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hi"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2}},
        {"type": "message_stop"},
    ]
    upstream = _agen([f"data: {json.dumps(e)}\n\n".encode() for e in upstream_events])

    decoder = SSEDecoder()
    payloads = []
    async for c in convert_stream_for_user(
        request_protocol="openai",
        supplier_protocol="anthropic",
        upstream=upstream,
        model="gpt-4o-mini",
    ):
        payloads.extend(decoder.feed(c))

    assert payloads[-1].strip() == "[DONE]"
    content_payloads = [p for p in payloads if p.strip() not in ("[DONE]", "")]
    chunk_obj = json.loads(next(p for p in content_payloads if '"chat.completion.chunk"' in p))
    assert chunk_obj["choices"][0]["delta"]["content"] == "Hi"
