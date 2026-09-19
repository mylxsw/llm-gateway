"""Disconnect propagation through the service, retry loop and conversion layers."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from starlette.responses import StreamingResponse

from app.common.protocol import converters
from app.common.time import utc_now
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.proxy_service import ProxyService


@pytest.mark.parametrize("http_disconnect", [False, True])
async def test_disconnect_during_buffering_closes_provider(
    monkeypatch, http_disconnect
):
    monkeypatch.setattr(converters, "ANTHROPIC_HEARTBEAT_INTERVAL_SECONDS", 0.005)
    now = utc_now()
    mapping = ModelMapping(
        requested_model="writer",
        strategy="priority",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    candidate = CandidateProvider(
        provider_id=1,
        provider_name="test",
        base_url="https://example.com",
        protocol="openai",
        api_key="test",
        target_model="test",
        priority=1,
    )
    service = ProxyService(
        model_repo=AsyncMock(), provider_repo=AsyncMock(), log_repo=AsyncMock()
    )
    service._resolve_candidates = AsyncMock(
        return_value=(mapping, [candidate], 0, "anthropic", {})
    )
    closed, disconnected = asyncio.Event(), asyncio.Event()

    async def forward_stream(**kwargs):
        response = ProviderResponse(
            status_code=200, headers={"content-type": "text/event-stream"}
        )
        try:
            for i, arguments in [(0, "{}"), (1, "{")]:
                payload = {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": i,
                                        "id": f"call_{i}",
                                        "function": {
                                            "name": "Tool",
                                            "arguments": arguments,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
                yield ("data: " + json.dumps(payload) + "\n\n").encode(), response
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0.01)
            closed.set()

    client = AsyncMock()
    client.forward_stream = forward_stream
    with patch("app.services.proxy_service.get_provider_client", return_value=client):
        response, output, _ = await service.process_request_stream(
            api_key_id=1,
            api_key_name="test",
            request_protocol="anthropic",
            path="/v1/messages",
            request_url="/v1/messages",
            method="POST",
            headers={},
            body={
                "model": "writer",
                "stream": True,
                "max_tokens": 100,
                "messages": [{"role": "user", "content": "Call tools"}],
            },
        )
        assert response.is_success
        if http_disconnect:

            async def receive():
                await disconnected.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                if b"event: ping" in message.get("body", b""):
                    disconnected.set()

            http_response = StreamingResponse(output, media_type="text/event-stream")
            await asyncio.wait_for(
                http_response(
                    {"type": "http", "asgi": {"spec_version": "2.3"}},
                    receive,
                    send,
                ),
                1,
            )
        else:
            try:
                for _ in range(10):
                    chunk = await asyncio.wait_for(anext(output), 1)
                    if b"event: ping" in chunk:
                        break
                else:
                    pytest.fail("No heartbeat during buffering")
            finally:
                await output.aclose()
        assert closed.is_set()
