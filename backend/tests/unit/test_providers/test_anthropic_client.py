import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.providers.anthropic_client import AnthropicClient
from app.providers.base import ProviderResponse

@pytest.mark.asyncio
async def test_anthropic_client_forward_url_construction_duplicate_v1():
    client = AnthropicClient()
    
    # Test case 1: base_url with /v1, path with /v1
    base_url = "https://api.anthropic.com/v1"
    path = "/v1/messages"
    
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.request.return_value = MagicMock(
            status_code=200,
            headers={},
            text='{"id": "test"}',
            json=lambda: {"id": "test"}
        )
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        await client.forward(
            base_url=base_url,
            api_key="sk-test",
            path=path,
            method="POST",
            headers={},
            body={"model": "claude-2"},
            target_model="claude-2"
        )
        
        # Verify call arguments
        call_args = mock_client.request.call_args
        assert call_args is not None
        # Expectation: base_url + (path - /v1)
        # https://api.anthropic.com/v1 + /messages
        assert call_args.kwargs["url"] == "https://api.anthropic.com/v1/messages"

@pytest.mark.asyncio
async def test_anthropic_client_forward_url_construction_no_v1_base():
    client = AnthropicClient()
    
    # Test case 2: base_url without /v1, path with /v1
    # This checks the "pure append" logic requested by user
    base_url = "https://api.anthropic.com"
    path = "/v1/messages"
    
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.request.return_value = MagicMock(
            status_code=200,
            headers={},
            text='{"id": "test"}',
            json=lambda: {"id": "test"}
        )
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        await client.forward(
            base_url=base_url,
            api_key="sk-test",
            path=path,
            method="POST",
            headers={},
            body={"model": "claude-2"},
            target_model="claude-2"
        )
        
        # Verify call arguments
        call_args = mock_client.request.call_args
        assert call_args is not None
        # Expectation: base_url + (path - /v1)
        # https://api.anthropic.com + /messages
        assert call_args.kwargs["url"] == "https://api.anthropic.com/messages"


@pytest.mark.asyncio
async def test_anthropic_client_forward_raw_passthrough_body_bytes():
    client = AnthropicClient()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock(
            status_code=200,
            headers={"content-type": "application/json"},
            text='{"id": "ignored"}',
            content=b'{"id":"raw"}',
        )
        mock_response.json.side_effect = AssertionError("json() should not be called in raw mode")
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        resp = await client.forward(
            base_url="https://api.anthropic.com",
            api_key="sk-test",
            path="/v1/messages",
            method="POST",
            headers={},
            body={"model": "claude-2"},
            target_model="claude-2",
            response_mode="raw",
        )

        assert isinstance(resp, ProviderResponse)
        assert resp.status_code == 200
        assert resp.body == b'{"id":"raw"}'