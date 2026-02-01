from unittest.mock import AsyncMock, patch

import pytest

from app.common.time import utc_now
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.protocol_hooks import ProtocolConversionHooks
from app.services.proxy_service import ProxyService


class RecordingHooks(ProtocolConversionHooks):
    def before_request_conversion(self, body, request_protocol, supplier_protocol):
        return {**body, "before": True}

    def after_request_conversion(self, supplier_body, request_protocol, supplier_protocol):
        return {**supplier_body, "after": True}

    def before_response_conversion(self, supplier_body, request_protocol, supplier_protocol):
        return {"wrapped": supplier_body}

    def after_response_conversion(self, response_body, request_protocol, supplier_protocol):
        return {"after_response": response_body}


class StreamHooks(ProtocolConversionHooks):
    def before_stream_chunk_conversion(self, chunk, request_protocol, supplier_protocol):
        return chunk.replace(b"message_start", b"message_start_hooked")

    def after_stream_chunk_conversion(self, chunk, request_protocol, supplier_protocol):
        return chunk.replace(b"hi", b"hi!")


@pytest.mark.asyncio
async def test_protocol_hooks_apply_to_non_stream_flow():
    now = utc_now()
    model_mapping = ModelMapping(
        requested_model="test-model",
        strategy="round_robin",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    candidate = CandidateProvider(
        provider_id=1,
        provider_name="p-anthropic",
        base_url="https://example.com",
        protocol="anthropic",
        api_key="sk-test",
        target_model="claude-3-sonnet",
        priority=0,
        weight=1,
    )

    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
        protocol_hooks=RecordingHooks(),
    )
    service._resolve_candidates = AsyncMock(
        return_value=(model_mapping, [candidate], 0, "openai", {})
    )  # type: ignore[method-assign]

    async def forward(*, body: dict, **kwargs):
        assert body["after"] is True
        return ProviderResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body={"upstream": "ok"},
        )

    fake_client = AsyncMock()
    fake_client.forward = AsyncMock(side_effect=forward)

    def fake_convert_request_for_supplier(*, body, **kwargs):
        assert body["before"] is True
        return "/v1/messages", {"converted": True}

    def fake_convert_response_for_user(*, body, **kwargs):
        assert body == {"wrapped": {"upstream": "ok"}}
        return {"converted_response": True}

    with patch(
        "app.services.proxy_service.convert_request_for_supplier",
        side_effect=fake_convert_request_for_supplier,
    ):
        with patch(
            "app.services.proxy_service.convert_response_for_user",
            side_effect=fake_convert_response_for_user,
        ):
            with patch(
                "app.services.proxy_service.get_provider_client",
                return_value=fake_client,
            ):
                response, _ = await service.process_request(
                    api_key_id=1,
                    api_key_name="k",
                    request_protocol="openai",
                    path="/v1/chat/completions",
                    method="POST",
                    headers={},
                    body={"model": "test-model", "messages": []},
                )

    assert response.body == {"after_response": {"converted_response": True}}
    service.log_repo.create.assert_awaited()


@pytest.mark.asyncio
async def test_protocol_hooks_apply_to_stream_chunks():
    now = utc_now()
    model_mapping = ModelMapping(
        requested_model="test-model",
        strategy="round_robin",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    candidate = CandidateProvider(
        provider_id=1,
        provider_name="p-anthropic",
        base_url="https://example.com",
        protocol="anthropic",
        api_key="sk-test",
        target_model="claude-3-sonnet",
        priority=0,
        weight=1,
    )

    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
        protocol_hooks=StreamHooks(),
    )
    service._resolve_candidates = AsyncMock(
        return_value=(model_mapping, [candidate], 0, "openai", {})
    )  # type: ignore[method-assign]

    def forward_stream(**kwargs):
        async def gen():
            response = ProviderResponse(status_code=200, headers={})
            yield b'data: {"type":"message_start"}\n\n', response

        return gen()

    fake_client = AsyncMock()
    fake_client.forward_stream = forward_stream

    async def fake_convert_stream_for_user(*, upstream, **kwargs):
        chunks = []
        async for chunk in upstream:
            chunks.append(chunk)
        assert chunks == [b'data: {"type":"message_start_hooked"}\n\n']
        for _ in chunks:
            yield b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'

    with patch(
        "app.services.proxy_service.convert_request_for_supplier",
        return_value=("/v1/messages", {"converted": True}),
    ):
        with patch(
            "app.services.proxy_service.convert_stream_for_user",
            side_effect=fake_convert_stream_for_user,
        ):
            with patch(
                "app.services.proxy_service.get_provider_client",
                return_value=fake_client,
            ):
                initial_response, stream_gen, _ = await service.process_request_stream(
                    api_key_id=1,
                    api_key_name="k",
                    request_protocol="openai",
                    path="/v1/chat/completions",
                    method="POST",
                    headers={},
                    body={"model": "test-model", "stream": True, "messages": []},
                )

    assert initial_response.status_code == 200

    chunks = []
    async for chunk in stream_gen:
        chunks.append(chunk)

    assert chunks == [b'data: {"choices":[{"delta":{"content":"hi!"}}]}\n\n']
    service.log_repo.create.assert_awaited()
