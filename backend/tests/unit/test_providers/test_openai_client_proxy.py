
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.providers.openai_client import OpenAIClient

@pytest.mark.asyncio
async def test_openai_client_proxy_config_passing():
    client = OpenAIClient()
    
    base_url = "https://api.openai.com"
    path = "/v1/chat/completions"
    proxy_config = {"all://": "http://proxy.example.com"}
    
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
            target_model="gpt-3.5-turbo",
            proxy_config=proxy_config
        )
        
        # Verify AsyncClient was initialized with proxy argument
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        
        # Check that 'proxies' is NOT present and 'proxy' IS present
        assert "proxies" not in call_kwargs
        assert "proxy" in call_kwargs
        assert call_kwargs["proxy"] == "http://proxy.example.com"

@pytest.mark.asyncio
async def test_openai_client_stream_proxy_config_passing():
    client = OpenAIClient()
    
    base_url = "https://api.openai.com"
    path = "/v1/chat/completions"
    proxy_config = {"all://": "http://proxy.example.com"}
    
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        
        # Setup for stream: client.stream should be a MagicMock (not AsyncMock) 
        # returning an async context manager
        mock_client.stream = MagicMock()
        
        # Response should be a MagicMock (so methods aren't auto-AsyncMocked inappropriately)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        
        async def async_iter():
            yield b"chunk"
        
        # aiter_bytes returns the async iterator
        mock_response.aiter_bytes.return_value = async_iter()
        
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_stream_ctx.__aexit__.return_value = None
        
        mock_client.stream.return_value = mock_stream_ctx
        
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        async for _ in client.forward_stream(
            base_url=base_url,
            api_key="sk-test",
            path=path,
            method="POST",
            headers={},
            body={"model": "gpt-3.5-turbo"},
            target_model="gpt-3.5-turbo",
            proxy_config=proxy_config
        ):
            pass
        
        # Verify AsyncClient was initialized with proxy argument
        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        
        # Check that 'proxies' is NOT present and 'proxy' IS present
        assert "proxies" not in call_kwargs
        assert "proxy" in call_kwargs
        assert call_kwargs["proxy"] == "http://proxy.example.com"
