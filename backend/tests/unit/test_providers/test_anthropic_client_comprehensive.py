"""
Comprehensive Unit Tests for Anthropic Protocol Client

Tests all functionality of the Anthropic client including:
- URL construction
- Header preparation (x-api-key, anthropic-version)
- Body preparation
- Request forwarding
- Streaming
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.anthropic_client import AnthropicClient
from app.providers.base import ProviderResponse


class TestAnthropicClientURLConstruction:
    """Test URL construction logic."""

    @pytest.mark.asyncio
    async def test_url_construction_base_with_v1_path_with_v1(self):
        """Test: base_url with /v1, path with /v1 -> avoids double /v1."""
        client = AnthropicClient()
        base_url = "https://api.anthropic.com/v1"
        path = "/v1/messages"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url=base_url,
                api_key="sk-ant-test",
                path=path,
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["url"] == "https://api.anthropic.com/v1/messages"

    @pytest.mark.asyncio
    async def test_url_construction_base_without_v1_path_with_v1(self):
        """Test: base_url without /v1, path with /v1 -> strips /v1 from path."""
        client = AnthropicClient()
        base_url = "https://api.anthropic.com"
        path = "/v1/messages"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url=base_url,
                api_key="sk-ant-test",
                path=path,
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["url"] == "https://api.anthropic.com/messages"

    @pytest.mark.asyncio
    async def test_url_construction_trailing_slash_removal(self):
        """Test: trailing slashes are properly handled."""
        client = AnthropicClient()
        base_url = "https://api.anthropic.com/v1/"
        path = "/v1/messages"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url=base_url,
                api_key="sk-ant-test",
                path=path,
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["url"] == "https://api.anthropic.com/v1/messages"

    @pytest.mark.asyncio
    async def test_url_construction_custom_base_url(self):
        """Test: custom base URL (e.g., AWS Bedrock, Google Vertex AI)."""
        client = AnthropicClient()
        base_url = "https://bedrock-runtime.us-east-1.amazonaws.com/model/anthropic.claude-v2/invoke"
        path = "/v1/messages"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url=base_url,
                api_key="aws-credentials",
                path=path,
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            # /v1 should be stripped from path
            assert (
                call_args.kwargs["url"]
                == "https://bedrock-runtime.us-east-1.amazonaws.com/model/anthropic.claude-v2/invoke/messages"
            )


class TestAnthropicClientHeaders:
    """Test header preparation logic."""

    @pytest.mark.asyncio
    async def test_x_api_key_header_set(self):
        """Test: x-api-key header is set (Anthropic style auth)."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-api-key-123",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["headers"]["x-api-key"] == "sk-ant-api-key-123"

    @pytest.mark.asyncio
    async def test_anthropic_version_header_set(self):
        """Test: anthropic-version header is set with default value."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["headers"]["anthropic-version"] == "2023-06-01"

    @pytest.mark.asyncio
    async def test_anthropic_version_preserved_if_provided(self):
        """Test: anthropic-version header is preserved if already provided."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={"anthropic-version": "2024-01-01"},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            # Should use the provided version, not the default
            assert call_args.kwargs["headers"]["anthropic-version"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_original_auth_headers_removed(self):
        """Test: Original authorization headers are removed."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-provider-key",
                path="/v1/messages",
                method="POST",
                headers={
                    "authorization": "Bearer sk-client-key",
                    "x-api-key": "client-api-key",
                    "api-key": "another-key",
                },
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            headers = call_args.kwargs["headers"]
            # Original client keys should be removed
            assert "authorization" not in headers
            assert "api-key" not in headers
            # Provider key should be set via x-api-key
            assert headers["x-api-key"] == "sk-ant-provider-key"

    @pytest.mark.asyncio
    async def test_content_length_and_host_removed(self):
        """Test: content-length and host headers are removed."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={
                    "content-length": "500",
                    "host": "gateway.example.com",
                    "Content-Type": "application/json",
                    "accept": "application/json",
                },
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            headers = call_args.kwargs["headers"]
            assert "content-length" not in headers
            assert "host" not in headers
            # Accept should be preserved
            assert headers["accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_extra_headers_merged(self):
        """Test: extra_headers are merged into request headers."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
                extra_headers={
                    "X-Custom-Header": "custom-value",
                    "anthropic-beta": "prompt-caching-2024-07-31",
                },
            )

            call_args = mock_client.request.call_args
            headers = call_args.kwargs["headers"]
            assert headers["X-Custom-Header"] == "custom-value"
            assert headers["anthropic-beta"] == "prompt-caching-2024-07-31"


class TestAnthropicClientBody:
    """Test body preparation logic."""

    @pytest.mark.asyncio
    async def test_model_replaced_in_body(self):
        """Test: model field is replaced with target_model."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={
                    "model": "claude-requested",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": "Hi"}],
                },
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            body = call_args.kwargs["json"]
            assert body["model"] == "claude-3-5-sonnet-20241022"
            assert body["max_tokens"] == 1024
            assert body["messages"] == [{"role": "user", "content": "Hi"}]

    @pytest.mark.asyncio
    async def test_other_fields_preserved(self):
        """Test: other fields in body are preserved unchanged."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            original_body = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": "Hello"}],
                "system": "You are helpful.",
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "stop_sequences": ["END"],
                "stream": False,
                "tools": [{"name": "test", "input_schema": {"type": "object"}}],
            }

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body=original_body,
                target_model="claude-3-5-sonnet-20241022",
            )

            call_args = mock_client.request.call_args
            body = call_args.kwargs["json"]
            assert body["max_tokens"] == 2048
            assert body["system"] == "You are helpful."
            assert body["temperature"] == 0.7
            assert body["top_p"] == 0.9
            assert body["top_k"] == 40
            assert body["stop_sequences"] == ["END"]
            assert body["stream"] is False
            assert body["tools"] == [{"name": "test", "input_schema": {"type": "object"}}]


class TestAnthropicClientResponseModes:
    """Test response mode handling."""

    @pytest.mark.asyncio
    async def test_parsed_response_mode(self):
        """Test: parsed mode returns JSON object."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock(
                status_code=200,
                headers={"content-type": "application/json"},
                text='{"id": "msg_123", "type": "message", "content": []}',
            )
            mock_response.json.return_value = {
                "id": "msg_123",
                "type": "message",
                "content": [],
            }
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
                response_mode="parsed",
            )

            assert isinstance(resp, ProviderResponse)
            assert resp.status_code == 200
            assert resp.body == {"id": "msg_123", "type": "message", "content": []}

    @pytest.mark.asyncio
    async def test_raw_response_mode(self):
        """Test: raw mode returns bytes."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock(
                status_code=200,
                headers={"content-type": "application/json"},
                content=b'{"id": "msg_123", "type": "message"}',
            )
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
                response_mode="raw",
            )

            assert isinstance(resp, ProviderResponse)
            assert resp.status_code == 200
            assert resp.body == b'{"id": "msg_123", "type": "message"}'


class TestAnthropicClientErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test: timeout errors are handled correctly."""
        client = AnthropicClient()
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("Connection timed out")
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            assert resp.status_code == 504
            assert "timeout" in resp.error.lower()

    @pytest.mark.asyncio
    async def test_request_error(self):
        """Test: request errors (network issues) are handled correctly."""
        client = AnthropicClient()
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.RequestError("Network error")
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            assert resp.status_code == 502
            assert "error" in resp.error.lower()

    @pytest.mark.asyncio
    async def test_unexpected_error(self):
        """Test: unexpected errors are handled correctly."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = ValueError("Unexpected error")
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            assert resp.status_code == 500
            assert "unexpected" in resp.error.lower()


class TestAnthropicClientStreaming:
    """Test streaming functionality."""

    @pytest.mark.asyncio
    async def test_streaming_chunks_yielded(self):
        """Test: streaming chunks are yielded correctly."""
        client = AnthropicClient()

        async def mock_aiter_bytes():
            yield b'event: message_start\ndata: {"type": "message_start"}\n\n'
            yield b'event: content_block_delta\ndata: {"type": "content_block_delta", "delta": {"text": "Hi"}}\n\n'
            yield b'event: message_stop\ndata: {"type": "message_stop"}\n\n'

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            # Setup for stream: client.stream should be a MagicMock
            mock_client.stream = MagicMock()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}
            mock_response.aiter_bytes.return_value = mock_aiter_bytes()

            # Setup async context manager
            mock_stream_ctx = MagicMock()
            mock_stream_ctx.__aenter__.return_value = mock_response
            mock_stream_ctx.__aexit__.return_value = None
            mock_client.stream.return_value = mock_stream_ctx

            mock_client_cls.return_value.__aenter__.return_value = mock_client

            chunks = []
            async for chunk, resp in client.forward_stream(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": [], "stream": True},
                target_model="claude-3-5-sonnet-20241022",
            ):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert b"message_start" in chunks[0]
            assert b"content_block_delta" in chunks[1]
            assert b"message_stop" in chunks[2]

    @pytest.mark.asyncio
    async def test_streaming_with_tool_use(self):
        """Test: streaming with tool use events."""
        client = AnthropicClient()

        async def mock_aiter_bytes():
            yield b'event: message_start\ndata: {"type": "message_start"}\n\n'
            yield b'event: content_block_start\ndata: {"type": "content_block_start", "content_block": {"type": "tool_use", "name": "get_weather"}}\n\n'
            yield b'event: content_block_delta\ndata: {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": "{\\"location\\""}}\n\n'
            yield b'event: content_block_stop\ndata: {"type": "content_block_stop"}\n\n'
            yield b'event: message_stop\ndata: {"type": "message_stop"}\n\n'

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            # Setup for stream: client.stream should be a MagicMock
            mock_client.stream = MagicMock()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "text/event-stream"}
            mock_response.aiter_bytes.return_value = mock_aiter_bytes()

            # Setup async context manager
            mock_stream_ctx = MagicMock()
            mock_stream_ctx.__aenter__.return_value = mock_response
            mock_stream_ctx.__aexit__.return_value = None
            mock_client.stream.return_value = mock_stream_ctx

            mock_client_cls.return_value.__aenter__.return_value = mock_client

            chunks = []
            async for chunk, resp in client.forward_stream(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={
                    "model": "claude-3-5-sonnet-20241022",
                    "max_tokens": 1024,
                    "messages": [],
                    "stream": True,
                    "tools": [{"name": "get_weather"}],
                },
                target_model="claude-3-5-sonnet-20241022",
            ):
                chunks.append(chunk)

            assert len(chunks) == 5
            assert b"tool_use" in chunks[1]
            assert b"input_json_delta" in chunks[2]

    @pytest.mark.asyncio
    async def test_streaming_timeout_error(self):
        """Test: streaming timeout errors are handled."""
        client = AnthropicClient()
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            # Setup stream to raise timeout exception
            mock_client.stream = MagicMock()

            mock_stream_ctx = MagicMock()
            mock_stream_ctx.__aenter__.side_effect = httpx.TimeoutException("Stream timed out")
            mock_client.stream.return_value = mock_stream_ctx

            mock_client_cls.return_value.__aenter__.return_value = mock_client

            chunks = []
            async for chunk, resp in client.forward_stream(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": [], "stream": True},
                target_model="claude-3-5-sonnet-20241022",
            ):
                chunks.append((chunk, resp))

            # Should yield one error response
            assert len(chunks) == 1
            assert chunks[0][1].status_code == 504

    @pytest.mark.asyncio
    async def test_streaming_request_error(self):
        """Test: streaming request errors are handled."""
        client = AnthropicClient()
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            # Setup stream to raise request error
            mock_client.stream = MagicMock()

            mock_stream_ctx = MagicMock()
            mock_stream_ctx.__aenter__.side_effect = httpx.RequestError("Connection failed")
            mock_client.stream.return_value = mock_stream_ctx

            mock_client_cls.return_value.__aenter__.return_value = mock_client

            chunks = []
            async for chunk, resp in client.forward_stream(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": [], "stream": True},
                target_model="claude-3-5-sonnet-20241022",
            ):
                chunks.append((chunk, resp))

            # Should yield one error response
            assert len(chunks) == 1
            assert chunks[0][1].status_code == 502


class TestAnthropicClientProxy:
    """Test proxy configuration."""

    @pytest.mark.asyncio
    async def test_proxy_config_used(self):
        """Test: proxy configuration is passed to httpx client."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
                proxy_config={"all://": "http://proxy.example.com:8080"},
            )

            # Verify proxy was passed to AsyncClient constructor
            mock_client_cls.assert_called_once()
            call_kwargs = mock_client_cls.call_args.kwargs
            assert call_kwargs["proxy"] == "http://proxy.example.com:8080"


class TestAnthropicClientTimingMetrics:
    """Test timing metrics are captured."""

    @pytest.mark.asyncio
    async def test_timing_metrics_captured(self):
        """Test: timing metrics (first_byte_delay_ms, total_time_ms) are captured."""
        client = AnthropicClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "msg_123"}',
                json=lambda: {"id": "msg_123"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.anthropic.com",
                api_key="sk-ant-test",
                path="/v1/messages",
                method="POST",
                headers={},
                body={"model": "claude-3-5-sonnet-20241022", "max_tokens": 1024, "messages": []},
                target_model="claude-3-5-sonnet-20241022",
            )

            # Timing metrics should be set (they will be small in tests)
            assert resp.first_byte_delay_ms is not None
            assert resp.total_time_ms is not None
            assert resp.first_byte_delay_ms >= 0
            assert resp.total_time_ms >= resp.first_byte_delay_ms
