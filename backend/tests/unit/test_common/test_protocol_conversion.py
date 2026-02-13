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
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
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
    assert out_body.get("tool_choice") == {
        "type": "function",
        "function": {"name": "get_weather"},
    }


def test_convert_request_openai_to_openai_responses_chat():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai_responses",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hi"},
            ],
            "max_tokens": 12,
        },
        target_model="gpt-4o-mini",
    )

    assert path == "/v1/responses"
    assert out_body["model"] == "gpt-4o-mini"
    assert out_body["instructions"] == "You are helpful"
    # SDK may simplify single user message to string or keep as list
    input_val = out_body.get("input")
    assert input_val is not None
    if isinstance(input_val, list):
        assert input_val[0]["role"] == "user"
    else:
        # Single message simplified to string
        assert isinstance(input_val, str)
        assert input_val == "Hi"
    assert out_body["max_output_tokens"] == 12


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
                        "parameters": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                        },
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
async def test_convert_request_openai_to_anthropic_preserves_tool_calls_and_user():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "user": "user_1",
            "messages": [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city":"Paris"}',
                            },
                        }
                    ],
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                        },
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "get_weather"}},
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    assert out_body.get("metadata", {}).get("user_id") == "user_1"
    assert isinstance(out_body.get("messages"), list)
    content = out_body["messages"][0].get("content")
    assert isinstance(content, list)
    tool_use_blocks = [
        b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"
    ]
    assert tool_use_blocks
    assert tool_use_blocks[0].get("name") == "get_weather"
    assert tool_use_blocks[0].get("id") == "call_1"


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
                    "input_schema": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
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
    assert out_body.get("tool_choice") == {
        "type": "function",
        "function": {"name": "get_weather"},
    }


@pytest.mark.asyncio
async def test_convert_request_anthropic_to_openai_preserves_tool_calls():
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai",
        path="/v1/messages",
        body={
            "model": "any",
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_123",
                            "name": "get_weather",
                            "input": {"city": "Paris"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_123",
                            "content": "Sunny",
                        }
                    ],
                },
            ],
            "max_tokens": 16,
        },
        target_model="gpt-4o-mini",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "gpt-4o-mini"
    assert out_body["messages"][0]["role"] == "assistant"
    assert out_body["messages"][0]["tool_calls"][0]["id"] == "toolu_123"
    assert out_body["messages"][0]["tool_calls"][0]["function"]["name"] == "get_weather"
    # Tool result message - SDK may use 'tool' or 'user' role depending on implementation
    tool_result_msg = out_body["messages"][1]
    assert tool_result_msg["role"] in ("tool", "user")
    if tool_result_msg["role"] == "tool":
        assert tool_result_msg["tool_call_id"] == "toolu_123"
    else:
        # User role with tool_result content is also valid
        assert "toolu_123" in str(tool_result_msg)


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


def test_convert_request_openai_responses_to_anthropic_with_max_output_tokens():
    """Test that max_output_tokens from OpenAI Responses is mapped to max_tokens for Anthropic."""
    path, out_body = convert_request_for_supplier(
        request_protocol="openai_responses",
        supplier_protocol="anthropic",
        path="/v1/responses",
        body={
            "model": "any",
            "input": "Hello, how are you?",
            "max_output_tokens": 1024,
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    assert out_body["max_tokens"] == 1024
    assert isinstance(out_body.get("messages"), list)


def test_convert_request_openai_responses_to_anthropic_without_max_output_tokens():
    """Test that default max_tokens is injected when max_output_tokens is not provided."""
    path, out_body = convert_request_for_supplier(
        request_protocol="openai_responses",
        supplier_protocol="anthropic",
        path="/v1/responses",
        body={
            "model": "any",
            "input": "Hello, how are you?",
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    # Default max_tokens should be 4096
    assert out_body["max_tokens"] == 4096
    assert isinstance(out_body.get("messages"), list)


def test_convert_request_openai_responses_to_openai_accepts_string_tool_choice():
    """Test Responses tool_choice as string is normalized before SDK conversion."""
    path, out_body = convert_request_for_supplier(
        request_protocol="openai_responses",
        supplier_protocol="openai",
        path="/v1/responses",
        body={
            "model": "any",
            "tool_choice": "none",
            "tools": [],
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": "You are offering command line completion suggestions and descriptions.",
                }
            ],
            "max_output_tokens": 128000,
            "stream": False,
        },
        target_model="gpt-5-mini",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "gpt-5-mini"
    assert isinstance(out_body.get("messages"), list)
    assert out_body["messages"][0]["role"] == "user"
    assert out_body["messages"][0]["content"] == (
        "You are offering command line completion suggestions and descriptions."
    )
    assert out_body.get("tool_choice") == "none"


def test_convert_response_openai_responses_to_openai():
    converted = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="openai_responses",
        target_model="gpt-4o-mini",
        body={
            "id": "resp_1",
            "object": "response",
            "created_at": 123,
            "model": "gpt-4o-mini",
            "output": [
                {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Hello"}],
                }
            ],
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
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


def test_convert_request_anthropic_to_anthropic_uses_provider_default_max_tokens():
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
        options={"default_parameters": {"max_tokens": 8192}},
    )

    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    assert out_body["max_tokens"] == 8192


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
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hi"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 2},
        },
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
    chunk_obj = json.loads(
        next(p for p in content_payloads if '"chat.completion.chunk"' in p)
    )
    assert chunk_obj["choices"][0]["delta"]["content"] == "Hi"


@pytest.mark.asyncio
async def test_convert_stream_anthropic_to_openai_includes_usage():
    """Test that usage information is included when converting Anthropic stream to OpenAI format."""
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
                "usage": {"input_tokens": 14},
            },
        },
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hello!"},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {
                "input_tokens": 14,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 16,
            },
        },
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

    # Find the usage chunk (should have empty choices array)
    usage_chunks = [
        json.loads(p)
        for p in content_payloads
        if '"chat.completion.chunk"' in p and '"usage"' in p
    ]
    assert len(usage_chunks) >= 1, "Expected at least one chunk with usage information"

    # Find the chunk with empty choices (OpenAI's usage-only chunk format)
    usage_only_chunk = next(
        (c for c in usage_chunks if c.get("choices") == []),
        None,
    )
    assert usage_only_chunk is not None, (
        "Expected a usage chunk with empty choices array"
    )

    usage = usage_only_chunk.get("usage")
    assert usage is not None, "Usage should be present in the chunk"
    assert usage.get("prompt_tokens") == 14, "prompt_tokens should be 14"
    assert usage.get("completion_tokens") == 16, "completion_tokens should be 16"
    assert usage.get("total_tokens") == 30, "total_tokens should be 30"


@pytest.mark.asyncio
async def test_convert_stream_openai_responses_to_openai():
    upstream_events = [
        {
            "type": "response.created",
            "response": {
                "id": "resp_1",
                "object": "response",
                "created_at": 1,
                "model": "gpt-4o-mini",
            },
        },
        {"type": "response.output_text.delta", "delta": "Hi"},
        {"type": "response.completed"},
    ]
    upstream = _agen([f"data: {json.dumps(e)}\n\n".encode() for e in upstream_events])

    decoder = SSEDecoder()
    payloads = []
    async for c in convert_stream_for_user(
        request_protocol="openai",
        supplier_protocol="openai_responses",
        upstream=upstream,
        model="gpt-4o-mini",
    ):
        payloads.extend(decoder.feed(c))

    assert payloads[-1].strip() == "[DONE]"
    chunk_obj = json.loads(next(p for p in payloads if '"chat.completion.chunk"' in p))
    assert chunk_obj["choices"][0]["delta"]["content"] == "Hi"


def test_convert_request_strips_stream_options_when_target_is_openai():
    """Test that stream_options is removed when converting to OpenAI protocol.

    Some OpenAI-compatible providers do not support stream_options parameter
    and will return an error like "Unknown parameter: 'include_usage'".
    """
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai",
        path="/v1/messages",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "stream": True,
            "stream_options": {"include_usage": True},
        },
        target_model="gpt-4o-mini",
    )

    assert "stream_options" not in out_body
    assert out_body["stream"] is True


def test_convert_request_strips_include_usage_when_target_is_openai():
    """Test that top-level include_usage is removed when converting to OpenAI protocol.

    Some clients send include_usage at the top level instead of inside stream_options.
    """
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai",
        path="/v1/messages",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "stream": True,
            "include_usage": True,
        },
        target_model="gpt-4o-mini",
    )

    assert "include_usage" not in out_body
    assert out_body["stream"] is True


def test_convert_request_strips_stream_options_when_target_is_openai_responses():
    """Test that stream_options is removed when converting to OpenAI Responses protocol."""
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai_responses",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "stream": True,
            "stream_options": {"include_usage": True},
        },
        target_model="gpt-4o-mini",
    )

    assert "stream_options" not in out_body
    assert out_body["stream"] is True


def test_convert_request_strips_include_usage_when_target_is_openai_responses():
    """Test that top-level include_usage is removed when converting to OpenAI Responses protocol."""
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai_responses",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "stream": True,
            "include_usage": True,
        },
        target_model="gpt-4o-mini",
    )

    assert "include_usage" not in out_body
    assert out_body["stream"] is True


def test_convert_request_strips_stream_options_same_protocol_openai():
    """Test that stream_options is removed even when source and target are both OpenAI.

    This is the identity conversion case where no protocol conversion is needed,
    but we still need to remove unsupported parameters for compatibility.
    """
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 16,
            "stream": True,
            "stream_options": {"include_usage": True},
            "include_usage": True,
        },
        target_model="gpt-4o-mini",
    )

    assert "stream_options" not in out_body
    assert "include_usage" not in out_body
    assert out_body["stream"] is True


@pytest.mark.asyncio
async def test_convert_stream_openai_to_anthropic_multiple_tool_calls_without_index():
    """Test that multiple tool_calls in OpenAI stream are correctly converted to separate
    Anthropic content blocks, even when the 'index' field is missing (e.g., Gemini API).

    This is a regression test for the bug where multiple tool_calls without index were
    merged into a single content block, causing JSON parsing errors.
    """
    # Simulate Gemini-style OpenAI response with multiple tool_calls without index field
    chunk_1 = {
        "choices": [
            {
                "delta": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "arguments": '{"path":"file1.txt","content":"content1"}',
                                "name": "write",
                            },
                            "id": "function-call-001",
                            "type": "function",
                        }
                    ],
                },
                "index": 0,
            }
        ],
        "created": 1234567890,
        "id": "test-id-1",
        "model": "gemini-3-pro-preview",
        "object": "chat.completion.chunk",
    }
    chunk_2 = {
        "choices": [
            {
                "delta": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "arguments": '{"path":"file2.txt","content":"content2"}',
                                "name": "write",
                            },
                            "id": "function-call-002",
                            "type": "function",
                        }
                    ],
                },
                "index": 0,
            }
        ],
        "created": 1234567891,
        "id": "test-id-1",
        "model": "gemini-3-pro-preview",
        "object": "chat.completion.chunk",
    }
    chunk_3 = {
        "choices": [
            {"delta": {"role": "assistant"}, "finish_reason": "stop", "index": 0}
        ],
        "created": 1234567892,
        "id": "test-id-1",
        "model": "gemini-3-pro-preview",
        "object": "chat.completion.chunk",
    }
    upstream = _agen(
        [
            f"data: {json.dumps(chunk_1)}\n\n".encode(),
            f"data: {json.dumps(chunk_2)}\n\n".encode(),
            f"data: {json.dumps(chunk_3)}\n\n".encode(),
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
    events = [json.loads(p) for p in payloads if p.strip() != "[DONE]"]

    # Count content_block_start events for tool_use
    tool_use_starts = [
        e
        for e in events
        if e.get("type") == "content_block_start"
        and e.get("content_block", {}).get("type") == "tool_use"
    ]
    assert (
        len(tool_use_starts) == 2
    ), f"Expected 2 tool_use content_block_start events, got {len(tool_use_starts)}"

    # Verify each tool has correct id
    tool_ids = [e["content_block"]["id"] for e in tool_use_starts]
    assert "function-call-001" in tool_ids
    assert "function-call-002" in tool_ids

    # Verify each tool has correct index (0 and 1)
    tool_indices = [e["index"] for e in tool_use_starts]
    assert 0 in tool_indices
    assert 1 in tool_indices

    # Count content_block_delta events for input_json_delta
    json_deltas = [
        e
        for e in events
        if e.get("type") == "content_block_delta"
        and e.get("delta", {}).get("type") == "input_json_delta"
    ]
    assert (
        len(json_deltas) == 2
    ), f"Expected 2 input_json_delta events, got {len(json_deltas)}"

    # Verify the deltas have different indices (0 and 1)
    delta_indices = [e["index"] for e in json_deltas]
    assert 0 in delta_indices
    assert 1 in delta_indices

    # Count content_block_stop events
    block_stops = [e for e in events if e.get("type") == "content_block_stop"]
    assert (
        len(block_stops) == 2
    ), f"Expected 2 content_block_stop events, got {len(block_stops)}"
