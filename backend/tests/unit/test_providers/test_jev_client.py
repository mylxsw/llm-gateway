"""
Tests for the Jev provider client.
"""

import json

import httpx
import pytest

from app.providers.jev_client import JevClient


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.fixture
def client():
    return JevClient()


def _patch_httpx(monkeypatch, handler):
    """Force httpx.AsyncClient to use a MockTransport."""
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = _mock_transport(handler)
        kwargs.pop("proxy", None)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


class TestJevClientForward:
    async def test_forward_posts_to_systemone_and_rewrites_model(
        self, client, monkeypatch
    ):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["method"] = request.method
            seen["auth"] = request.headers.get("authorization")
            seen["content_type"] = request.headers.get("content-type")
            seen["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "model": "jev-1.13.0",
                    "answers": {"is_urgent": {"type": "noul", "noul": 0.95}},
                    "usage": {"input_tokens": 296, "output_tokens": 20},
                },
            )

        _patch_httpx(monkeypatch, handler)

        response = await client.forward(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
            path="/systemone",
            method="POST",
            headers={"authorization": "Bearer client-key", "x-user-id": "u1"},
            body={
                "model": "jev-latest",
                "state": "Help! My payouts have been failing.",
                "questions": {
                    "is_urgent": {"type": "noul", "instructions": "Urgent?"}
                },
            },
            target_model="jev-1.13.0",
        )

        assert response.status_code == 200
        assert response.is_success
        assert seen["url"] == "https://api.typesafe.ai/v1/systemone"
        assert seen["method"] == "POST"
        # Client Authorization is replaced with the provider key.
        assert seen["auth"] == "Bearer sk-test"
        assert seen["content_type"] == "application/json"
        # Only the model field is rewritten; everything else is untouched.
        assert seen["body"]["model"] == "jev-1.13.0"
        assert seen["body"]["state"] == "Help! My payouts have been failing."
        assert seen["body"]["questions"] == {
            "is_urgent": {"type": "noul", "instructions": "Urgent?"}
        }
        assert response.body["usage"]["input_tokens"] == 296

    async def test_forward_strips_client_user_id_header(self, client, monkeypatch):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["headers"] = dict(request.headers)
            return httpx.Response(200, json={"answers": {}})

        _patch_httpx(monkeypatch, handler)

        await client.forward(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
            path="/systemone",
            method="POST",
            headers={"x-user-id": "u1", "x-api-key": "leak"},
            body={"model": "m", "state": "s", "questions": {}},
            target_model="jev-1.13.0",
        )

        lowered = {k.lower() for k in seen["headers"]}
        assert "x-user-id" not in lowered
        assert "x-api-key" not in lowered

    async def test_forward_raw_mode_returns_bytes(self, client, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"answers": {"a": {"type": "noul"}}})

        _patch_httpx(monkeypatch, handler)

        response = await client.forward(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
            path="/systemone",
            method="POST",
            headers={},
            body={"model": "m", "state": "s", "questions": {}},
            target_model="jev-1.13.0",
            response_mode="raw",
        )

        assert isinstance(response.body, bytes)
        assert json.loads(response.body)["answers"]["a"]["type"] == "noul"

    @pytest.mark.parametrize("status", [401, 422, 429, 529])
    async def test_forward_passes_through_upstream_errors(
        self, client, monkeypatch, status
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json={"error": {"message": "nope"}})

        _patch_httpx(monkeypatch, handler)

        response = await client.forward(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
            path="/systemone",
            method="POST",
            headers={},
            body={"model": "m", "state": "s", "questions": {}},
            target_model="jev-1.13.0",
        )

        assert response.status_code == status
        assert response.body == {"error": {"message": "nope"}}

    async def test_forward_non_json_body_falls_back_to_text(self, client, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="<html>bad gateway</html>")

        _patch_httpx(monkeypatch, handler)

        response = await client.forward(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
            path="/systemone",
            method="POST",
            headers={},
            body={"model": "m", "state": "s", "questions": {}},
            target_model="jev-1.13.0",
        )

        assert response.status_code == 502
        assert response.body == "<html>bad gateway</html>"

    async def test_forward_timeout_returns_504(self, client, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        _patch_httpx(monkeypatch, handler)

        response = await client.forward(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
            path="/systemone",
            method="POST",
            headers={},
            body={"model": "m", "state": "s", "questions": {}},
            target_model="jev-1.13.0",
        )

        assert response.status_code == 504
        assert "timeout" in response.error.lower()

    async def test_forward_request_error_returns_502(self, client, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        _patch_httpx(monkeypatch, handler)

        response = await client.forward(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
            path="/systemone",
            method="POST",
            headers={},
            body={"model": "m", "state": "s", "questions": {}},
            target_model="jev-1.13.0",
        )

        assert response.status_code == 502
        assert "Request error" in response.error


class TestJevClientListModels:
    async def test_list_models_hits_v1_models(self, client, monkeypatch):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("authorization")
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "jev-latest",
                            "description": "flagship",
                            "release_date": "2026-01-01",
                        }
                    ]
                },
            )

        _patch_httpx(monkeypatch, handler)

        response = await client.list_models(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
        )

        assert response.status_code == 200
        assert seen["url"] == "https://api.typesafe.ai/v1/models"
        assert seen["auth"] == "Bearer sk-test"
        assert response.body["models"][0]["name"] == "jev-latest"

    async def test_list_models_response_shape_is_understood_by_extractor(
        self, client, monkeypatch
    ):
        from app.services.provider_service import ProviderService

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "models": [
                        {"name": "jev-latest", "description": "", "release_date": ""},
                        {"name": "jev-preview", "description": "", "release_date": ""},
                    ]
                },
            )

        _patch_httpx(monkeypatch, handler)

        response = await client.list_models(
            base_url="https://api.typesafe.ai/v1", api_key="sk-test"
        )
        assert ProviderService._extract_model_ids(response.body) == [
            "jev-latest",
            "jev-preview",
        ]

    async def test_list_models_timeout_returns_504(self, client, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("too slow", request=request)

        _patch_httpx(monkeypatch, handler)

        response = await client.list_models(
            base_url="https://api.typesafe.ai/v1", api_key="sk-test"
        )
        assert response.status_code == 504

    async def test_list_models_request_error_returns_502(self, client, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        _patch_httpx(monkeypatch, handler)

        response = await client.list_models(
            base_url="https://api.typesafe.ai/v1", api_key="sk-test"
        )
        assert response.status_code == 502


class TestJevClientStreaming:
    async def test_forward_stream_reports_unsupported(self, client):
        chunks = []
        async for chunk, response in client.forward_stream(
            base_url="https://api.typesafe.ai/v1",
            api_key="sk-test",
            path="/systemone",
            method="POST",
            headers={},
            body={"model": "m", "state": "s", "questions": {}},
            target_model="jev-1.13.0",
        ):
            chunks.append((chunk, response))

        assert len(chunks) == 1
        chunk, response = chunks[0]
        assert chunk == b""
        assert response.status_code == 400
        assert "does not support streaming" in response.error
