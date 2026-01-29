"""
Unit tests for the refactored protocol conversion module.

Tests the new modular architecture with unified interfaces.
"""

import json
import pytest
from typing import AsyncGenerator

from app.common.protocol import (
    Protocol,
    ConversionResult,
    ProtocolConversionError,
    UnsupportedConversionError,
    ValidationError,
    convert_request,
    convert_response,
    convert_stream,
    normalize_protocol,
    reset_registry,
    ConverterRegistry,
    ProtocolConverterManager,
)
from app.common.protocol.base import (
    IRequestConverter,
    IResponseConverter,
    IStreamConverter,
)


class TestProtocolEnum:
    """Test Protocol enum functionality."""

    def test_protocol_values(self):
        assert Protocol.OPENAI.value == "openai"
        assert Protocol.OPENAI_RESPONSES.value == "openai_responses"
        assert Protocol.ANTHROPIC.value == "anthropic"

    def test_protocol_from_string(self):
        assert Protocol.from_string("openai") == Protocol.OPENAI
        assert Protocol.from_string("OPENAI") == Protocol.OPENAI
        assert Protocol.from_string("openai_chat") == Protocol.OPENAI
        assert Protocol.from_string("openai_classic") == Protocol.OPENAI
        assert Protocol.from_string("openai_responses") == Protocol.OPENAI_RESPONSES
        assert Protocol.from_string("anthropic") == Protocol.ANTHROPIC
        assert Protocol.from_string("anthropic_messages") == Protocol.ANTHROPIC

    def test_protocol_from_string_invalid(self):
        with pytest.raises(ValueError):
            Protocol.from_string("unknown_protocol")


class TestNormalizeProtocol:
    """Test normalize_protocol function."""

    def test_normalize_openai(self):
        assert normalize_protocol("openai") == Protocol.OPENAI
        assert normalize_protocol("OPENAI") == Protocol.OPENAI
        assert normalize_protocol("openai_chat") == Protocol.OPENAI

    def test_normalize_anthropic(self):
        assert normalize_protocol("anthropic") == Protocol.ANTHROPIC
        assert normalize_protocol("ANTHROPIC") == Protocol.ANTHROPIC
        assert normalize_protocol("anthropic_messages") == Protocol.ANTHROPIC

    def test_normalize_openai_responses(self):
        assert normalize_protocol("openai_responses") == Protocol.OPENAI_RESPONSES

    def test_normalize_invalid(self):
        with pytest.raises(UnsupportedConversionError):
            normalize_protocol("invalid_protocol")


class TestConverterRegistry:
    """Test ConverterRegistry functionality."""

    def setup_method(self):
        reset_registry()

    def test_singleton_instance(self):
        registry1 = ConverterRegistry.get_instance()
        registry2 = ConverterRegistry.get_instance()
        assert registry1 is registry2

    def test_reset_singleton(self):
        registry1 = ConverterRegistry.get_instance()
        reset_registry()
        registry2 = ConverterRegistry.get_instance()
        assert registry1 is not registry2

    def test_list_supported_conversions(self):
        registry = ConverterRegistry.get_instance()
        # First trigger lazy initialization by doing a conversion
        try:
            convert_request("openai", "anthropic", "/v1/chat/completions",
                          {"messages": [{"role": "user", "content": "Hi"}]}, "test")
        except Exception:
            pass

        conversions = registry.list_supported_conversions()
        assert "request" in conversions
        assert "response" in conversions
        assert "stream" in conversions


class TestConvertRequest:
    """Test convert_request function."""

    def setup_method(self):
        reset_registry()

    def test_openai_to_anthropic(self):
        result = convert_request(
            source_protocol="openai",
            target_protocol="anthropic",
            path="/v1/chat/completions",
            body={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                ],
                "temperature": 0.7,
            },
            target_model="claude-3-5-sonnet-20241022",
        )

        assert isinstance(result, ConversionResult)
        assert result.path == "/v1/messages"
        assert result.body["model"] == "claude-3-5-sonnet-20241022"
        assert "messages" in result.body
        assert "max_tokens" in result.body  # Anthropic requires max_tokens

    def test_anthropic_to_openai(self):
        result = convert_request(
            source_protocol="anthropic",
            target_protocol="openai",
            path="/v1/messages",
            body={
                "model": "claude-3-5-sonnet-20241022",
                "system": "You are helpful",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 1024,
            },
            target_model="gpt-4o-mini",
        )

        assert isinstance(result, ConversionResult)
        assert result.path == "/v1/chat/completions"
        assert result.body["model"] == "gpt-4o-mini"
        assert "messages" in result.body
        # System message should be included
        system_messages = [m for m in result.body["messages"] if m.get("role") == "system"]
        assert len(system_messages) == 1

    def test_openai_to_openai_responses(self):
        result = convert_request(
            source_protocol="openai",
            target_protocol="openai_responses",
            path="/v1/chat/completions",
            body={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                ],
                "max_tokens": 512,
            },
            target_model="gpt-4o-mini",
        )

        assert isinstance(result, ConversionResult)
        assert result.path == "/v1/responses"
        assert result.body["model"] == "gpt-4o-mini"
        assert "input" in result.body
        assert "instructions" in result.body

    def test_same_protocol_passthrough(self):
        original_body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        result = convert_request(
            source_protocol="openai",
            target_protocol="openai",
            path="/v1/chat/completions",
            body=original_body,
            target_model="gpt-4o-mini",
        )

        assert result.path == "/v1/chat/completions"
        assert result.body["model"] == "gpt-4o-mini"
        assert result.body["messages"] == original_body["messages"]

    def test_with_tools(self):
        result = convert_request(
            source_protocol="openai",
            target_protocol="anthropic",
            path="/v1/chat/completions",
            body={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "What's the weather?"}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "description": "Get weather information",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string"},
                                },
                                "required": ["location"],
                            },
                        },
                    }
                ],
            },
            target_model="claude-3-5-sonnet-20241022",
        )

        assert result.path == "/v1/messages"
        assert "tools" in result.body
        assert result.body["tools"][0]["name"] == "get_weather"

    def test_legacy_functions_normalized(self):
        result = convert_request(
            source_protocol="openai",
            target_protocol="openai",
            path="/v1/chat/completions",
            body={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
                "functions": [
                    {
                        "name": "my_function",
                        "description": "A test function",
                        "parameters": {"type": "object", "properties": {}},
                    }
                ],
                "function_call": "auto",
            },
            target_model="gpt-4o-mini",
        )

        # Should have normalized to tools
        assert "tools" in result.body
        assert result.body["tools"][0]["function"]["name"] == "my_function"


class TestConvertResponse:
    """Test convert_response function."""

    def setup_method(self):
        reset_registry()

    def test_anthropic_to_openai(self):
        result = convert_response(
            source_protocol="anthropic",
            target_protocol="openai",
            body={
                "id": "msg_123",
                "type": "message",
                "role": "assistant",
                "model": "claude-3-5-sonnet-20241022",
                "content": [{"type": "text", "text": "Hello there!"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
            target_model="gpt-4o-mini",
        )

        assert "choices" in result
        assert result["choices"][0]["message"]["content"] == "Hello there!"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 5

    def test_openai_to_anthropic(self):
        result = convert_response(
            source_protocol="openai",
            target_protocol="anthropic",
            body={
                "id": "chatcmpl-123",
                "object": "chat.completion",
                "created": 1234567890,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
            target_model="claude-3-5-sonnet-20241022",
        )

        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

    def test_same_protocol_passthrough(self):
        original = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [{"message": {"content": "Hello"}}],
        }
        result = convert_response(
            source_protocol="openai",
            target_protocol="openai",
            body=original,
            target_model="gpt-4o-mini",
        )
        assert result == original

    def test_with_tool_calls(self):
        result = convert_response(
            source_protocol="anthropic",
            target_protocol="openai",
            body={
                "id": "msg_123",
                "type": "message",
                "role": "assistant",
                "model": "claude-3-5-sonnet-20241022",
                "content": [
                    {"type": "text", "text": "Let me check the weather."},
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "get_weather",
                        "input": {"location": "Paris"},
                    },
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 10, "output_tokens": 20},
            },
            target_model="gpt-4o-mini",
        )

        assert "choices" in result
        message = result["choices"][0]["message"]
        assert "tool_calls" in message
        assert message["tool_calls"][0]["function"]["name"] == "get_weather"


class TestConvertStream:
    """Test convert_stream function."""

    def setup_method(self):
        reset_registry()

    @pytest.mark.asyncio
    async def test_anthropic_to_openai_stream(self):
        """Test streaming conversion from Anthropic to OpenAI."""
        anthropic_events = [
            {
                "type": "message_start",
                "message": {
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": "claude-3-5-sonnet-20241022",
                    "stop_reason": None,
                    "usage": {"input_tokens": 10, "output_tokens": 0},
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
                "delta": {"type": "text_delta", "text": "Hello"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": " there!"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 5},
            },
            {"type": "message_stop"},
        ]

        async def upstream():
            for event in anthropic_events:
                yield f"data: {json.dumps(event)}\n\n".encode()

        output_chunks = []
        async for chunk in convert_stream(
            source_protocol="anthropic",
            target_protocol="openai",
            upstream=upstream(),
            model="gpt-4o-mini",
        ):
            output_chunks.append(chunk)

        # Verify we got output
        assert len(output_chunks) > 0

        # Parse and verify chunks
        all_content = b"".join(output_chunks).decode()
        assert "chat.completion.chunk" in all_content
        assert "[DONE]" in all_content

    @pytest.mark.asyncio
    async def test_openai_to_anthropic_stream(self):
        """Test streaming conversion from OpenAI to Anthropic."""
        openai_chunks = [
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": "gpt-4o-mini",
                "choices": [
                    {"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}
                ],
            },
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": "gpt-4o-mini",
                "choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-123",
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": "gpt-4o-mini",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ]

        async def upstream():
            for chunk in openai_chunks:
                yield f"data: {json.dumps(chunk)}\n\n".encode()
            yield b"data: [DONE]\n\n"

        output_chunks = []
        async for chunk in convert_stream(
            source_protocol="openai",
            target_protocol="anthropic",
            upstream=upstream(),
            model="claude-3-5-sonnet-20241022",
        ):
            output_chunks.append(chunk)

        # Verify we got output
        assert len(output_chunks) > 0

        # Parse and verify chunks
        all_content = b"".join(output_chunks).decode()
        assert "message_start" in all_content
        assert "message_stop" in all_content

    @pytest.mark.asyncio
    async def test_same_protocol_stream_passthrough(self):
        """Test that same protocol streams pass through unchanged."""
        original_chunks = [
            b"data: {\"id\": \"1\", \"choices\": [{\"delta\": {\"content\": \"Hi\"}}]}\n\n",
            b"data: [DONE]\n\n",
        ]

        async def upstream():
            for chunk in original_chunks:
                yield chunk

        output_chunks = []
        async for chunk in convert_stream(
            source_protocol="openai",
            target_protocol="openai",
            upstream=upstream(),
            model="gpt-4o-mini",
        ):
            output_chunks.append(chunk)

        assert output_chunks == original_chunks


class TestConversionErrors:
    """Test error handling in conversions."""

    def setup_method(self):
        reset_registry()

    def test_conversion_result_dataclass(self):
        result = ConversionResult(
            path="/v1/chat/completions",
            body={"model": "test"},
        )
        assert result.path == "/v1/chat/completions"
        assert result.body == {"model": "test"}
        assert result.headers == {}

    def test_unsupported_conversion_error(self):
        error = UnsupportedConversionError("invalid", "invalid2")
        assert "invalid" in str(error)
        assert "invalid2" in str(error)
        assert error.code == "unsupported_protocol_conversion"

    def test_validation_error(self):
        error = ValidationError(
            field="max_tokens",
            message="must be positive",
            expected="integer > 0",
        )
        assert "max_tokens" in str(error)
        assert error.field == "max_tokens"
        assert error.expected == "integer > 0"


class TestEndToEndConversion:
    """End-to-end conversion tests simulating real-world scenarios."""

    def setup_method(self):
        reset_registry()

    def test_multipart_conversation(self):
        """Test conversion of a multi-turn conversation."""
        result = convert_request(
            source_protocol="openai",
            target_protocol="anthropic",
            path="/v1/chat/completions",
            body={
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What is Python?"},
                    {
                        "role": "assistant",
                        "content": "Python is a programming language.",
                    },
                    {"role": "user", "content": "What can I do with it?"},
                ],
            },
            target_model="claude-3-5-sonnet-20241022",
        )

        # Should have system as separate field and messages without system
        assert "messages" in result.body
        # User and assistant messages only
        user_messages = [m for m in result.body["messages"] if m.get("role") == "user"]
        assistant_messages = [
            m for m in result.body["messages"] if m.get("role") == "assistant"
        ]
        assert len(user_messages) == 2
        assert len(assistant_messages) == 1

    def test_roundtrip_conversion(self):
        """Test that request -> response conversion maintains data integrity."""
        # OpenAI request
        openai_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
        }

        # Convert to Anthropic
        anthropic_result = convert_request(
            source_protocol="openai",
            target_protocol="anthropic",
            path="/v1/chat/completions",
            body=openai_request,
            target_model="claude-3-5-sonnet-20241022",
        )

        # Simulate Anthropic response
        anthropic_response = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-20241022",
            "content": [{"type": "text", "text": "Hello! How can I help you?"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 8},
        }

        # Convert response back to OpenAI format
        openai_response = convert_response(
            source_protocol="anthropic",
            target_protocol="openai",
            body=anthropic_response,
            target_model="gpt-4o-mini",
        )

        # Verify OpenAI format
        assert openai_response["object"] == "chat.completion"
        assert openai_response["choices"][0]["message"]["role"] == "assistant"
        assert (
            openai_response["choices"][0]["message"]["content"]
            == "Hello! How can I help you?"
        )
