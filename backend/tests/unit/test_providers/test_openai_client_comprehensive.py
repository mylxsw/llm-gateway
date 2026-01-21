"""
Comprehensive Unit Tests for OpenAI Protocol Client

Tests all functionality of the OpenAI client including:
- URL construction
- Header preparation
- Body preparation
- Request forwarding
- Streaming
- Error handling
- Multipart handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.openai_client import OpenAIClient
from app.providers.base import ProviderResponse


class TestOpenAIClientURLConstruction:
    """Test URL construction logic."""

    @pytest.mark.asyncio
    async def test_url_construction_base_without_v1_path_with_v1(self):
        """Test: base_url without /v1, path with /v1 -> strips /v1 from path."""
        client = OpenAIClient()
        base_url = "https://api.openai.com"
        path = "/v1/chat/completions"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url=base_url,
                api_key="sk-test",
                path=path,
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["url"] == "https://api.openai.com/chat/completions"

    @pytest.mark.asyncio
    async def test_url_construction_base_with_v1_path_with_v1(self):
        """Test: base_url with /v1, path with /v1 -> avoids double /v1."""
        client = OpenAIClient()
        base_url = "https://api.openai.com/v1"
        path = "/v1/chat/completions"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url=base_url,
                api_key="sk-test",
                path=path,
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["url"] == "https://api.openai.com/v1/chat/completions"

    @pytest.mark.asyncio
    async def test_url_construction_trailing_slash_removal(self):
        """Test: trailing slashes are properly handled."""
        client = OpenAIClient()
        base_url = "https://api.openai.com/v1/"
        path = "/v1/embeddings"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"data": []}',
                json=lambda: {"data": []},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url=base_url,
                api_key="sk-test",
                path=path,
                method="POST",
                headers={},
                body={"model": "text-embedding-ada-002", "input": "hello"},
                target_model="text-embedding-ada-002",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["url"] == "https://api.openai.com/v1/embeddings"

    @pytest.mark.asyncio
    async def test_url_construction_custom_base_url(self):
        """Test: custom base URL (e.g., Azure OpenAI)."""
        client = OpenAIClient()
        base_url = "https://myresource.openai.azure.com/openai/deployments/gpt-4"
        path = "/v1/chat/completions"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url=base_url,
                api_key="api-key",
                path=path,
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            call_args = mock_client.request.call_args
            # /v1 should be stripped from path
            assert (
                call_args.kwargs["url"]
                == "https://myresource.openai.azure.com/openai/deployments/gpt-4/chat/completions"
            )


class TestOpenAIClientHeaders:
    """Test header preparation logic."""

    @pytest.mark.asyncio
    async def test_authorization_header_set(self):
        """Test: Authorization header is set with Bearer token."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test-key-123",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            call_args = mock_client.request.call_args
            assert call_args.kwargs["headers"]["Authorization"] == "Bearer sk-test-key-123"

    @pytest.mark.asyncio
    async def test_original_auth_headers_removed(self):
        """Test: Original authorization headers are removed."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-provider-key",
                path="/v1/chat/completions",
                method="POST",
                headers={
                    "Authorization": "Bearer sk-client-key",
                    "x-api-key": "client-api-key",
                    "api-key": "another-key",
                },
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            call_args = mock_client.request.call_args
            headers = call_args.kwargs["headers"]
            # Original keys should be replaced with provider key
            assert headers["Authorization"] == "Bearer sk-provider-key"
            assert "x-api-key" not in headers
            assert "api-key" not in headers

    @pytest.mark.asyncio
    async def test_content_length_and_host_removed(self):
        """Test: content-length and host headers are removed."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={
                    "content-length": "123",
                    "host": "gateway.example.com",
                    "Content-Type": "application/json",
                },
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            call_args = mock_client.request.call_args
            headers = call_args.kwargs["headers"]
            assert "content-length" not in headers
            assert "host" not in headers

    @pytest.mark.asyncio
    async def test_extra_headers_merged(self):
        """Test: extra_headers are merged into request headers."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
                extra_headers={"X-Custom-Header": "custom-value", "api-version": "2024-01-01"},
            )

            call_args = mock_client.request.call_args
            headers = call_args.kwargs["headers"]
            assert headers["X-Custom-Header"] == "custom-value"
            assert headers["api-version"] == "2024-01-01"


class TestOpenAIClientBody:
    """Test body preparation logic."""

    @pytest.mark.asyncio
    async def test_model_replaced_in_body(self):
        """Test: model field is replaced with target_model."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4-requested", "messages": [{"role": "user", "content": "Hi"}]},
                target_model="gpt-4-actual",
            )

            call_args = mock_client.request.call_args
            body = call_args.kwargs["json"]
            assert body["model"] == "gpt-4-actual"
            assert body["messages"] == [{"role": "user", "content": "Hi"}]

    @pytest.mark.asyncio
    async def test_other_fields_preserved(self):
        """Test: other fields in body are preserved unchanged."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            original_body = {
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hi"}],
                "temperature": 0.7,
                "max_tokens": 100,
                "tools": [{"type": "function", "function": {"name": "test"}}],
                "stream": False,
            }

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body=original_body,
                target_model="gpt-4",
            )

            call_args = mock_client.request.call_args
            body = call_args.kwargs["json"]
            assert body["temperature"] == 0.7
            assert body["max_tokens"] == 100
            assert body["tools"] == [{"type": "function", "function": {"name": "test"}}]
            assert body["stream"] is False


class TestOpenAIClientResponseModes:
    """Test response mode handling."""

    @pytest.mark.asyncio
    async def test_parsed_response_mode(self):
        """Test: parsed mode returns JSON object."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock(
                status_code=200,
                headers={"content-type": "application/json"},
                text='{"id": "chatcmpl-123", "choices": []}',
            )
            mock_response.json.return_value = {"id": "chatcmpl-123", "choices": []}
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
                response_mode="parsed",
            )

            assert isinstance(resp, ProviderResponse)
            assert resp.status_code == 200
            assert resp.body == {"id": "chatcmpl-123", "choices": []}

    @pytest.mark.asyncio
    async def test_raw_response_mode(self):
        """Test: raw mode returns bytes."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock(
                status_code=200,
                headers={"content-type": "audio/mpeg"},
                content=b"audio binary data",
            )
            mock_client.request.return_value = mock_response
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/audio/speech",
                method="POST",
                headers={},
                body={"model": "tts-1", "input": "Hello", "voice": "alloy"},
                target_model="tts-1",
                response_mode="raw",
            )

            assert isinstance(resp, ProviderResponse)
            assert resp.status_code == 200
            assert resp.body == b"audio binary data"


class TestOpenAIClientMultipart:
    """Test multipart request handling."""

    @pytest.mark.asyncio
    async def test_multipart_files_sent_correctly(self):
        """Test: multipart files are sent correctly."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"text": "transcription"}',
                json=lambda: {"text": "transcription"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/audio/transcriptions",
                method="POST",
                headers={},
                body={
                    "model": "whisper-1",
                    "language": "en",
                    "_files": [
                        {
                            "field": "file",
                            "filename": "audio.wav",
                            "content_type": "audio/wav",
                            "data": b"audio content",
                        }
                    ],
                },
                target_model="whisper-1",
            )

            call_args = mock_client.request.call_args
            assert "files" in call_args.kwargs
            assert "data" in call_args.kwargs
            # Verify files tuple structure
            files = call_args.kwargs["files"]
            assert files[0][0] == "file"
            assert files[0][1][0] == "audio.wav"
            assert files[0][1][1] == b"audio content"
            assert files[0][1][2] == "audio/wav"

    @pytest.mark.asyncio
    async def test_multipart_data_fields_sent_correctly(self):
        """Test: multipart data fields are sent correctly."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"text": "transcription"}',
                json=lambda: {"text": "transcription"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/audio/transcriptions",
                method="POST",
                headers={},
                body={
                    "model": "whisper-1",
                    "language": "en",
                    "prompt": "Previous text",
                    "response_format": "json",
                    "_files": [
                        {
                            "field": "file",
                            "filename": "audio.wav",
                            "content_type": "audio/wav",
                            "data": b"audio content",
                        }
                    ],
                },
                target_model="whisper-1",
            )

            call_args = mock_client.request.call_args
            data = call_args.kwargs["data"]
            # Data should be list of tuples
            data_dict = dict(data)
            assert data_dict["model"] == "whisper-1"
            assert data_dict["language"] == "en"
            assert data_dict["prompt"] == "Previous text"
            assert data_dict["response_format"] == "json"


class TestOpenAIClientErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test: timeout errors are handled correctly."""
        client = OpenAIClient()
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("Connection timed out")
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            assert resp.status_code == 504
            assert "timeout" in resp.error.lower()

    @pytest.mark.asyncio
    async def test_request_error(self):
        """Test: request errors (network issues) are handled correctly."""
        client = OpenAIClient()
        import httpx

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.RequestError("Network error")
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            assert resp.status_code == 502
            assert "error" in resp.error.lower()

    @pytest.mark.asyncio
    async def test_unexpected_error(self):
        """Test: unexpected errors are handled correctly."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.side_effect = ValueError("Unexpected error")
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            resp = await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
            )

            assert resp.status_code == 500
            assert "unexpected" in resp.error.lower()


class TestOpenAIClientStreaming:
    """Test streaming functionality."""

    @pytest.mark.asyncio
    async def test_streaming_chunks_yielded(self):
        """Test: streaming chunks are yielded correctly."""
        client = OpenAIClient()

        async def mock_aiter_bytes():
            yield b'data: {"id": "chunk1"}\n\n'
            yield b'data: {"id": "chunk2"}\n\n'
            yield b"data: [DONE]\n\n"

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
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4", "stream": True},
                target_model="gpt-4",
            ):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert chunks[0] == b'data: {"id": "chunk1"}\n\n'
            assert chunks[1] == b'data: {"id": "chunk2"}\n\n'
            assert chunks[2] == b"data: [DONE]\n\n"

    @pytest.mark.asyncio
    async def test_streaming_timeout_error(self):
        """Test: streaming timeout errors are handled."""
        client = OpenAIClient()
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
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4", "stream": True},
                target_model="gpt-4",
            ):
                chunks.append((chunk, resp))

            # Should yield one error response
            assert len(chunks) == 1
            assert chunks[0][1].status_code == 504


class TestOpenAIClientProxy:
    """Test proxy configuration."""

    @pytest.mark.asyncio
    async def test_proxy_config_used(self):
        """Test: proxy configuration is passed to httpx client."""
        client = OpenAIClient()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.request.return_value = MagicMock(
                status_code=200,
                headers={},
                text='{"id": "test"}',
                json=lambda: {"id": "test"},
            )
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            await client.forward(
                base_url="https://api.openai.com",
                api_key="sk-test",
                path="/v1/chat/completions",
                method="POST",
                headers={},
                body={"model": "gpt-4"},
                target_model="gpt-4",
                proxy_config={"all://": "http://proxy.example.com:8080"},
            )

            # Verify proxy was passed to AsyncClient constructor
            mock_client_cls.assert_called_once()
            call_kwargs = mock_client_cls.call_args.kwargs
            assert call_kwargs["proxy"] == "http://proxy.example.com:8080"
