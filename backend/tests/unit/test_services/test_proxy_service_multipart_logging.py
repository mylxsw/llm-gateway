import io
import wave
from unittest.mock import AsyncMock, patch

import pytest

from app.common.time import utc_now
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository
from app.rules.models import CandidateProvider
from app.services.proxy_service import ProxyService


@pytest.mark.asyncio
async def test_process_request_sanitizes_multipart_body_and_binary_response(db_session):
    now = utc_now()
    model_mapping = ModelMapping(
        requested_model="audio-model",
        strategy="round_robin",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    candidate = CandidateProvider(
        provider_id=1,
        provider_name="p-openai",
        base_url="https://example.com",
        protocol="openai",
        api_key="sk-test",
        target_model="whisper-1",
        priority=0,
        weight=1,
    )

    log_repo = SQLAlchemyLogRepository(db_session)
    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=log_repo,
    )
    service._resolve_candidates = AsyncMock(  # type: ignore[method-assign]
        return_value=(model_mapping, [candidate], 0, "openai", {})
    )

    async def forward(**kwargs):
        return ProviderResponse(
            status_code=200,
            headers={"content-type": "audio/wav"},
            body=b"\x00\x01binary",
        )

    fake_client = AsyncMock()
    fake_client.forward = AsyncMock(side_effect=forward)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\xff\x00" * 80)
    audio_data = buffer.getvalue()
    request_body = {
        "model": "audio-model",
        "_files": [
            {
                "field": "file",
                "filename": "audio.wav",
                "content_type": "audio/wav",
                "data": audio_data,
            }
        ],
    }

    with patch("app.services.proxy_service.get_provider_client", return_value=fake_client):
        with patch(
            "app.services.proxy_service.convert_request_for_supplier",
            return_value=("/v1/audio/transcriptions", request_body),
        ):
            response, _ = await service.process_request(
                api_key_id=None,
                api_key_name="k",
                request_protocol="openai",
                path="/v1/audio/transcriptions",
                request_url="/v1/audio/transcriptions",
                method="POST",
                headers={},
                body=request_body,
            )

    assert response.status_code == 200
    log_data = await log_repo.get_by_id(1)
    assert log_data.is_completed is True
    assert log_data.request_body["_files"][0]["size"] == len(audio_data)
    assert log_data.converted_request_body["_files"][0]["data"] == f"[binary data: {len(audio_data)} bytes]"
    assert log_data.response_body == "[binary data: 8 bytes]"
