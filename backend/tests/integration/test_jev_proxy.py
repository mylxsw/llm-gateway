"""
Integration tests for the Jev proxy endpoint.

Covers the full path through the real ProxyService: forwarding, logging,
billing and upstream error pass-through, plus the FastAPI route itself.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_api_key, get_proxy_service
from app.common.time import utc_now
from app.domain.api_key import ApiKeyModel
from app.domain.model import ModelMapping
from app.main import app
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.proxy_service import ProxyService

JEV_REQUEST = {
    "model": "jev-latest",
    "state": "Help! My payouts have been failing for 3 days.",
    "questions": {
        "is_urgent": {
            "type": "noul",
            "instructions": "Does this convey urgency?",
            "criteria": {"true": "Explicitly time-sensitive", "false": "No urgency"},
        },
        "department": {
            "type": "choice",
            "instructions": "Which team should handle this?",
            "criteria": {
                "billing": "Payments, invoicing, refunds",
                "technical": "Bugs, outages, integrations",
            },
        },
        "frustration": {
            "type": "score",
            "instructions": "How frustrated is the customer?",
            "criteria": ["Calm", "Frustrated", "Very angry"],
        },
    },
}

JEV_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "is_urgent": {"type": "noul", "noul": 0.95},
        "department": {
            "type": "choice",
            "choice": "billing",
            "probabilities": {"billing": 0.88, "technical": 0.12},
            "confidence": 0.81,
        },
        "frustration": {
            "type": "score",
            "score": 1.05,
            "legend": {"0": "Calm", "1": "Frustrated", "2": "Very angry"},
            "probabilities": {"0": 0.0, "1": 0.95, "2": 0.05},
            "confidence": 0.92,
        },
    },
    "usage": {"input_tokens": 296, "output_tokens": 20},
}


def _make_api_key() -> ApiKeyModel:
    return ApiKeyModel(
        id=1,
        key_name="test-key",
        key_value="sk-test-key-123",
        is_active=True,
        created_at=utc_now(),
        last_used_at=None,
    )


def _model_mapping(**overrides) -> ModelMapping:
    now = utc_now()
    defaults = dict(
        requested_model="jev-latest",
        model_type="jev",
        strategy="round_robin",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
        # TypeSafe publishes $0.042 / 1M input tokens with free output. The
        # operator configures the real numbers; these are just test values.
        billing_mode="token_flat",
        input_price=0.042,
        output_price=0.0,
    )
    defaults.update(overrides)
    return ModelMapping(**defaults)


def _candidate() -> CandidateProvider:
    return CandidateProvider(
        provider_id=1,
        provider_name="typesafe",
        base_url="https://api.typesafe.ai/v1",
        protocol="jev",
        api_key="sk-upstream",
        target_model="jev-1.13.0",
        priority=0,
        weight=1,
    )


def _service(model_mapping=None, input_tokens=0) -> ProxyService:
    service = ProxyService(
        model_repo=AsyncMock(),
        provider_repo=AsyncMock(),
        log_repo=AsyncMock(),
    )
    service._resolve_candidates = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            model_mapping or _model_mapping(),
            [_candidate()],
            input_tokens,
            "jev",
            {},
        )
    )
    return service


class TestJevProxyServiceForwarding:
    @pytest.mark.asyncio
    async def test_request_is_forwarded_untouched_except_model(self):
        service = _service()
        seen = {}

        async def forward(**kwargs):
            seen.update(kwargs)
            return ProviderResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                body=json.dumps(JEV_RESPONSE).encode("utf-8"),
            )

        fake_client = AsyncMock()
        fake_client.forward = AsyncMock(side_effect=forward)

        with patch(
            "app.services.proxy_service.get_provider_client", return_value=fake_client
        ):
            response, log_info = await service.process_request(
                api_key_id=1,
                api_key_name="k",
                request_protocol="jev",
                path="/v1/systemone",
                request_url="http://gw/v1/systemone",
                method="POST",
                headers={},
                body=dict(JEV_REQUEST),
            )

        assert response.status_code == 200
        # Same protocol on both sides means raw byte pass-through.
        assert seen["response_mode"] == "raw"
        assert seen["path"] == "/v1/systemone"
        assert seen["target_model"] == "jev-1.13.0"
        # Only the model field differs from what the client sent.
        assert seen["body"]["model"] == "jev-1.13.0"
        assert seen["body"]["state"] == JEV_REQUEST["state"]
        assert seen["body"]["questions"] == JEV_REQUEST["questions"]
        assert log_info["trace_id"]

    @pytest.mark.asyncio
    async def test_response_body_is_returned_verbatim(self):
        service = _service()
        raw = json.dumps(JEV_RESPONSE).encode("utf-8")

        fake_client = AsyncMock()
        fake_client.forward = AsyncMock(
            return_value=ProviderResponse(status_code=200, body=raw, headers={})
        )

        with patch(
            "app.services.proxy_service.get_provider_client", return_value=fake_client
        ):
            with patch(
                "app.services.proxy_service.convert_response_for_user",
                side_effect=AssertionError("no response conversion for same protocol"),
            ):
                response, _ = await service.process_request(
                    api_key_id=1,
                    api_key_name="k",
                    request_protocol="jev",
                    path="/v1/systemone",
                    request_url="http://gw/v1/systemone",
                    method="POST",
                    headers={},
                    body=dict(JEV_REQUEST),
                )

        assert response.body == raw


class TestJevProxyServiceLoggingAndBilling:
    @pytest.mark.asyncio
    async def test_usage_and_cost_come_from_upstream_usage(self):
        service = _service(input_tokens=11)

        fake_client = AsyncMock()
        fake_client.forward = AsyncMock(
            return_value=ProviderResponse(
                status_code=200,
                body=json.dumps(JEV_RESPONSE).encode("utf-8"),
                headers={},
            )
        )

        with patch(
            "app.services.proxy_service.get_provider_client", return_value=fake_client
        ):
            await service.process_request(
                api_key_id=1,
                api_key_name="k",
                request_protocol="jev",
                path="/v1/systemone",
                request_url="http://gw/v1/systemone",
                method="POST",
                headers={},
                body=dict(JEV_REQUEST),
            )

        log_data = service.log_repo.update.await_args.args[1]
        # Upstream usage overrides the pre-flight estimate.
        assert log_data.input_tokens == 296
        assert log_data.output_tokens == 20
        assert log_data.usage_details["source"] == "upstream"
        # 296 tokens * $0.042 / 1M, rounded up to 4dp; output is free.
        assert log_data.input_cost == 0.0001
        assert log_data.output_cost == 0.0
        assert log_data.total_cost == 0.0001
        assert log_data.price_source == "ModelFallback"

    @pytest.mark.asyncio
    async def test_large_request_cost_is_proportional(self):
        service = _service()
        body = json.dumps(
            {
                "model": "jev-1.13.0",
                "answers": {},
                "usage": {"input_tokens": 10_000_000, "output_tokens": 500},
            }
        ).encode("utf-8")

        fake_client = AsyncMock()
        fake_client.forward = AsyncMock(
            return_value=ProviderResponse(status_code=200, body=body, headers={})
        )

        with patch(
            "app.services.proxy_service.get_provider_client", return_value=fake_client
        ):
            await service.process_request(
                api_key_id=1,
                api_key_name="k",
                request_protocol="jev",
                path="/v1/systemone",
                request_url="http://gw/v1/systemone",
                method="POST",
                headers={},
                body=dict(JEV_REQUEST),
            )

        log_data = service.log_repo.update.await_args.args[1]
        # 10M tokens * $0.042 / 1M = $0.42
        assert log_data.total_cost == pytest.approx(0.42)
        assert log_data.output_cost == 0.0

    @pytest.mark.asyncio
    async def test_log_records_protocol_and_upstream_details(self):
        service = _service()

        fake_client = AsyncMock()
        fake_client.forward = AsyncMock(
            return_value=ProviderResponse(
                status_code=200,
                body=json.dumps(JEV_RESPONSE).encode("utf-8"),
                headers={"content-type": "application/json"},
            )
        )

        with patch(
            "app.services.proxy_service.get_provider_client", return_value=fake_client
        ):
            await service.process_request(
                api_key_id=1,
                api_key_name="k",
                request_protocol="jev",
                path="/v1/systemone",
                request_url="http://gw/v1/systemone",
                method="POST",
                headers={"authorization": "Bearer sk-client"},
                body=dict(JEV_REQUEST),
            )

        log_data = service.log_repo.update.await_args.args[1]
        assert log_data.request_protocol == "jev"
        assert log_data.supplier_protocol == "jev"
        assert log_data.request_path == "/v1/systemone"
        assert log_data.upstream_url == "https://api.typesafe.ai/v1/systemone"
        assert log_data.is_stream is False
        assert log_data.provider_name == "typesafe"
        assert log_data.target_model == "jev-1.13.0"
        # Full request body is captured for auditing.
        assert log_data.request_body["state"] == JEV_REQUEST["state"]
        assert set(log_data.request_body["questions"]) == {
            "is_urgent",
            "department",
            "frustration",
        }
        # The converted upstream body is recorded too.
        assert log_data.converted_request_body["model"] == "jev-1.13.0"
        # The client credential is masked rather than stored verbatim.
        logged_auth = log_data.request_headers["authorization"]
        assert "sk-client" not in logged_auth
        assert logged_auth.startswith("Bearer ")
        assert "***" in logged_auth
        # Response body is persisted.
        assert "is_urgent" in log_data.response_body

    @pytest.mark.asyncio
    async def test_detail_logging_disabled_strips_bodies(self):
        service = _service()

        fake_client = AsyncMock()
        fake_client.forward = AsyncMock(
            return_value=ProviderResponse(
                status_code=200,
                body=json.dumps(JEV_RESPONSE).encode("utf-8"),
                headers={},
            )
        )

        with patch(
            "app.services.proxy_service.get_provider_client", return_value=fake_client
        ):
            await service.process_request(
                api_key_id=1,
                api_key_name="k",
                request_protocol="jev",
                path="/v1/systemone",
                request_url="http://gw/v1/systemone",
                method="POST",
                headers={},
                body=dict(JEV_REQUEST),
                record_details=False,
            )

        log_data = service.log_repo.update.await_args.args[1]
        assert log_data.request_body is None
        assert log_data.response_body is None
        assert log_data.converted_request_body is None
        # Metadata and usage are still retained.
        assert log_data.input_tokens == 296
        assert log_data.total_cost == 0.0001


class TestJevProxyServiceErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [401, 422, 429])
    async def test_client_errors_pass_through_without_retry(self, status):
        service = _service()
        error_body = {"error": {"message": "bad request"}}

        fake_client = AsyncMock()
        fake_client.forward = AsyncMock(
            return_value=ProviderResponse(
                status_code=status,
                body=json.dumps(error_body).encode("utf-8"),
                headers={},
            )
        )

        with patch(
            "app.services.proxy_service.get_provider_client", return_value=fake_client
        ):
            response, _ = await service.process_request(
                api_key_id=1,
                api_key_name="k",
                request_protocol="jev",
                path="/v1/systemone",
                request_url="http://gw/v1/systemone",
                method="POST",
                headers={},
                body=dict(JEV_REQUEST),
            )

        assert response.status_code == status
        assert json.loads(response.body) == error_body

    @pytest.mark.asyncio
    async def test_overloaded_529_is_retried_on_the_same_provider(self):
        service = _service()
        calls = []

        async def forward(**kwargs):
            calls.append(kwargs)
            return ProviderResponse(
                status_code=529, body=b'{"error":{"message":"overloaded"}}', headers={}
            )

        fake_client = AsyncMock()
        fake_client.forward = AsyncMock(side_effect=forward)

        with patch(
            "app.services.proxy_service.get_provider_client", return_value=fake_client
        ):
            response, _ = await service.process_request(
                api_key_id=1,
                api_key_name="k",
                request_protocol="jev",
                path="/v1/systemone",
                request_url="http://gw/v1/systemone",
                method="POST",
                headers={},
                body=dict(JEV_REQUEST),
            )

        assert response.status_code == 529
        # 529 is a server error, so the gateway retried rather than giving up.
        assert len(calls) > 1


class TestJevProxyRoute:
    @pytest.mark.asyncio
    async def test_systemone_route_is_registered_and_returns_answers(self):
        class MockProxyService:
            def __init__(self):
                self.calls = []

            async def process_request(self, **kwargs):
                self.calls.append(kwargs)
                return (
                    ProviderResponse(
                        status_code=200,
                        body=JEV_RESPONSE,
                        headers={"content-type": "application/json"},
                    ),
                    {"trace_id": "trace-123"},
                )

        service = MockProxyService()
        app.dependency_overrides[get_proxy_service] = lambda: service
        app.dependency_overrides[get_current_api_key] = _make_api_key

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post("/v1/systemone", json=JEV_REQUEST)

            assert response.status_code == 200
            assert response.json() == JEV_RESPONSE
            assert response.headers["x-lgw-trace-id"] == "trace-123"

            call = service.calls[0]
            assert call["request_protocol"] == "jev"
            assert call["path"] == "/v1/systemone"
            assert call["body"] == JEV_REQUEST
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_upstream_error_status_is_preserved(self):
        class MockProxyService:
            async def process_request(self, **kwargs):
                return (
                    ProviderResponse(
                        status_code=422,
                        body={"error": {"message": "missing questions"}},
                        headers={},
                    ),
                    {"trace_id": "t"},
                )

        app.dependency_overrides[get_proxy_service] = lambda: MockProxyService()
        app.dependency_overrides[get_current_api_key] = _make_api_key

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post("/v1/systemone", json=JEV_REQUEST)

            assert response.status_code == 422
            assert response.json()["error"]["message"] == "missing questions"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_app_error_is_rendered_as_json(self):
        from app.common.errors import NotFoundError

        class MockProxyService:
            async def process_request(self, **kwargs):
                raise NotFoundError(
                    message="Model 'jev-latest' is not configured",
                    code="model_not_found",
                )

        app.dependency_overrides[get_proxy_service] = lambda: MockProxyService()
        app.dependency_overrides[get_current_api_key] = _make_api_key

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                response = await client.post("/v1/systemone", json=JEV_REQUEST)

            assert response.status_code == 404
            assert response.json()["error"]["code"] == "model_not_found"
        finally:
            app.dependency_overrides.clear()
