from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.gemini_client import GeminiClient


def test_gemini_prepare_headers_uses_x_goog_api_key():
    client = GeminiClient()
    prepared = client._prepare_headers(
        headers={
            "Authorization": "Bearer old",
            "x-goog-api-key": "old-key",
            "User-Agent": "ua",
        },
        api_key="new-key",
    )
    assert prepared["x-goog-api-key"] == "new-key"
    assert "Authorization" not in prepared
    assert prepared["User-Agent"] == "ua"


@pytest.mark.asyncio
async def test_gemini_forward_url_construction():
    client = GeminiClient()
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.request.return_value = MagicMock(
            status_code=200,
            headers={},
            text='{"ok":true}',
            json=lambda: {"ok": True},
        )
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        await client.forward(
            base_url="https://generativelanguage.googleapis.com",
            api_key="k",
            path="/v1beta/models/gemini-2.0-flash:generateContent",
            method="POST",
            headers={},
            body={"contents": [{"parts": [{"text": "hi"}]}]},
            target_model="gemini-2.0-flash",
        )

        call_args = mock_client.request.call_args
        assert (
            call_args.kwargs["url"]
            == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        )


@pytest.mark.asyncio
async def test_gemini_list_models_path():
    client = GeminiClient()
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.request.return_value = MagicMock(
            status_code=200,
            headers={},
            text='{"models":[]}',
            json=lambda: {"models": []},
        )
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        await client.list_models(
            base_url="https://generativelanguage.googleapis.com",
            api_key="k",
        )

        call_args = mock_client.request.call_args
        assert (
            call_args.kwargs["url"]
            == "https://generativelanguage.googleapis.com/v1beta/models"
        )


@pytest.mark.asyncio
async def test_gemini_list_models_strips_models_prefix():
    """list_models should strip 'models/' prefix from model names."""
    client = GeminiClient()
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.request.return_value = MagicMock(
            status_code=200,
            headers={},
            text='{"models":[{"name":"models/gemini-2.0-flash"},{"name":"models/gemini-1.5-pro"}]}',
            json=lambda: {
                "models": [
                    {"name": "models/gemini-2.0-flash"},
                    {"name": "models/gemini-1.5-pro"},
                ]
            },
        )
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await client.list_models(
            base_url="https://generativelanguage.googleapis.com",
            api_key="k",
        )

        assert result.body["models"][0]["name"] == "gemini-2.0-flash"
        assert result.body["models"][1]["name"] == "gemini-1.5-pro"


def test_strip_model_name_prefix_no_op_for_non_dict():
    """_strip_model_name_prefix should be a no-op for non-dict bodies."""
    client = GeminiClient()
    body = "not a dict"
    client._strip_model_name_prefix(body)
    assert body == "not a dict"


def test_strip_model_name_prefix_preserves_names_without_prefix():
    """Names without 'models/' prefix should not be modified."""
    body = {"models": [{"name": "gemini-2.0-flash"}]}
    GeminiClient._strip_model_name_prefix(body)
    assert body["models"][0]["name"] == "gemini-2.0-flash"
