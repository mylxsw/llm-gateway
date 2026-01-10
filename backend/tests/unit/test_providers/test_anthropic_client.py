import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.providers.anthropic_client import AnthropicClient

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