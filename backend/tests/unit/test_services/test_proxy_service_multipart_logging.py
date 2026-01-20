from unittest.mock import AsyncMock, patch

import pytest

from app.common.time import utc_now
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.proxy_service import ProxyService


@pytest.mark.asyncio
async def test_process_request_sanitizes_multipart_body_and_binary_response():
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

    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
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

    request_body = {
        "model": "audio-model",
        "_files": [
            {
                "field": "file",
                "filename": "audio.wav",
                "content_type": "audio/wav",
                "data": b"fake-audio",
            }
        ],
    }

    with patch("app.services.proxy_service.get_provider_client", return_value=fake_client):
        with patch(
            "app.services.proxy_service.convert_request_for_supplier",
            return_value=("/v1/audio/transcriptions", request_body),
        ):
            response, _ = await service.process_request(
                api_key_id=1,
                api_key_name="k",
                request_protocol="openai",
                path="/v1/audio/transcriptions",
                method="POST",
                headers={},
                body=request_body,
            )

    assert response.status_code == 200
    service.log_repo.create.assert_awaited()
    log_data = service.log_repo.create.await_args.args[0]
    assert log_data.request_body["_files"][0]["size"] == len(b"fake-audio")
    assert log_data.response_body == "[binary data: 8 bytes]"
