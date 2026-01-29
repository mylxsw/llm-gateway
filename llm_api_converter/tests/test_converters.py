"""
Unit Tests for Protocol Converters

Tests all 6 conversion directions for requests, responses, and streams.
"""

import json
import sys
from typing import Any, Dict, List

import pytest

sys.path.insert(0, "/home/user/playground")

from api_protocol_converter import (
    Protocol,
    anthropic_messages_to_openai_chat_request,
    anthropic_messages_to_openai_chat_response,
    anthropic_messages_to_openai_responses_request,
    anthropic_messages_to_openai_responses_response,
    convert_request,
    convert_response,
    convert_stream,
    openai_chat_to_anthropic_messages_request,
    openai_chat_to_anthropic_messages_response,
    openai_chat_to_openai_responses_request,
    openai_chat_to_openai_responses_response,
    openai_responses_to_anthropic_messages_request,
    openai_responses_to_anthropic_messages_response,
    openai_responses_to_openai_chat_request,
    openai_responses_to_openai_chat_response,
)
from api_protocol_converter.converters.exceptions import (
    CapabilityNotSupportedError,
    ConversionError,
    ValidationError,
)
from tests.fixtures import (
    ANTHROPIC_MULTI_TOOL_USE_RESPONSE,
    ANTHROPIC_MULTIMODAL_REQUEST,
    # Anthropic fixtures
    ANTHROPIC_SIMPLE_REQUEST,
    ANTHROPIC_SIMPLE_RESPONSE,
    ANTHROPIC_STREAM_EVENTS,
    ANTHROPIC_TOOL_RESULT_REQUEST,
    ANTHROPIC_TOOL_USE_RESPONSE,
    ANTHROPIC_WITH_BASE64_IMAGE_REQUEST,
    ANTHROPIC_WITH_SYSTEM_REQUEST,
    ANTHROPIC_WITH_TOOLS_REQUEST,
    # Complex fixtures
    OPENAI_CHAT_MULTI_TOOL_CALLS_RESPONSE,
    OPENAI_CHAT_MULTIMODAL_REQUEST,
    # OpenAI Chat fixtures
    OPENAI_CHAT_SIMPLE_REQUEST,
    OPENAI_CHAT_SIMPLE_RESPONSE,
    OPENAI_CHAT_STREAM_CHUNKS,
    OPENAI_CHAT_TOOL_CALL_RESPONSE,
    OPENAI_CHAT_TOOL_CALL_RESPONSE_WRONG_FINISH_REASON,
    OPENAI_CHAT_TOOL_RESULT_REQUEST,
    OPENAI_CHAT_WITH_BASE64_IMAGE_REQUEST,
    OPENAI_CHAT_WITH_SYSTEM_REQUEST,
    OPENAI_CHAT_WITH_TOOLS_REQUEST,
    # OpenAI Responses fixtures
    OPENAI_RESPONSES_MULTIMODAL_REQUEST,
    OPENAI_RESPONSES_SIMPLE_REQUEST,
    OPENAI_RESPONSES_SIMPLE_RESPONSE,
    OPENAI_RESPONSES_TOOL_CALL_RESPONSE,
    OPENAI_RESPONSES_WITH_INSTRUCTIONS_REQUEST,
    OPENAI_RESPONSES_WITH_TOOLS_REQUEST,
)

# =============================================================================
# OpenAI Chat -> OpenAI Responses Tests
# =============================================================================


class TestOpenAIChatToOpenAIResponses:
    """Tests for OpenAI Chat -> OpenAI Responses conversion."""

    def test_simple_request(self):
        """Test simple text request conversion."""
        result = openai_chat_to_openai_responses_request(OPENAI_CHAT_SIMPLE_REQUEST)

        assert result["model"] == "gpt-4o"
        assert result["max_output_tokens"] == 100
        # Input should be converted
        assert "input" in result

    def test_request_with_system(self):
        """Test request with system prompt conversion."""
        result = openai_chat_to_openai_responses_request(
            OPENAI_CHAT_WITH_SYSTEM_REQUEST
        )

        assert result["model"] == "gpt-4o"
        assert result["instructions"] == "You are a helpful assistant."
        assert result["temperature"] == 0.7

    def test_request_with_tools(self):
        """Test request with tools conversion."""
        result = openai_chat_to_openai_responses_request(OPENAI_CHAT_WITH_TOOLS_REQUEST)

        assert "tools" in result
        assert len(result["tools"]) == 1
        tool = result["tools"][0]
        assert tool["type"] == "function"
        assert tool["name"] == "get_weather"
        # In Responses API, parameters are at top level, not nested under function
        assert "parameters" in tool

    def test_simple_response(self):
        """Test simple response conversion."""
        result = openai_chat_to_openai_responses_response(OPENAI_CHAT_SIMPLE_RESPONSE)

        assert result["object"] == "response"
        assert "output" in result
        assert result["status"] == "completed"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 15

    def test_tool_call_response(self):
        """Test tool call response conversion."""
        result = openai_chat_to_openai_responses_response(
            OPENAI_CHAT_TOOL_CALL_RESPONSE
        )

        assert "output" in result
        # Should have function_call in output
        function_calls = [o for o in result["output"] if o["type"] == "function_call"]
        assert len(function_calls) == 1
        assert function_calls[0]["name"] == "get_weather"


# =============================================================================
# OpenAI Chat -> Anthropic Messages Tests
# =============================================================================


class TestOpenAIChatToAnthropicMessages:
    """Tests for OpenAI Chat -> Anthropic Messages conversion."""

    def test_simple_request(self):
        """Test simple text request conversion."""
        result = openai_chat_to_anthropic_messages_request(OPENAI_CHAT_SIMPLE_REQUEST)

        assert result["model"] == "gpt-4o"
        assert result["max_tokens"] == 100
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

    def test_request_with_system(self):
        """Test request with system prompt conversion."""
        result = openai_chat_to_anthropic_messages_request(
            OPENAI_CHAT_WITH_SYSTEM_REQUEST
        )

        assert result["system"] == "You are a helpful assistant."
        # System message should be extracted, not in messages
        assert all(m["role"] != "system" for m in result["messages"])

    def test_request_with_tools(self):
        """Test request with tools conversion."""
        result = openai_chat_to_anthropic_messages_request(
            OPENAI_CHAT_WITH_TOOLS_REQUEST
        )

        assert "tools" in result
        assert len(result["tools"]) == 1
        tool = result["tools"][0]
        assert tool["name"] == "get_weather"
        # Anthropic uses input_schema instead of parameters
        assert "input_schema" in tool

    def test_multimodal_request(self):
        """Test multimodal (image) request conversion."""
        result = openai_chat_to_anthropic_messages_request(
            OPENAI_CHAT_MULTIMODAL_REQUEST
        )

        content = result["messages"][0]["content"]
        assert isinstance(content, list)
        # Should have text and image blocks
        types = [c["type"] for c in content]
        assert "text" in types
        assert "image" in types

    def test_simple_response(self):
        """Test simple response conversion."""
        result = openai_chat_to_anthropic_messages_response(OPENAI_CHAT_SIMPLE_RESPONSE)

        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["stop_reason"] == "end_turn"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"

    def test_tool_call_response(self):
        """Test tool call response conversion."""
        result = openai_chat_to_anthropic_messages_response(
            OPENAI_CHAT_TOOL_CALL_RESPONSE
        )

        assert result["stop_reason"] == "tool_use"
        tool_uses = [c for c in result["content"] if c["type"] == "tool_use"]
        assert len(tool_uses) == 1
        assert tool_uses[0]["name"] == "get_weather"
        # Anthropic uses input (object) instead of arguments (string)
        assert isinstance(tool_uses[0]["input"], dict)

    def test_tool_call_response_with_wrong_finish_reason(self):
        """Test tool call response conversion when finish_reason is incorrectly set to 'stop'.

        Some OpenAI-compatible providers return finish_reason='stop' even when
        the response contains tool_calls. The converter should detect this and
        set stop_reason='tool_use' in the Anthropic response.
        """
        result = openai_chat_to_anthropic_messages_response(
            OPENAI_CHAT_TOOL_CALL_RESPONSE_WRONG_FINISH_REASON
        )

        # Even though the original finish_reason was "stop", it should be "tool_use"
        assert result["stop_reason"] == "tool_use"
        tool_uses = [c for c in result["content"] if c["type"] == "tool_use"]
        assert len(tool_uses) == 1
        assert tool_uses[0]["name"] == "get_server_status"
        assert isinstance(tool_uses[0]["input"], dict)

    def test_temperature_clamping(self):
        """Test that temperature is clamped to Anthropic's range."""
        request = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "temperature": 1.5,  # Above Anthropic's max of 1.0
        }
        result = openai_chat_to_anthropic_messages_request(request)

        assert result["temperature"] == 1.0  # Clamped


# =============================================================================
# OpenAI Responses -> OpenAI Chat Tests
# =============================================================================


class TestOpenAIResponsesToOpenAIChat:
    """Tests for OpenAI Responses -> OpenAI Chat conversion."""

    def test_simple_request(self):
        """Test simple text request conversion."""
        result = openai_responses_to_openai_chat_request(
            OPENAI_RESPONSES_SIMPLE_REQUEST
        )

        assert result["model"] == "gpt-4o"
        assert result["max_completion_tokens"] == 100
        assert "messages" in result

    def test_multimodal_request_with_input_text_and_input_image(self):
        """Test multimodal request with input_text and input_image types."""
        result = openai_responses_to_openai_chat_request(
            OPENAI_RESPONSES_MULTIMODAL_REQUEST
        )

        assert result["model"] == "gpt-4o"
        assert result["max_completion_tokens"] == 500
        assert "messages" in result
        assert len(result["messages"]) == 1

        # Check message content
        content = result["messages"][0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2

        # Check text block
        text_block = content[0]
        assert text_block["type"] == "text"
        assert text_block["text"] == "What is in this image?"

        # Check image block
        image_block = content[1]
        assert image_block["type"] == "image_url"
        assert image_block["image_url"]["url"] == "https://example.com/image.jpg"

    def test_request_with_instructions(self):
        """Test request with instructions conversion."""
        result = openai_responses_to_openai_chat_request(
            OPENAI_RESPONSES_WITH_INSTRUCTIONS_REQUEST
        )

        # Instructions should become system message
        system_messages = [m for m in result["messages"] if m["role"] == "system"]
        assert len(system_messages) == 1
        assert system_messages[0]["content"] == "You are a helpful assistant."

    def test_request_with_tools(self):
        """Test request with tools conversion."""
        result = openai_responses_to_openai_chat_request(
            OPENAI_RESPONSES_WITH_TOOLS_REQUEST
        )

        assert "tools" in result
        tool = result["tools"][0]
        assert tool["type"] == "function"
        # OpenAI Chat nests under function
        assert "function" in tool
        assert tool["function"]["name"] == "get_weather"

    def test_simple_response(self):
        """Test simple response conversion."""
        result = openai_responses_to_openai_chat_response(
            OPENAI_RESPONSES_SIMPLE_RESPONSE
        )

        assert result["object"] == "chat.completion"
        assert "choices" in result
        assert result["choices"][0]["message"]["role"] == "assistant"
        assert result["choices"][0]["finish_reason"] == "stop"

    def test_tool_call_response(self):
        """Test tool call response conversion."""
        result = openai_responses_to_openai_chat_response(
            OPENAI_RESPONSES_TOOL_CALL_RESPONSE
        )

        message = result["choices"][0]["message"]
        assert "tool_calls" in message
        assert len(message["tool_calls"]) == 1
        assert message["tool_calls"][0]["function"]["name"] == "get_weather"


# =============================================================================
# OpenAI Responses -> Anthropic Messages Tests
# =============================================================================


class TestOpenAIResponsesToAnthropicMessages:
    """Tests for OpenAI Responses -> Anthropic Messages conversion."""

    def test_simple_request(self):
        """Test simple text request conversion."""
        result = openai_responses_to_anthropic_messages_request(
            OPENAI_RESPONSES_SIMPLE_REQUEST
        )

        assert result["model"] == "gpt-4o"
        assert result["max_tokens"] == 100
        assert len(result["messages"]) == 1

    def test_multimodal_request_with_input_text_and_input_image(self):
        """Test multimodal request with input_text and input_image types."""
        result = openai_responses_to_anthropic_messages_request(
            OPENAI_RESPONSES_MULTIMODAL_REQUEST
        )

        assert result["model"] == "gpt-4o"
        assert result["max_tokens"] == 500
        assert len(result["messages"]) == 1

        # Check message content
        content = result["messages"][0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2

        # Check text block
        text_block = content[0]
        assert text_block["type"] == "text"
        assert text_block["text"] == "What is in this image?"

        # Check image block
        image_block = content[1]
        assert image_block["type"] == "image"
        assert image_block["source"]["type"] == "url"
        assert image_block["source"]["url"] == "https://example.com/image.jpg"

    def test_request_with_instructions(self):
        """Test request with instructions conversion."""
        result = openai_responses_to_anthropic_messages_request(
            OPENAI_RESPONSES_WITH_INSTRUCTIONS_REQUEST
        )

        assert result["system"] == "You are a helpful assistant."

    def test_simple_response(self):
        """Test simple response conversion."""
        result = openai_responses_to_anthropic_messages_response(
            OPENAI_RESPONSES_SIMPLE_RESPONSE
        )

        assert result["type"] == "message"
        assert result["stop_reason"] == "end_turn"


# =============================================================================
# Anthropic Messages -> OpenAI Chat Tests
# =============================================================================


class TestAnthropicMessagesToOpenAIChat:
    """Tests for Anthropic Messages -> OpenAI Chat conversion."""

    def test_simple_request(self):
        """Test simple text request conversion."""
        result = anthropic_messages_to_openai_chat_request(ANTHROPIC_SIMPLE_REQUEST)

        assert result["model"] == "claude-3-5-sonnet-20241022"
        assert result["max_completion_tokens"] == 100
        assert len(result["messages"]) == 1

    def test_request_with_system(self):
        """Test request with system prompt conversion."""
        result = anthropic_messages_to_openai_chat_request(
            ANTHROPIC_WITH_SYSTEM_REQUEST
        )

        system_messages = [m for m in result["messages"] if m["role"] == "system"]
        assert len(system_messages) == 1
        assert system_messages[0]["content"] == "You are a helpful assistant."

    def test_request_with_tools(self):
        """Test request with tools conversion."""
        result = anthropic_messages_to_openai_chat_request(ANTHROPIC_WITH_TOOLS_REQUEST)

        assert "tools" in result
        tool = result["tools"][0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "get_weather"
        # parameters instead of input_schema
        assert "parameters" in tool["function"]

    def test_multimodal_request(self):
        """Test multimodal (image) request conversion."""
        result = anthropic_messages_to_openai_chat_request(ANTHROPIC_MULTIMODAL_REQUEST)

        content = result["messages"][0]["content"]
        assert isinstance(content, list)
        types = [c["type"] for c in content]
        assert "text" in types
        assert "image_url" in types

    def test_simple_response(self):
        """Test simple response conversion."""
        result = anthropic_messages_to_openai_chat_response(ANTHROPIC_SIMPLE_RESPONSE)

        assert result["object"] == "chat.completion"
        assert result["choices"][0]["finish_reason"] == "stop"

    def test_tool_use_response(self):
        """Test tool use response conversion."""
        result = anthropic_messages_to_openai_chat_response(ANTHROPIC_TOOL_USE_RESPONSE)

        assert result["choices"][0]["finish_reason"] == "tool_calls"
        message = result["choices"][0]["message"]
        assert "tool_calls" in message
        # Arguments should be JSON string
        assert isinstance(message["tool_calls"][0]["function"]["arguments"], str)


# =============================================================================
# Anthropic Messages -> OpenAI Responses Tests
# =============================================================================


class TestAnthropicMessagesToOpenAIResponses:
    """Tests for Anthropic Messages -> OpenAI Responses conversion."""

    def test_simple_request(self):
        """Test simple text request conversion."""
        result = anthropic_messages_to_openai_responses_request(
            ANTHROPIC_SIMPLE_REQUEST
        )

        assert result["model"] == "claude-3-5-sonnet-20241022"
        assert result["max_output_tokens"] == 100
        # Simple single-message input may be simplified to a string
        assert "input" in result

    def test_multimodal_request_uses_correct_types(self):
        """Test that multimodal user messages use input_text and input_image types."""
        result = anthropic_messages_to_openai_responses_request(
            ANTHROPIC_MULTIMODAL_REQUEST
        )

        # Multimodal requests should always use array format
        assert "input" in result
        assert isinstance(result["input"], list), "Multimodal input should be an array"
        assert len(result["input"]) > 0

        # Find the user message
        user_message = None
        for item in result["input"]:
            if item.get("type") == "message" and item.get("role") == "user":
                user_message = item
                break

        assert user_message is not None, "User message not found in input"
        assert "content" in user_message
        assert isinstance(user_message["content"], list)

        # Check content blocks use the correct types for OpenAI Responses API
        content_types = [block["type"] for block in user_message["content"]]
        assert "input_text" in content_types, (
            f"Expected 'input_text' in content types but got {content_types}"
        )
        assert "input_image" in content_types, (
            f"Expected 'input_image' in content types but got {content_types}"
        )

    def test_request_with_system(self):
        """Test request with system prompt conversion."""
        result = anthropic_messages_to_openai_responses_request(
            ANTHROPIC_WITH_SYSTEM_REQUEST
        )

        assert result["instructions"] == "You are a helpful assistant."

    def test_simple_response(self):
        """Test simple response conversion."""
        result = anthropic_messages_to_openai_responses_response(
            ANTHROPIC_SIMPLE_RESPONSE
        )

        assert result["object"] == "response"
        assert result["status"] == "completed"


# =============================================================================
# Generic Converter Tests
# =============================================================================


class TestGenericConverters:
    """Tests for generic convert_request/convert_response functions."""

    def test_convert_request_with_string_protocol(self):
        """Test convert_request with string protocol identifiers."""
        result = convert_request(
            "openai_chat",
            "anthropic_messages",
            OPENAI_CHAT_SIMPLE_REQUEST,
        )
        assert result["max_tokens"] == 100

    def test_convert_request_with_enum_protocol(self):
        """Test convert_request with Protocol enum."""
        result = convert_request(
            Protocol.OPENAI_CHAT,
            Protocol.ANTHROPIC_MESSAGES,
            OPENAI_CHAT_SIMPLE_REQUEST,
        )
        assert result["max_tokens"] == 100

    def test_convert_response_preserves_content(self):
        """Test that response conversion preserves content."""
        result = convert_response(
            Protocol.OPENAI_CHAT,
            Protocol.ANTHROPIC_MESSAGES,
            OPENAI_CHAT_SIMPLE_RESPONSE,
        )
        assert "Hello! I'm doing great" in result["content"][0]["text"]


# =============================================================================
# Streaming Tests
# =============================================================================


class TestStreamConversion:
    """Tests for stream conversion."""

    def test_openai_chat_to_anthropic_stream(self):
        """Test OpenAI Chat stream to Anthropic stream conversion."""
        result = list(
            convert_stream(
                Protocol.OPENAI_CHAT,
                Protocol.ANTHROPIC_MESSAGES,
                iter(OPENAI_CHAT_STREAM_CHUNKS),
            )
        )

        # Should have message_start, content blocks, and message_stop
        event_types = [e.get("type") for e in result if isinstance(e, dict)]
        assert "message_start" in event_types
        assert "content_block_delta" in event_types

    def test_anthropic_to_openai_chat_stream(self):
        """Test Anthropic stream to OpenAI Chat stream conversion."""
        result = list(
            convert_stream(
                Protocol.ANTHROPIC_MESSAGES,
                Protocol.OPENAI_CHAT,
                iter(ANTHROPIC_STREAM_EVENTS),
            )
        )

        # Should have chunks with delta content
        assert len(result) > 0
        # Check for content deltas
        has_content = any(
            isinstance(e, dict)
            and e.get("choices", [{}])[0].get("delta", {}).get("content")
            for e in result
        )
        assert has_content


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_multi_tool_calls_conversion(self):
        """Test conversion of responses with multiple tool calls."""
        result = openai_chat_to_anthropic_messages_response(
            OPENAI_CHAT_MULTI_TOOL_CALLS_RESPONSE
        )

        tool_uses = [c for c in result["content"] if c["type"] == "tool_use"]
        assert len(tool_uses) == 2

    def test_base64_image_conversion(self):
        """Test conversion of base64 encoded images."""
        result = openai_chat_to_anthropic_messages_request(
            OPENAI_CHAT_WITH_BASE64_IMAGE_REQUEST
        )

        content = result["messages"][0]["content"]
        image_blocks = [c for c in content if c["type"] == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0]["source"]["type"] == "base64"

    def test_anthropic_missing_max_tokens_raises_error(self):
        """Test that missing max_tokens raises ValidationError for Anthropic."""
        request = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            # No max_tokens
        }
        with pytest.raises(ValidationError) as exc_info:
            openai_chat_to_anthropic_messages_request(request)

        assert "max_tokens" in str(exc_info.value)

    def test_empty_content_handling(self):
        """Test handling of empty content in messages."""
        request = {
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": ""},
            ],
            "max_tokens": 100,
        }
        # Should not raise
        result = openai_chat_to_anthropic_messages_request(request)
        assert "messages" in result

    def test_tool_result_conversion(self):
        """Test conversion of tool result messages."""
        result = openai_chat_to_anthropic_messages_request(
            OPENAI_CHAT_TOOL_RESULT_REQUEST
        )

        # Find tool result in messages
        tool_results = []
        for msg in result["messages"]:
            content = msg.get("content", [])
            if isinstance(content, list):
                tool_results.extend(
                    c
                    for c in content
                    if isinstance(c, dict) and c.get("type") == "tool_result"
                )

        assert len(tool_results) == 1
        assert tool_results[0]["tool_use_id"] == "call_abc123"


# =============================================================================
# Round-Trip Tests
# =============================================================================


class TestRoundTrip:
    """Tests for round-trip conversions (A -> B -> A)."""

    def test_openai_chat_round_trip_via_anthropic(self):
        """Test OpenAI Chat -> Anthropic -> OpenAI Chat preserves key fields."""
        # Forward
        anthropic = openai_chat_to_anthropic_messages_request(
            OPENAI_CHAT_WITH_SYSTEM_REQUEST
        )

        # Back
        result = anthropic_messages_to_openai_chat_request(anthropic)

        # Key fields should be preserved
        assert result["model"] == OPENAI_CHAT_WITH_SYSTEM_REQUEST["model"]
        assert (
            result["max_completion_tokens"]
            == OPENAI_CHAT_WITH_SYSTEM_REQUEST["max_tokens"]
        )

        # System prompt should be preserved
        system_messages = [m for m in result["messages"] if m["role"] == "system"]
        assert len(system_messages) == 1

    def test_anthropic_round_trip_via_openai_chat(self):
        """Test Anthropic -> OpenAI Chat -> Anthropic preserves key fields."""
        # Forward
        openai = anthropic_messages_to_openai_chat_request(
            ANTHROPIC_WITH_SYSTEM_REQUEST
        )

        # Back
        result = openai_chat_to_anthropic_messages_request(openai)

        # Key fields should be preserved
        assert result["model"] == ANTHROPIC_WITH_SYSTEM_REQUEST["model"]
        assert result["max_tokens"] == ANTHROPIC_WITH_SYSTEM_REQUEST["max_tokens"]
        assert result["system"] == ANTHROPIC_WITH_SYSTEM_REQUEST["system"]

    def test_response_round_trip(self):
        """Test response round-trip conversion."""
        # Forward
        anthropic = openai_chat_to_anthropic_messages_response(
            OPENAI_CHAT_SIMPLE_RESPONSE
        )

        # Back
        result = anthropic_messages_to_openai_chat_response(anthropic)

        # Content should be preserved
        original_content = OPENAI_CHAT_SIMPLE_RESPONSE["choices"][0]["message"][
            "content"
        ]
        result_content = result["choices"][0]["message"]["content"]
        assert original_content == result_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
