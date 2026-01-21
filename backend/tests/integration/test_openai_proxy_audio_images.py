import pytest
from httpx import AsyncClient, ASGITransport

from app.api.deps import get_current_api_key, get_proxy_service
from app.domain.api_key import ApiKeyModel
from app.main import app
from app.providers.base import ProviderResponse
from app.common.time import utc_now


class _DummyProxyService:
    def __init__(self) -> None:
        self.calls = []

    async def process_request(self, **kwargs):
        self.calls.append(kwargs)
        return ProviderResponse(status_code=200, body={"ok": True, "path": kwargs.get("path")}), {}

    async def process_request_stream(self, **kwargs):
        raise AssertionError("streaming not expected in these tests")


def _make_api_key():
    return ApiKeyModel(
        id=1,
        key_name="test-key",
        key_value="sk-test...",
        is_active=True,
        created_at=utc_now(),
        last_used_at=None,
    )


@pytest.mark.asyncio
async def test_openai_embeddings_proxy():
    service = _DummyProxyService()
    app.dependency_overrides[get_proxy_service] = lambda: service
    app.dependency_overrides[get_current_api_key] = _make_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/embeddings",
            json={"model": "text-embedding-ada-002", "input": "hello"},
        )

    assert response.status_code == 200
    assert service.calls[0]["path"] == "/v1/embeddings"
    assert service.calls[0]["body"]["model"] == "text-embedding-ada-002"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_openai_audio_speech_proxy():
    service = _DummyProxyService()
    app.dependency_overrides[get_proxy_service] = lambda: service
    app.dependency_overrides[get_current_api_key] = _make_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/speech",
            json={"model": "gpt-4o-mini-tts", "input": "hello", "voice": "alloy"},
        )

    assert response.status_code == 200
    assert service.calls[0]["path"] == "/v1/audio/speech"
    assert service.calls[0]["body"]["model"] == "gpt-4o-mini-tts"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_openai_images_generations_proxy():
    service = _DummyProxyService()
    app.dependency_overrides[get_proxy_service] = lambda: service
    app.dependency_overrides[get_current_api_key] = _make_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/images/generations",
            json={"model": "gpt-image-1", "prompt": "A cat"},
        )

    assert response.status_code == 200
    assert service.calls[0]["path"] == "/v1/images/generations"
    assert service.calls[0]["body"]["prompt"] == "A cat"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_openai_audio_transcriptions_proxy_multipart():
    service = _DummyProxyService()
    app.dependency_overrides[get_proxy_service] = lambda: service
    app.dependency_overrides[get_current_api_key] = _make_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1", "language": "en"},
            files={"file": ("audio.wav", b"audio-bytes", "audio/wav")},
        )

    assert response.status_code == 200
    assert service.calls[0]["path"] == "/v1/audio/transcriptions"
    body = service.calls[0]["body"]
    assert body["model"] == "whisper-1"
    assert body["_files"][0]["filename"] == "audio.wav"
    assert body["_files"][0]["content_type"] == "audio/wav"
    assert body["_files"][0]["data"] == b"audio-bytes"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_openai_audio_translations_proxy_multipart():
    service = _DummyProxyService()
    app.dependency_overrides[get_proxy_service] = lambda: service
    app.dependency_overrides[get_current_api_key] = _make_api_key

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/translations",
            data={"model": "whisper-1"},
            files={"file": ("audio.mp3", b"audio-bytes", "audio/mpeg")},
        )

    assert response.status_code == 200
    assert service.calls[0]["path"] == "/v1/audio/translations"
    body = service.calls[0]["body"]
    assert body["model"] == "whisper-1"
    assert body["_files"][0]["filename"] == "audio.mp3"
    assert body["_files"][0]["content_type"] == "audio/mpeg"
    assert body["_files"][0]["data"] == b"audio-bytes"

    app.dependency_overrides = {}
