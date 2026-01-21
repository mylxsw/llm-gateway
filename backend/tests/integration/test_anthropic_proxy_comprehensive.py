"""
Comprehensive Integration Tests for Anthropic Proxy API

Tests all Anthropic-compatible endpoints including:
- Messages API (streaming and non-streaming)
- Various content types (text, images, documents)
- Tool use
- Different model parameters

Each test covers different request/response formats as per Anthropic API specification.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_api_key, get_proxy_service
from app.common.time import utc_now
from app.domain.api_key import ApiKeyModel
from app.main import app
from app.providers.base import ProviderResponse


def _make_api_key() -> ApiKeyModel:
    """Create a mock API key for testing."""
    return ApiKeyModel(
        id=1,
        key_name="test-key",
        key_value="sk-ant-test-key-123",
        is_active=True,
        created_at=utc_now(),
        last_used_at=None,
    )


class MockProxyService:
    """Mock proxy service that captures calls and returns configurable responses."""

    def __init__(self, response_body=None, status_code=200, headers=None):
        self.calls = []
        self.response_body = response_body or {"type": "message"}
        self.status_code = status_code
        self.headers = headers or {}

    async def process_request(self, **kwargs):
        self.calls.append(kwargs)
        return ProviderResponse(
            status_code=self.status_code,
            body=self.response_body,
            headers=self.headers,
        ), {}

    async def process_request_stream(self, **kwargs):
        self.calls.append(kwargs)

        async def gen():
            for chunk in self.response_body:
                yield chunk

        return ProviderResponse(
            status_code=self.status_code,
            headers={"Content-Type": "text/event-stream", **self.headers},
        ), gen(), {}


class TestAnthropicMessages:
    """Test cases for /v1/messages endpoint."""

    @pytest.mark.asyncio
    async def test_basic_message(self):
        """Test basic message request."""
        response_body = {
            "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello! How can I help you today?"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 15},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Hello!"}],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "message"
        assert data["role"] == "assistant"
        assert data["content"][0]["type"] == "text"
        assert service.calls[0]["path"] == "/v1/messages"
        assert service.calls[0]["request_protocol"] == "anthropic"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_message_with_system_prompt(self):
        """Test message with system prompt."""
        response_body = {
            "id": "msg_02ABC123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Ahoy, matey! How can this humble pirate assist ye today?"}],
            "model": "claude-3-opus-20240229",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 25, "output_tokens": 20},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-opus-20240229",
                    "max_tokens": 1024,
                    "system": "You are a pirate. Always respond like a pirate.",
                    "messages": [{"role": "user", "content": "Hello!"}],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert "system" in body
        assert "pirate" in body["system"].lower()

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_message_with_multi_turn_conversation(self):
        """Test multi-turn conversation."""
        response_body = {
            "id": "msg_03DEF456",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Your name is Alice, as you mentioned earlier."}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 15},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "user", "content": "My name is Alice."},
                        {"role": "assistant", "content": "Nice to meet you, Alice! How can I help you today?"},
                        {"role": "user", "content": "What is my name?"},
                    ],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert len(body["messages"]) == 3

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_message_with_all_parameters(self):
        """Test message with all optional parameters."""
        response_body = {
            "id": "msg_04GHI789",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Response with all parameters."}],
            "model": "claude-3-haiku-20240307",
            "stop_reason": "stop_sequence",
            "stop_sequence": "END",
            "usage": {"input_tokens": 30, "output_tokens": 10},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40,
                    "stop_sequences": ["END", "STOP"],
                    "metadata": {"user_id": "user-123"},
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["temperature"] == 0.7
        assert body["top_p"] == 0.9
        assert body["top_k"] == 40
        assert body["stop_sequences"] == ["END", "STOP"]

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_message_with_image_content(self):
        """Test message with image content (vision)."""
        response_body = {
            "id": "msg_05JKL012",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "I can see a beautiful landscape in the image."}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 1000, "output_tokens": 20},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What do you see in this image?"},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/jpeg",
                                        "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                                    },
                                },
                            ],
                        }
                    ],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        content = service.calls[0]["body"]["messages"][0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image"
        assert content[1]["source"]["type"] == "base64"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_message_with_image_url(self):
        """Test message with image URL."""
        response_body = {
            "id": "msg_06MNO345",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "I see an image from the URL."}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 500, "output_tokens": 15},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Describe this image:"},
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "url",
                                        "url": "https://example.com/image.jpg",
                                    },
                                },
                            ],
                        }
                    ],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_message_with_tool_use(self):
        """Test message with tool use (function calling)."""
        response_body = {
            "id": "msg_07PQR678",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_01A09q90qw90lq917835lgs",
                    "name": "get_weather",
                    "input": {"location": "San Francisco, CA"},
                }
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 30},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "What's the weather in San Francisco?"}],
                    "tools": [
                        {
                            "name": "get_weather",
                            "description": "Get the current weather in a given location",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "description": "The city and state, e.g. San Francisco, CA",
                                    }
                                },
                                "required": ["location"],
                            },
                        }
                    ],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["stop_reason"] == "tool_use"
        assert data["content"][0]["type"] == "tool_use"
        assert "tools" in service.calls[0]["body"]

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_message_with_tool_result(self):
        """Test message with tool result (continuation after tool use)."""
        response_body = {
            "id": "msg_08STU901",
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "text", "text": "The weather in San Francisco is 68°F and sunny."}
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 100, "output_tokens": 25},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [
                        {"role": "user", "content": "What's the weather in San Francisco?"},
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": "toolu_01A09q90qw90lq917835lgs",
                                    "name": "get_weather",
                                    "input": {"location": "San Francisco, CA"},
                                }
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": "toolu_01A09q90qw90lq917835lgs",
                                    "content": "68°F, sunny",
                                }
                            ],
                        },
                    ],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        messages = service.calls[0]["body"]["messages"]
        assert len(messages) == 3
        # Verify tool_result is in the last user message
        assert messages[2]["content"][0]["type"] == "tool_result"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_message_with_tool_choice(self):
        """Test message with tool_choice parameter."""
        response_body = {
            "id": "msg_09VWX234",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_02B",
                    "name": "get_weather",
                    "input": {"location": "Tokyo"},
                }
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "usage": {"input_tokens": 60, "output_tokens": 25},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Get weather for Tokyo"}],
                    "tools": [
                        {
                            "name": "get_weather",
                            "description": "Get weather",
                            "input_schema": {
                                "type": "object",
                                "properties": {"location": {"type": "string"}},
                            },
                        }
                    ],
                    "tool_choice": {"type": "tool", "name": "get_weather"},
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["tool_choice"]["type"] == "tool"
        assert body["tool_choice"]["name"] == "get_weather"

        app.dependency_overrides = {}


class TestAnthropicStreaming:
    """Test cases for streaming messages."""

    @pytest.mark.asyncio
    async def test_basic_streaming(self):
        """Test basic streaming message."""
        chunks = [
            b'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_stream_1","type":"message","role":"assistant","content":[],"model":"claude-3-5-sonnet-20241022","stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":10,"output_tokens":0}}}\n\n',
            b'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
            b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}\n\n',
            b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}}\n\n',
            b'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            b'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":5}}\n\n',
            b'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]
        service = MockProxyService(response_body=chunks)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": True,
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        assert service.calls[0]["body"]["stream"] is True

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_streaming_with_tool_use(self):
        """Test streaming with tool use."""
        chunks = [
            b'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_stream_tool","type":"message","role":"assistant","content":[],"model":"claude-3-5-sonnet-20241022","stop_reason":null,"stop_sequence":null,"usage":{"input_tokens":50,"output_tokens":0}}}\n\n',
            b'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_stream_1","name":"get_weather","input":{}}}\n\n',
            b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"location\\": \\""}}\n\n',
            b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"NYC\\"}"}}\n\n',
            b'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            b'event: message_delta\ndata: {"type":"message_delta","delta":{"stop_reason":"tool_use","stop_sequence":null},"usage":{"output_tokens":25}}\n\n',
            b'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]
        service = MockProxyService(response_body=chunks)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Weather in NYC?"}],
                    "stream": True,
                    "tools": [
                        {
                            "name": "get_weather",
                            "description": "Get weather",
                            "input_schema": {
                                "type": "object",
                                "properties": {"location": {"type": "string"}},
                            },
                        }
                    ],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["stream"] is True
        assert "tools" in body

        app.dependency_overrides = {}


class TestAnthropicErrorHandling:
    """Test error handling for Anthropic proxy endpoints."""

    @pytest.mark.asyncio
    async def test_authentication_error(self):
        """Test handling of authentication errors."""
        error_response = {
            "type": "error",
            "error": {
                "type": "authentication_error",
                "message": "Invalid API key",
            },
        }
        service = MockProxyService(response_body=error_response, status_code=401)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={
                    "x-api-key": "invalid-key",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 401
        data = response.json()
        assert data["type"] == "error"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_invalid_request_error(self):
        """Test handling of invalid request errors."""
        error_response = {
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "max_tokens must be a positive integer",
            },
        }
        service = MockProxyService(response_body=error_response, status_code=400)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": -1,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 400

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test handling of rate limit errors."""
        error_response = {
            "type": "error",
            "error": {
                "type": "rate_limit_error",
                "message": "Rate limit exceeded. Please retry after 60 seconds.",
            },
        }
        service = MockProxyService(
            response_body=error_response,
            status_code=429,
            headers={"retry-after": "60"},
        )
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 429

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_overloaded_error(self):
        """Test handling of overloaded errors."""
        error_response = {
            "type": "error",
            "error": {
                "type": "overloaded_error",
                "message": "Anthropic API is temporarily overloaded. Please try again later.",
            },
        }
        service = MockProxyService(response_body=error_response, status_code=529)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 529

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_api_error(self):
        """Test handling of generic API errors."""
        error_response = {
            "type": "error",
            "error": {
                "type": "api_error",
                "message": "An unexpected error occurred.",
            },
        }
        service = MockProxyService(response_body=error_response, status_code=500)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 500

        app.dependency_overrides = {}


class TestAnthropicSpecialFeatures:
    """Test special features of the Anthropic API."""

    @pytest.mark.asyncio
    async def test_extended_thinking(self):
        """Test extended thinking feature (thinking blocks)."""
        response_body = {
            "id": "msg_thinking_1",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "Let me think about this step by step...",
                },
                {
                    "type": "text",
                    "text": "Based on my analysis, the answer is 42.",
                },
            ],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 20, "output_tokens": 100},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 16000,
                    "messages": [{"role": "user", "content": "What is the meaning of life?"}],
                    "thinking": {
                        "type": "enabled",
                        "budget_tokens": 10000,
                    },
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
            )

        assert response.status_code == 200
        data = response.json()
        # Verify response contains thinking block
        assert data["content"][0]["type"] == "thinking"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_cache_control(self):
        """Test prompt caching feature."""
        response_body = {
            "id": "msg_cache_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Response with caching."}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 0,
            },
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "system": [
                        {
                            "type": "text",
                            "text": "You are a helpful assistant with a lot of context.",
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": [{"role": "user", "content": "Hello"}],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "prompt-caching-2024-07-31",
                },
            )

        assert response.status_code == 200
        # Verify cache-related usage is returned
        data = response.json()
        assert "cache_creation_input_tokens" in data["usage"]

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_document_content(self):
        """Test PDF document content (vision feature)."""
        response_body = {
            "id": "msg_doc_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "I analyzed the document..."}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 2000, "output_tokens": 50},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Summarize this document:"},
                                {
                                    "type": "document",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "application/pdf",
                                        "data": "JVBERi0xLjcKCjEgMCBvYmoKPDwKL1R5cGUgL0NhdGFsb2cKPj4KZW5kb2Jq...",
                                    },
                                },
                            ],
                        }
                    ],
                },
                headers={
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "pdfs-2024-09-25",
                },
            )

        assert response.status_code == 200

        app.dependency_overrides = {}
