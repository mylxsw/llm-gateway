import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.providers.openai_client import OpenAIClient
from app.providers.base import ProviderResponse

@pytest.mark.asyncio
async def test_openai_client_forward_url_construction():
    client = OpenAIClient()
    
    # Test case 1: base_url without /v1, path with /v1
    # User requirement: strip /v1 from path, append to base_url
    base_url = "https://api.openai.com"
    path = "/v1/chat/completions"
    
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
            body={"model": "gpt-3.5-turbo"},
            target_model="gpt-3.5-turbo"
        )
        
        # Verify call arguments
        call_args = mock_client.request.call_args
        assert call_args is not None
        # Expectation: base_url + (path - /v1)
        # https://api.openai.com + /chat/completions
        assert call_args.kwargs["url"] == "https://api.openai.com/chat/completions"

@pytest.mark.asyncio
async def test_openai_client_forward_url_construction_with_duplicate_v1():
    client = OpenAIClient()
    
    # Test case 2: base_url with /v1, path with /v1
    base_url = "https://api.openai.com/v1"
    path = "/v1/chat/completions"
    
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
            body={"model": "gpt-3.5-turbo"},
            target_model="gpt-3.5-turbo"
        )
        
        # Verify call arguments
        call_args = mock_client.request.call_args
        assert call_args is not None
        # Expectation: base_url + (path - /v1)
        # https://api.openai.com/v1 + /chat/completions
        assert call_args.kwargs["url"] == "https://api.openai.com/v1/chat/completions"