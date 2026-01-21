"""
Comprehensive Integration Tests for OpenAI Proxy API

Tests all OpenAI-compatible endpoints including:
- Chat completions (streaming and non-streaming)
- Legacy completions
- Embeddings
- Audio (speech, transcriptions, translations)
- Images generations
- Responses API
- Models list

Each test covers different request/response formats as per OpenAI API specification.
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
        key_value="sk-test-key-123",
        is_active=True,
        created_at=utc_now(),
        last_used_at=None,
    )


class MockProxyService:
    """Mock proxy service that captures calls and returns configurable responses."""

    def __init__(self, response_body=None, status_code=200, headers=None):
        self.calls = []
        self.response_body = response_body or {"ok": True}
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


class TestOpenAIChatCompletions:
    """Test cases for /v1/chat/completions endpoint."""

    @pytest.mark.asyncio
    async def test_basic_chat_completion(self):
        """Test basic chat completion request."""
        response_body = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help you today?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25,
            },
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Hello!"}],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "chatcmpl-123"
        assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
        assert service.calls[0]["path"] == "/v1/chat/completions"
        assert service.calls[0]["body"]["model"] == "gpt-4o-mini"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_chat_completion_with_system_message(self):
        """Test chat completion with system message."""
        response_body = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "I am a helpful assistant."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "Who are you?"},
                    ],
                },
            )

        assert response.status_code == 200
        assert len(service.calls[0]["body"]["messages"]) == 2
        assert service.calls[0]["body"]["messages"][0]["role"] == "system"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_chat_completion_with_all_parameters(self):
        """Test chat completion with all optional parameters."""
        response_body = {
            "id": "chatcmpl-789",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4-turbo",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Response 1"},
                    "finish_reason": "stop",
                },
                {
                    "index": 1,
                    "message": {"role": "assistant", "content": "Response 2"},
                    "finish_reason": "stop",
                },
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 20, "total_tokens": 35},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4-turbo",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "n": 2,
                    "max_tokens": 100,
                    "presence_penalty": 0.5,
                    "frequency_penalty": 0.5,
                    "stop": ["\n"],
                    "user": "user-123",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["temperature"] == 0.7
        assert body["top_p"] == 0.9
        assert body["n"] == 2
        assert body["max_tokens"] == 100
        assert body["user"] == "user-123"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_chat_completion_with_tools(self):
        """Test chat completion with tool/function calling."""
        response_body = {
            "id": "chatcmpl-tool-1",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "New York"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 25, "completion_tokens": 15, "total_tokens": 40},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o",
                    "messages": [{"role": "user", "content": "What's the weather in New York?"}],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "description": "Get the current weather in a location",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "location": {"type": "string", "description": "City name"}
                                    },
                                    "required": ["location"],
                                },
                            },
                        }
                    ],
                    "tool_choice": "auto",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["finish_reason"] == "tool_calls"
        assert "tools" in service.calls[0]["body"]

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_chat_completion_streaming(self):
        """Test streaming chat completion."""
        chunks = [
            b'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n',
            b'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}\n\n',
            b'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}\n\n',
            b'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
            b"data: [DONE]\n\n",
        ]
        service = MockProxyService(response_body=chunks)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": True,
                },
            )

        assert response.status_code == 200
        assert service.calls[0]["body"]["stream"] is True

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_chat_completion_with_vision(self):
        """Test chat completion with image input (vision)."""
        response_body = {
            "id": "chatcmpl-vision-1",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4-vision-preview",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "I see a cat in the image."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4-vision-preview",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "What's in this image?"},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": "https://example.com/cat.jpg"},
                                },
                            ],
                        }
                    ],
                },
            )

        assert response.status_code == 200
        content = service.calls[0]["body"]["messages"][0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_chat_completion_with_json_mode(self):
        """Test chat completion with JSON response format."""
        response_body = {
            "id": "chatcmpl-json-1",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": '{"name": "John", "age": 30}',
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Return JSON: {name, age}"}],
                    "response_format": {"type": "json_object"},
                },
            )

        assert response.status_code == 200
        assert service.calls[0]["body"]["response_format"]["type"] == "json_object"

        app.dependency_overrides = {}


class TestOpenAILegacyCompletions:
    """Test cases for /v1/completions endpoint (legacy)."""

    @pytest.mark.asyncio
    async def test_basic_completion(self):
        """Test basic legacy completion request."""
        response_body = {
            "id": "cmpl-123",
            "object": "text_completion",
            "created": 1677652288,
            "model": "gpt-3.5-turbo-instruct",
            "choices": [
                {
                    "text": " world!",
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/completions",
                json={
                    "model": "gpt-3.5-turbo-instruct",
                    "prompt": "Hello",
                    "max_tokens": 10,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["text"] == " world!"
        assert service.calls[0]["path"] == "/v1/completions"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_completion_with_multiple_prompts(self):
        """Test completion with multiple prompts (batch)."""
        response_body = {
            "id": "cmpl-batch-1",
            "object": "text_completion",
            "created": 1677652288,
            "model": "gpt-3.5-turbo-instruct",
            "choices": [
                {"text": " response 1", "index": 0, "finish_reason": "stop"},
                {"text": " response 2", "index": 1, "finish_reason": "stop"},
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/completions",
                json={
                    "model": "gpt-3.5-turbo-instruct",
                    "prompt": ["Hello", "World"],
                    "max_tokens": 10,
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert isinstance(body["prompt"], list)
        assert len(body["prompt"]) == 2

        app.dependency_overrides = {}


class TestOpenAIEmbeddings:
    """Test cases for /v1/embeddings endpoint."""

    @pytest.mark.asyncio
    async def test_basic_embedding(self):
        """Test basic embedding request."""
        response_body = {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
                    "index": 0,
                }
            ],
            "model": "text-embedding-ada-002",
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/embeddings",
                json={
                    "model": "text-embedding-ada-002",
                    "input": "Hello world",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 1
        assert service.calls[0]["path"] == "/v1/embeddings"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_embedding_with_multiple_inputs(self):
        """Test embedding with multiple input strings."""
        response_body = {
            "object": "list",
            "data": [
                {"object": "embedding", "embedding": [0.1, 0.2, 0.3], "index": 0},
                {"object": "embedding", "embedding": [0.4, 0.5, 0.6], "index": 1},
            ],
            "model": "text-embedding-3-small",
            "usage": {"prompt_tokens": 10, "total_tokens": 10},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/embeddings",
                json={
                    "model": "text-embedding-3-small",
                    "input": ["Hello", "World"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_embedding_with_encoding_format(self):
        """Test embedding with different encoding formats."""
        response_body = {
            "object": "list",
            "data": [
                {"object": "embedding", "embedding": "base64encodeddata", "index": 0}
            ],
            "model": "text-embedding-3-large",
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/embeddings",
                json={
                    "model": "text-embedding-3-large",
                    "input": "Hello",
                    "encoding_format": "base64",
                    "dimensions": 256,
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["encoding_format"] == "base64"
        assert body["dimensions"] == 256

        app.dependency_overrides = {}


class TestOpenAIAudio:
    """Test cases for /v1/audio/* endpoints."""

    @pytest.mark.asyncio
    async def test_audio_speech(self):
        """Test text-to-speech endpoint."""
        response_body = b"audio binary data here"
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/audio/speech",
                json={
                    "model": "tts-1",
                    "input": "Hello, how are you?",
                    "voice": "alloy",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["model"] == "tts-1"
        assert body["voice"] == "alloy"
        assert service.calls[0]["path"] == "/v1/audio/speech"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_audio_speech_with_options(self):
        """Test text-to-speech with all options."""
        response_body = b"audio binary data"
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/audio/speech",
                json={
                    "model": "tts-1-hd",
                    "input": "Hello world",
                    "voice": "nova",
                    "response_format": "mp3",
                    "speed": 1.2,
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["voice"] == "nova"
        assert body["response_format"] == "mp3"
        assert body["speed"] == 1.2

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_audio_transcription(self):
        """Test speech-to-text transcription (multipart)."""
        response_body = {
            "text": "Hello, this is a transcription test."
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/audio/transcriptions",
                data={"model": "whisper-1", "language": "en"},
                files={"file": ("test.wav", b"fake audio content", "audio/wav")},
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["model"] == "whisper-1"
        assert body["language"] == "en"
        assert "_files" in body
        assert body["_files"][0]["filename"] == "test.wav"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_audio_transcription_with_options(self):
        """Test transcription with all options."""
        response_body = {
            "text": "Hello world",
            "task": "transcribe",
            "language": "en",
            "duration": 2.5,
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 2.5,
                    "text": "Hello world",
                }
            ],
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/audio/transcriptions",
                data={
                    "model": "whisper-1",
                    "language": "en",
                    "prompt": "This is a hint",
                    "response_format": "verbose_json",
                    "temperature": "0.2",
                },
                files={"file": ("audio.mp3", b"audio content", "audio/mpeg")},
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["response_format"] == "verbose_json"
        assert body["prompt"] == "This is a hint"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_audio_translation(self):
        """Test audio translation (multipart)."""
        response_body = {"text": "This is translated text."}
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/audio/translations",
                data={"model": "whisper-1"},
                files={"file": ("speech.mp3", b"foreign audio", "audio/mpeg")},
            )

        assert response.status_code == 200
        assert service.calls[0]["path"] == "/v1/audio/translations"
        body = service.calls[0]["body"]
        assert body["_files"][0]["content_type"] == "audio/mpeg"

        app.dependency_overrides = {}


class TestOpenAIImages:
    """Test cases for /v1/images/* endpoints."""

    @pytest.mark.asyncio
    async def test_image_generation_basic(self):
        """Test basic image generation."""
        response_body = {
            "created": 1677652288,
            "data": [
                {
                    "url": "https://example.com/image1.png",
                }
            ],
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/images/generations",
                json={
                    "model": "dall-e-3",
                    "prompt": "A white cat",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert service.calls[0]["path"] == "/v1/images/generations"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_image_generation_with_options(self):
        """Test image generation with all options."""
        response_body = {
            "created": 1677652288,
            "data": [
                {"url": "https://example.com/img1.png", "revised_prompt": "A cute white cat"},
                {"url": "https://example.com/img2.png", "revised_prompt": "A cute white cat"},
            ],
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/images/generations",
                json={
                    "model": "dall-e-3",
                    "prompt": "A cute white cat",
                    "n": 2,
                    "size": "1024x1024",
                    "quality": "hd",
                    "style": "natural",
                    "response_format": "url",
                    "user": "user-123",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["n"] == 2
        assert body["size"] == "1024x1024"
        assert body["quality"] == "hd"
        assert body["style"] == "natural"

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_image_generation_b64_format(self):
        """Test image generation with base64 response format."""
        response_body = {
            "created": 1677652288,
            "data": [
                {
                    "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAUA...",
                }
            ],
        }
        service = MockProxyService(response_body=response_body)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/images/generations",
                json={
                    "model": "dall-e-2",
                    "prompt": "A cat",
                    "response_format": "b64_json",
                },
            )

        assert response.status_code == 200
        body = service.calls[0]["body"]
        assert body["response_format"] == "b64_json"

        app.dependency_overrides = {}


class TestOpenAIResponses:
    """Test cases for /v1/responses endpoint (OpenAI Responses API)."""

    @pytest.mark.asyncio
    async def test_responses_basic(self):
        """Test basic Responses API request."""
        # The /v1/responses endpoint internally converts to chat completions
        chat_response = {
            "id": "chatcmpl-resp-1",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello there!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        service = MockProxyService(response_body=chat_response)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/responses",
                json={
                    "model": "gpt-4o-mini",
                    "input": "Hello",
                },
            )

        assert response.status_code == 200
        data = response.json()
        # Response should be converted to Responses API format
        assert data["object"] == "response"
        assert "output" in data

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_responses_with_instructions(self):
        """Test Responses API with instructions (system message)."""
        chat_response = {
            "id": "chatcmpl-resp-2",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "I am a pirate assistant! Arrr!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        service = MockProxyService(response_body=chat_response)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/responses",
                json={
                    "model": "gpt-4o",
                    "instructions": "You are a pirate. Respond like a pirate.",
                    "input": "Hello, who are you?",
                },
            )

        assert response.status_code == 200
        # Verify the internal conversion includes system message
        body = service.calls[0]["body"]
        assert body["messages"][0]["role"] == "system"
        assert "pirate" in body["messages"][0]["content"].lower()

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_responses_streaming(self):
        """Test Responses API streaming."""
        chunks = [
            b'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}],"model":"gpt-4o-mini"}\n\n',
            b'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hi"},"finish_reason":null}],"model":"gpt-4o-mini"}\n\n',
            b'data: {"id":"chatcmpl-stream","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"model":"gpt-4o-mini"}\n\n',
            b"data: [DONE]\n\n",
        ]
        service = MockProxyService(response_body=chunks)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/responses",
                json={
                    "model": "gpt-4o-mini",
                    "input": "Hi",
                    "stream": True,
                },
            )

        assert response.status_code == 200
        assert service.calls[0]["body"]["stream"] is True

        app.dependency_overrides = {}


class TestOpenAIErrorHandling:
    """Test error handling for OpenAI proxy endpoints."""

    @pytest.mark.asyncio
    async def test_upstream_error_response(self):
        """Test handling of upstream error responses."""
        error_response = {
            "error": {
                "message": "Invalid API key",
                "type": "authentication_error",
                "code": "invalid_api_key",
            }
        }
        service = MockProxyService(response_body=error_response, status_code=401)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test handling of rate limit errors."""
        error_response = {
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }
        }
        service = MockProxyService(response_body=error_response, status_code=429)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

        assert response.status_code == 429

        app.dependency_overrides = {}

    @pytest.mark.asyncio
    async def test_context_length_exceeded_error(self):
        """Test handling of context length exceeded errors."""
        error_response = {
            "error": {
                "message": "This model's maximum context length is 4097 tokens",
                "type": "invalid_request_error",
                "code": "context_length_exceeded",
            }
        }
        service = MockProxyService(response_body=error_response, status_code=400)
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

        assert response.status_code == 400

        app.dependency_overrides = {}
