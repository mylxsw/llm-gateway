import json

import pytest

from app.common.protocol import (
    sanitize_anthropic_tool_schema,
    sanitize_anthropic_tools,
    sanitize_gemini_request_body,
)
from app.common.protocol_conversion import (
    convert_request_for_supplier,
    convert_response_for_user,
    convert_stream_for_user,
)
from app.common.stream_usage import SSEDecoder, StreamUsageAccumulator


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


def test_convert_request_openai_to_anthropic_maps_reasoning_effort():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "xhigh"},
            "max_tokens": 16,
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert "reasoning" not in out_body
    assert out_body["thinking"] == {"type": "enabled"}
    assert out_body["output_config"] == {"effort": "max"}


def test_convert_request_openai_to_anthropic_maps_reasoning_none_to_disabled():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "none"},
            "max_tokens": 16,
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert "reasoning" not in out_body
    assert out_body["thinking"] == {"type": "disabled"}
    assert "output_config" not in out_body


def test_convert_request_openai_to_deepseek_maps_reasoning_none_to_thinking_disabled():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="deepseek",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "none"},
        },
        target_model="deepseek-chat",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "deepseek-chat"
    assert "reasoning" not in out_body
    assert out_body["thinking"] == {"type": "disabled"}


def test_convert_request_openai_to_deepseek_maps_reasoning_effort_to_thinking_enabled():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="deepseek",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "high"},
        },
        target_model="deepseek-reasoner",
    )

    assert path == "/v1/chat/completions"
    assert "reasoning" not in out_body
    assert out_body["thinking"] == {"type": "enabled"}
    assert "output_config" not in out_body


def test_convert_request_openai_to_deepseek_preserves_explicit_thinking_type():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="deepseek",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "high"},
            "thinking": {"type": "disabled"},
        },
        target_model="deepseek-chat",
    )

    assert path == "/v1/chat/completions"
    assert "reasoning" not in out_body
    assert out_body["thinking"] == {"type": "disabled"}


def test_convert_request_openai_to_moonshot_uses_deepseek_thinking_handling():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="moonshot",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "high"},
        },
        target_model="kimi-k2",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "kimi-k2"
    assert "reasoning" not in out_body
    assert "output_config" not in out_body
    assert out_body["thinking"] == {"type": "enabled"}


def test_convert_request_openai_to_zhipu_uses_deepseek_thinking_handling():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="zhipu",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "high"},
        },
        target_model="glm-4.5",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "glm-4.5"
    assert "reasoning" not in out_body
    assert "output_config" not in out_body
    assert out_body["thinking"] == {"type": "enabled"}


def test_convert_request_openai_to_aliyun_maps_reasoning_effort_to_enable_thinking():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="aliyun",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "high"},
        },
        target_model="qwen3-max",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "qwen3-max"
    assert "reasoning" not in out_body
    assert "thinking" not in out_body
    assert "output_config" not in out_body
    assert out_body["enable_thinking"] is True


def test_convert_request_openai_to_aliyun_maps_reasoning_none_to_disable_thinking():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="aliyun",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "none"},
        },
        target_model="qwen3-max",
    )

    assert path == "/v1/chat/completions"
    assert "reasoning" not in out_body
    assert out_body["enable_thinking"] is False


def test_convert_request_openai_to_aliyun_preserves_explicit_enable_thinking():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="aliyun",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "high"},
            "enable_thinking": False,
        },
        target_model="qwen3-max",
    )

    assert path == "/v1/chat/completions"
    assert "reasoning" not in out_body
    assert out_body["enable_thinking"] is False


def test_convert_request_openai_to_ark_uses_deepseek_thinking_handling():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="ark",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "none"},
        },
        target_model="doubao-seed-1-6",
    )

    assert path == "/v1/chat/completions"
    assert out_body["model"] == "doubao-seed-1-6"
    assert "reasoning" not in out_body
    assert "output_config" not in out_body
    assert out_body["thinking"] == {"type": "disabled"}


def test_convert_request_openai_completion_to_anthropic_maps_reasoning_effort():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/completions",
        body={
            "model": "any",
            "prompt": "Hi",
            "reasoning": {"effort": "high"},
            "max_tokens": 16,
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert out_body["messages"][0]["content"] in (
        "Hi",
        [{"type": "text", "text": "Hi"}],
    )
    assert "reasoning" not in out_body
    assert out_body["thinking"] == {"type": "enabled"}
    assert out_body["output_config"] == {"effort": "high"}


def test_convert_request_openai_completion_to_responses_preserves_reasoning_effort():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai_responses",
        path="/v1/completions",
        body={
            "model": "any",
            "prompt": "Hi",
            "reasoning": {"effort": "minimal"},
            "max_tokens": 16,
        },
        target_model="gpt-5-mini",
    )

    assert path == "/v1/responses"
    assert out_body["input"] == "Hi"
    assert out_body["reasoning"] == {"effort": "minimal"}


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
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 2,
                "total_tokens": 7,
                "prompt_tokens_details": {"cached_tokens": 4},
            },
        },
    )

    assert converted["type"] == "message"
    assert converted["role"] == "assistant"
    assert isinstance(converted["content"], list)
    assert converted["content"][0]["type"] == "text"
    assert converted["usage"]["input_tokens"] == 1
    assert converted["usage"]["cache_read_input_tokens"] == 4


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
            "usage": {
                "input_tokens": 1,
                "cache_creation_input_tokens": 3,
                "cache_read_input_tokens": 4,
                "output_tokens": 2,
            },
        },
    )

    assert converted["object"] == "chat.completion"
    assert converted["choices"][0]["message"]["content"] == "Hello"
    assert converted["usage"]["prompt_tokens"] == 8
    assert converted["usage"]["completion_tokens"] == 2
    assert converted["usage"]["total_tokens"] == 10
    assert converted["usage"]["prompt_tokens_details"] == {"cached_tokens": 4}


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


def test_convert_request_anthropic_to_openai_maps_thinking_effort():
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai",
        path="/v1/messages",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "max"},
            "max_tokens": 16,
        },
        target_model="gpt-5-mini",
    )

    assert path == "/v1/chat/completions"
    assert "thinking" not in out_body
    assert "output_config" not in out_body
    assert out_body["reasoning"] == {"effort": "xhigh"}


def test_convert_request_anthropic_to_openai_maps_disabled_thinking_to_none():
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai",
        path="/v1/messages",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "thinking": {"type": "disabled"},
            "output_config": {"effort": "high"},
            "max_tokens": 16,
        },
        target_model="gpt-5-mini",
    )

    assert path == "/v1/chat/completions"
    assert "thinking" not in out_body
    assert "output_config" not in out_body
    assert out_body["reasoning"] == {"effort": "none"}


def test_convert_request_identity_openai_normalizes_anthropic_reasoning_fields():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai",
        path="/v1/chat/completions",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "thinking": {"type": "enabled"},
            "output_config": {"effort": "low"},
        },
        target_model="gpt-5-mini",
    )

    assert path == "/v1/chat/completions"
    assert "thinking" not in out_body
    assert "output_config" not in out_body
    assert out_body["reasoning"] == {"effort": "low"}


def test_convert_request_identity_anthropic_normalizes_openai_reasoning_fields():
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="anthropic",
        path="/v1/messages",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "reasoning": {"effort": "high"},
        },
        target_model="claude-3-5-sonnet",
    )

    assert path == "/v1/messages"
    assert "reasoning" not in out_body
    assert out_body["thinking"] == {"type": "enabled"}
    assert out_body["output_config"] == {"effort": "high"}


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


class TestImageDefaultResponseFormat:
    """Test that image API requests get response_format=b64_json by default."""

    def test_generations_default_response_format(self):
        path, body = convert_request_for_supplier(
            request_protocol="openai",
            supplier_protocol="openai",
            path="/v1/images/generations",
            body={"model": "gpt-image-1", "prompt": "A cat"},
            target_model="gpt-image-1",
        )
        assert body["response_format"] == "b64_json"

    def test_generations_explicit_response_format_preserved(self):
        path, body = convert_request_for_supplier(
            request_protocol="openai",
            supplier_protocol="openai",
            path="/v1/images/generations",
            body={"model": "dall-e-3", "prompt": "A cat", "response_format": "url"},
            target_model="dall-e-3",
        )
        assert body["response_format"] == "url"

    def test_edits_default_response_format(self):
        path, body = convert_request_for_supplier(
            request_protocol="openai",
            supplier_protocol="openai",
            path="/v1/images/edits",
            body={"model": "gpt-image-1", "prompt": "Add a hat"},
            target_model="gpt-image-1",
        )
        assert body["response_format"] == "b64_json"

    def test_variations_default_response_format(self):
        path, body = convert_request_for_supplier(
            request_protocol="openai",
            supplier_protocol="openai",
            path="/v1/images/variations",
            body={"model": "dall-e-2"},
            target_model="dall-e-2",
        )
        assert body["response_format"] == "b64_json"

    def test_non_image_path_no_default(self):
        path, body = convert_request_for_supplier(
            request_protocol="openai",
            supplier_protocol="openai",
            path="/v1/chat/completions",
            body={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
            target_model="gpt-4",
        )
        assert "response_format" not in body


def test_convert_request_openai_to_gemini_chat():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="gemini",
        path="/v1/chat/completions",
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello Gemini"}],
            "max_tokens": 64,
        },
        target_model="gemini-2.0-flash",
    )
    assert path == "/v1beta/models/gemini-2.0-flash:generateContent"
    assert out_body["contents"][0]["role"] == "user"
    assert out_body["contents"][0]["parts"][0]["text"] == "Hello Gemini"
    assert out_body["generationConfig"]["maxOutputTokens"] == 64


def test_convert_request_openai_to_gemini_preserves_tool_response_name():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="gemini",
        path="/v1/chat/completions",
        body={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": "Run ls"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "exec",
                                "arguments": "{\"command\":\"ls\"}",
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_123",
                    "content": "file-a\nfile-b",
                },
            ],
        },
        target_model="gemini-2.0-flash",
    )
    assert path == "/v1beta/models/gemini-2.0-flash:generateContent"
    assert out_body["contents"][1]["role"] == "model"
    assert out_body["contents"][1]["parts"][0]["functionCall"]["name"] == "exec"
    assert out_body["contents"][2]["role"] == "user"
    assert (
        out_body["contents"][2]["parts"][0]["functionResponse"]["name"] == "exec"
    )
    assert out_body["contents"][2]["parts"][0]["functionResponse"]["id"] == "call_123"


def test_convert_request_openai_to_gemini_omits_empty_tool_parameters():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="gemini",
        path="/v1/chat/completions",
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "List agents"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "agents_list",
                        "description": "List agents",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                }
            ],
        },
        target_model="gemini-2.0-flash",
    )
    assert path == "/v1beta/models/gemini-2.0-flash:generateContent"
    decl = out_body["tools"][0]["functionDeclarations"][0]
    assert decl["name"] == "agents_list"
    assert "parameters" not in decl


def test_convert_request_openai_to_gemini_strips_unsupported_tool_schema_keywords():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="gemini",
        path="/v1/chat/completions",
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Check tool schemas"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "exec",
                        "parameters": {
                            "$schema": "http://json-schema.org/draft-07/schema#",
                            "type": "object",
                            "required": ["command"],
                            "properties": {
                                "command": {"type": "string"},
                                "env": {
                                    "type": "object",
                                    "propertyNames": {"type": "string"},
                                    "patternProperties": {
                                        "^(.*)$": {"type": "string"}
                                    },
                                },
                                "timeout": {
                                    "type": "integer",
                                    "exclusiveMinimum": 0,
                                },
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "browser",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "fields": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {},
                                        "additionalProperties": True,
                                    },
                                },
                                "request": {
                                    "type": "object",
                                    "properties": {
                                        "fields": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {},
                                                "additionalProperties": True,
                                            },
                                        }
                                    },
                                },
                            },
                        },
                    },
                },
            ],
        },
        target_model="gemini-2.0-flash",
    )

    assert path == "/v1beta/models/gemini-2.0-flash:generateContent"
    tools = out_body["tools"][0]["functionDeclarations"]
    exec_params = tools[0]["parameters"]
    browser_params = tools[1]["parameters"]

    assert "$schema" not in exec_params
    assert "patternProperties" not in json.dumps(exec_params)
    assert "propertyNames" not in json.dumps(exec_params)
    assert "exclusiveMinimum" not in json.dumps(exec_params)
    assert "additionalProperties" not in json.dumps(browser_params)
    assert exec_params["properties"]["env"] == {"type": "object"}
    assert exec_params["properties"]["timeout"] == {"type": "integer"}
    assert browser_params["properties"]["fields"]["items"] == {"type": "object"}
    assert (
        browser_params["properties"]["request"]["properties"]["fields"]["items"]
        == {"type": "object"}
    )


def test_convert_request_openai_to_gemini_strips_unsupported_response_schema_keywords():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="gemini",
        path="/v1/chat/completions",
        body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Return JSON"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "schema": {
                        "$schema": "http://json-schema.org/draft-07/schema#",
                        "type": "object",
                        "properties": {
                            "env": {
                                "type": "object",
                                "patternProperties": {
                                    "^(.*)$": {"type": "string"}
                                },
                            }
                        },
                    }
                },
            },
        },
        target_model="gemini-2.0-flash",
    )

    assert path == "/v1beta/models/gemini-2.0-flash:generateContent"
    response_schema = out_body["generationConfig"]["responseSchema"]
    assert "$schema" not in response_schema
    assert "patternProperties" not in json.dumps(response_schema)
    assert response_schema["properties"]["env"] == {"type": "object"}


def test_sanitize_gemini_request_body_is_public_helper():
    out_body = sanitize_gemini_request_body(
        {
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "exec",
                            "parameters": {
                                "$schema": "http://json-schema.org/draft-07/schema#",
                                "type": "object",
                                "properties": {
                                    "env": {
                                        "type": "object",
                                        "additionalProperties": True,
                                        "propertyNames": {"type": "string"},
                                    }
                                },
                                "example": {"env": {"PATH": "/tmp"}},
                            },
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseSchema": {
                    "type": "object",
                    "properties": {
                        "env": {
                            "type": "object",
                            "patternProperties": {"^(.*)$": {"type": "string"}},
                        },
                        "timeout": {"type": "integer", "exclusiveMinimum": 0},
                    },
                }
            },
        }
    )

    params = out_body["tools"][0]["functionDeclarations"][0]["parameters"]
    response_schema = out_body["generationConfig"]["responseSchema"]
    assert "$schema" not in params
    assert "additionalProperties" not in json.dumps(params)
    assert "propertyNames" not in json.dumps(params)
    assert "patternProperties" not in json.dumps(response_schema)
    assert "exclusiveMinimum" not in json.dumps(response_schema)
    assert params["example"] == {"env": {"PATH": "/tmp"}}


def test_convert_request_openai_completion_to_gemini():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="gemini",
        path="/v1/completions",
        body={"model": "gpt-3.5-turbo-instruct", "prompt": "Say hi"},
        target_model="gemini-2.0-flash",
    )
    assert path == "/v1beta/models/gemini-2.0-flash:generateContent"
    assert out_body["contents"][0]["parts"][0]["text"] == "Say hi"


def test_convert_request_openai_embeddings_to_gemini_batch():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="gemini",
        path="/v1/embeddings",
        body={"model": "text-embedding-3-small", "input": ["a", "b"], "dimensions": 8},
        target_model="gemini-embedding-001",
    )
    assert path == "/v1beta/models/gemini-embedding-001:batchEmbedContents"
    assert len(out_body["requests"]) == 2
    assert out_body["requests"][0]["outputDimensionality"] == 8


def test_convert_request_openai_images_to_gemini_generate_content():
    path, out_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="gemini",
        path="/v1/images/generations",
        body={"model": "gpt-image-1", "prompt": "A cat", "size": "1024x1024"},
        target_model="gemini-2.5-flash-image",
    )
    assert path == "/v1beta/models/gemini-2.5-flash-image:generateContent"
    assert out_body["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert out_body["generationConfig"]["imageConfig"]["aspectRatio"] == "1:1"


def test_convert_response_gemini_to_openai_chat():
    converted = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="gemini",
        target_model="gemini-2.0-flash",
        body={
            "responseId": "resp-1",
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "Hello from Gemini"}]},
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 3,
                "candidatesTokenCount": 5,
                "totalTokenCount": 8,
            },
        },
    )
    assert converted["object"] == "chat.completion"
    assert converted["choices"][0]["message"]["content"] == "Hello from Gemini"
    assert converted["usage"]["prompt_tokens"] == 3
    assert converted["usage"]["completion_tokens"] == 5


def test_convert_response_gemini_to_openai_embeddings():
    converted = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="gemini",
        target_model="gemini-embedding-001",
        body={"embedding": {"values": [0.1, 0.2, 0.3]}},
    )
    assert converted["object"] == "list"
    assert converted["data"][0]["object"] == "embedding"
    assert converted["data"][0]["embedding"] == [0.1, 0.2, 0.3]


def test_convert_response_gemini_to_openai_images():
    converted = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="gemini",
        target_model="gemini-2.5-flash-image",
        body={
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/jpeg",
                                    "data": "0dHA6base64data",
                                }
                            }
                        ],
                    },
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 6,
                "candidatesTokenCount": 1220,
                "totalTokenCount": 1377,
                "promptTokensDetails": [
                    {"modality": "TEXT", "tokenCount": 6}
                ],
                "candidatesTokensDetails": [
                    {"modality": "IMAGE", "tokenCount": 1120}
                ],
                "thoughtsTokenCount": 151,
            },
        },
    )
    assert isinstance(converted.get("data"), list)
    assert converted["data"][0]["b64_json"] == "0dHA6base64data"
    assert converted["output_format"] == "jpeg"
    # Verify usage
    usage = converted.get("usage")
    assert usage is not None
    assert usage["input_tokens"] == 6
    assert usage["output_tokens"] == 1220
    assert usage["total_tokens"] == 1377
    assert usage["input_tokens_details"] == {"text_tokens": 6}
    assert usage["output_tokens_details"] == {"image_tokens": 1120}


def test_convert_response_gemini_to_openai_images_png_no_usage():
    """Image response with png mimeType and no usageMetadata."""
    converted = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="gemini",
        target_model="gemini-2.5-flash-image",
        body={
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": "iVBORw0KGgoAAAANSUhEUgAAAAUA",
                                }
                            }
                        ],
                    },
                    "finishReason": "STOP",
                    "index": 0,
                }
            ]
        },
    )
    assert isinstance(converted.get("data"), list)
    assert converted["data"][0]["b64_json"] == "iVBORw0KGgoAAAANSUhEUgAAAAUA"
    assert converted["output_format"] == "png"
    assert "usage" not in converted


@pytest.mark.asyncio
async def test_convert_stream_gemini_to_openai():
    upstream = _agen(
        [
            b'data: {"candidates":[{"content":{"role":"model","parts":[{"text":"Hello"}]},"index":0}]}\n\n',
            b'data: {"candidates":[{"finishReason":"STOP","index":0}],"usageMetadata":{"promptTokenCount":2,"candidatesTokenCount":3,"totalTokenCount":5}}\n\n',
        ]
    )

    out = b""
    async for chunk in convert_stream_for_user(
        request_protocol="openai",
        supplier_protocol="gemini",
        upstream=upstream,
        model="gemini-2.0-flash",
    ):
        out += chunk

    decoder = SSEDecoder()
    payloads = decoder.feed(out)
    assert any('"chat.completion.chunk"' in payload for payload in payloads)
    assert any('"usage"' in payload for payload in payloads if payload != "[DONE]")


@pytest.mark.asyncio
async def test_convert_stream_gemini_to_anthropic():
    """Test chain conversion: Gemini -> OpenAI -> Anthropic stream."""
    upstream = _agen(
        [
            b'data: {"candidates":[{"content":{"role":"model","parts":[{"text":"Bonjour"}]},"index":0}]}\n\n',
            b'data: {"candidates":[{"finishReason":"STOP","index":0}],"usageMetadata":{"promptTokenCount":2,"candidatesTokenCount":4,"totalTokenCount":6}}\n\n',
        ]
    )

    out = b""
    async for chunk in convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol="gemini",
        upstream=upstream,
        model="claude-3-5-sonnet",
    ):
        out += chunk

    decoder = SSEDecoder()
    payloads = decoder.feed(out)
    events = [json.loads(p) for p in payloads if p.strip() != "[DONE]"]
    event_types = [e.get("type") for e in events]
    assert "message_start" in event_types
    assert "content_block_delta" in event_types
    assert "message_stop" in event_types
    # Verify text content arrived
    text_deltas = [
        e for e in events
        if e.get("type") == "content_block_delta"
        and e.get("delta", {}).get("type") == "text_delta"
    ]
    assert len(text_deltas) > 0
    assert text_deltas[0]["delta"]["text"] == "Bonjour"


@pytest.mark.asyncio
async def test_convert_stream_anthropic_to_gemini():
    """Test chain conversion: Anthropic -> OpenAI -> Gemini stream."""
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
            "delta": {"type": "text_delta", "text": "Hola"},
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

    out = b""
    async for chunk in convert_stream_for_user(
        request_protocol="gemini",
        supplier_protocol="anthropic",
        upstream=upstream,
        model="gemini-2.0-flash",
    ):
        out += chunk

    decoder = SSEDecoder()
    payloads = decoder.feed(out)
    # Gemini stream format uses candidates[].content.parts[]
    gemini_chunks = [json.loads(p) for p in payloads if p.strip() != "[DONE]"]
    assert len(gemini_chunks) > 0
    # Find chunk with text content
    text_found = False
    for chunk in gemini_chunks:
        candidates = chunk.get("candidates", [])
        for cand in candidates:
            parts = cand.get("content", {}).get("parts", [])
            for part in parts:
                if isinstance(part.get("text"), str) and part["text"]:
                    text_found = True
    assert text_found, "Expected Gemini stream to contain text parts"


def test_convert_request_openai_responses_to_gemini():
    """Test OpenAI Responses -> Gemini request conversion."""
    path, out_body = convert_request_for_supplier(
        request_protocol="openai_responses",
        supplier_protocol="gemini",
        path="/v1/responses",
        body={
            "model": "any",
            "input": "Hello from Responses",
            "instructions": "Be helpful",
            "max_output_tokens": 128,
        },
        target_model="gemini-2.0-flash",
    )
    assert "/v1beta/models/gemini-2.0-flash:" in path
    assert isinstance(out_body.get("contents"), list)
    assert len(out_body["contents"]) > 0


def test_convert_request_anthropic_to_gemini():
    """Test Anthropic -> Gemini request conversion."""
    path, out_body = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="gemini",
        path="/v1/messages",
        body={
            "model": "claude-3-5-sonnet",
            "system": "You are helpful",
            "messages": [{"role": "user", "content": "Greetings"}],
            "max_tokens": 256,
        },
        target_model="gemini-2.0-flash",
    )
    assert "/v1beta/models/gemini-2.0-flash:" in path
    assert isinstance(out_body.get("contents"), list)
    assert len(out_body["contents"]) > 0


def test_convert_request_gemini_to_anthropic():
    """Test Gemini -> Anthropic request conversion."""
    path, out_body = convert_request_for_supplier(
        request_protocol="gemini",
        supplier_protocol="anthropic",
        path="/v1beta/models/gemini-2.0-flash:generateContent",
        body={
            "contents": [{"role": "user", "parts": [{"text": "Hi from Gemini"}]}],
            "generationConfig": {"maxOutputTokens": 64},
        },
        target_model="claude-3-5-sonnet",
    )
    assert path == "/v1/messages"
    assert out_body["model"] == "claude-3-5-sonnet"
    assert isinstance(out_body.get("messages"), list)
    assert "max_tokens" in out_body


def test_convert_response_gemini_to_anthropic():
    """Test Gemini -> Anthropic response conversion (chain: Gemini -> OpenAI -> Anthropic)."""
    converted = convert_response_for_user(
        request_protocol="anthropic",
        supplier_protocol="gemini",
        target_model="claude-3-5-sonnet",
        body={
            "responseId": "resp-1",
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "Hello from Gemini"}]},
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 3,
                "candidatesTokenCount": 5,
                "totalTokenCount": 8,
            },
        },
    )
    assert converted["type"] == "message"
    assert converted["role"] == "assistant"
    assert isinstance(converted["content"], list)
    assert converted["content"][0]["type"] == "text"
    assert converted["usage"]["input_tokens"] == 3
    assert "Hello from Gemini" in converted["content"][0]["text"]


# ---------------------------------------------------------------------------
# Anthropic tool-schema sanitization (top-level anyOf/oneOf/allOf)
# ---------------------------------------------------------------------------


def _share_artifact_schema():
    """The real schema from the Osaurus `share_artifact` tool that triggered the
    Anthropic 400 (top-level anyOf)."""
    return {
        "additionalProperties": False,
        "anyOf": [
            {"required": ["path"]},
            {"required": ["content", "filename"]},
        ],
        "properties": {
            "content": {"type": "string"},
            "path": {"type": "string"},
            "filename": {"type": "string"},
        },
        "required": [],
        "type": "object",
    }


def test_sanitize_anthropic_tool_schema_strips_top_level_anyof():
    schema = _share_artifact_schema()
    out = sanitize_anthropic_tool_schema(schema)

    assert "anyOf" not in out
    assert "oneOf" not in out
    assert "allOf" not in out
    assert out["type"] == "object"
    assert out["required"] == []
    # all branch + top-level properties survive
    assert set(out["properties"]) >= {"content", "path", "filename"}
    # input is not mutated
    assert "anyOf" in schema


def test_sanitize_anthropic_tool_schema_merges_branch_properties():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "oneOf": [
            {"properties": {"b": {"type": "integer"}}, "required": ["b"]},
            {"properties": {"c": {"type": "boolean"}}},
        ],
    }
    out = sanitize_anthropic_tool_schema(schema)
    assert set(out["properties"]) == {"a", "b", "c"}
    assert out["required"] == []
    assert "oneOf" not in out


def test_sanitize_anthropic_tool_schema_preserves_nested_combinators():
    schema = {
        "type": "object",
        "properties": {
            "x": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
        },
    }
    out = sanitize_anthropic_tool_schema(schema)
    # nested anyOf is valid for Anthropic and must be left intact
    assert "anyOf" in out["properties"]["x"]


def test_sanitize_anthropic_tool_schema_noop_without_combinators():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    out = sanitize_anthropic_tool_schema(schema)
    assert out == schema


def test_sanitize_anthropic_tools_end_to_end():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "share_artifact",
                "parameters": _share_artifact_schema(),
            },
        }
    ]
    out = sanitize_anthropic_tools(tools)
    params = out[0]["function"]["parameters"]
    assert "anyOf" not in json.dumps(params)
    # original untouched
    assert "anyOf" in tools[0]["function"]["parameters"]


def test_sanitize_anthropic_tools_skips_malformed_entries():
    tools = [
        "not-a-dict",
        {"type": "function"},  # no function dict
        {"type": "function", "function": {"name": "x"}},  # no parameters
    ]
    # must not raise
    out = sanitize_anthropic_tools(tools)
    assert len(out) == 3


@pytest.mark.asyncio
async def test_convert_stream_openai_to_anthropic_carries_usage_from_empty_choices_chunk():
    """Regression: OpenAI streams report the real usage in a final chunk whose
    `choices` is `[]` (often after the finish_reason chunk). That usage — including
    cached tokens — must survive the OpenAI→Anthropic conversion and be readable by
    the billing accumulator. See plan crispy-petting-mccarthy."""
    content_chunk = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "claude-opus-4-8",
        "choices": [{"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}],
        "usage": None,
    }
    finish_chunk = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "claude-opus-4-8",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": None,
    }
    # Real usage arrives last, with empty choices.
    usage_chunk = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": "claude-opus-4-8",
        "choices": [],
        "usage": {
            "prompt_tokens": 373372,
            "completion_tokens": 891,
            "total_tokens": 374263,
            "prompt_tokens_details": {"cached_tokens": 373245},
        },
    }
    upstream = _agen(
        [
            f"data: {json.dumps(content_chunk)}\n\n".encode(),
            f"data: {json.dumps(finish_chunk)}\n\n".encode(),
            f"data: {json.dumps(usage_chunk)}\n\n".encode(),
            b"data: [DONE]\n\n",
        ]
    )

    # The accumulator consumes the CONVERTED (Anthropic) stream, exactly as
    # proxy_service.process_request_stream does for a cross-protocol request.
    acc = StreamUsageAccumulator(protocol="anthropic", model="claude-opus-4-8")
    async for c in convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        upstream=upstream,
        model="claude-opus-4-8",
    ):
        acc.feed(c)

    result = acc.finalize()
    assert result.input_tokens == 373372
    assert result.output_tokens == 891
    assert result.usage_details is not None
    assert result.usage_details["cache_read_input_tokens"] == 373245


@pytest.mark.asyncio
async def test_convert_stream_openai_to_anthropic_empty_stream_no_spurious_message_delta():
    """An empty/contentless upstream must emit only message_stop — never a
    message_delta without a preceding message_start (which would be malformed
    Anthropic SSE). Guards the trailing-flush logic."""
    upstream = _agen([b"data: [DONE]\n\n"])

    out = b""
    async for c in convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        upstream=upstream,
        model="claude-opus-4-8",
    ):
        out += c

    decoder = SSEDecoder()
    events = [
        json.loads(p)["type"]
        for p in decoder.feed(out)
        if p.strip() != "[DONE]"
    ]
    assert events == ["message_stop"]


@pytest.mark.asyncio
async def test_convert_stream_openai_to_anthropic_usage_without_finish_reason():
    """Some suppliers emit the usage chunk (empty choices) without ever sending a
    finish_reason. Usage must still be carried into the terminal message_delta."""
    content_chunk = {
        "choices": [{"index": 0, "delta": {"content": "Hi"}, "finish_reason": None}],
    }
    usage_chunk = {
        "choices": [],
        "usage": {"prompt_tokens": 100, "completion_tokens": 5},
    }
    upstream = _agen(
        [
            f"data: {json.dumps(content_chunk)}\n\n".encode(),
            f"data: {json.dumps(usage_chunk)}\n\n".encode(),
            b"data: [DONE]\n\n",
        ]
    )

    acc = StreamUsageAccumulator(protocol="anthropic", model="claude-opus-4-8")
    async for c in convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        upstream=upstream,
        model="claude-opus-4-8",
    ):
        acc.feed(c)

    result = acc.finalize()
    assert result.input_tokens == 100
    assert result.output_tokens == 5
