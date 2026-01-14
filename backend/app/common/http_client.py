"""
HTTP Client Wrapper Module

Provides a unified asynchronous HTTP client for communicating with upstream providers.
"""

from typing import Any, AsyncGenerator, Optional

import httpx

from app.config import get_settings


class HttpClient:
    """
    Asynchronous HTTP Client Wrapper
    
    Wraps httpx.AsyncClient, providing unified request methods and timeout configuration.
    Supports normal requests and streaming requests.
    """
    
    def __init__(
        self,
        base_url: str = "",
        timeout: Optional[int] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        """
        Initialize HTTP Client
        
        Args:
            base_url: Base URL
            timeout: Request timeout (seconds), defaults to configuration
            headers: Default request headers
        """
        settings = get_settings()
        self.base_url = base_url
        self.timeout = timeout or settings.HTTP_TIMEOUT
        self.default_headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client instance
        
        Returns:
            httpx.AsyncClient: HTTP client instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self.default_headers,
            )
        return self._client
    
    async def close(self) -> None:
        """Close HTTP Client"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        json: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Send HTTP Request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL (relative to base_url)
            headers: Request headers
            json: JSON request body
            **kwargs: Other httpx parameters
        
        Returns:
            httpx.Response: HTTP response
        """
        client = await self._get_client()
        return await client.request(
            method=method,
            url=url,
            headers=headers,
            json=json,
            **kwargs,
        )
    
    async def post(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        json: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Send POST Request
        
        Args:
            url: Request URL
            headers: Request headers
            json: JSON request body
            **kwargs: Other parameters
        
        Returns:
            httpx.Response: HTTP response
        """
        return await self.request("POST", url, headers=headers, json=json, **kwargs)
    
    async def stream_request(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        json: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[bytes, None]:
        """
        Send Streaming Request
        
        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            json: JSON request body
            **kwargs: Other parameters
        
        Yields:
            bytes: Response data chunk
        """
        client = await self._get_client()
        async with client.stream(
            method=method,
            url=url,
            headers=headers,
            json=json,
            **kwargs,
        ) as response:
            async for chunk in response.aiter_bytes():
                yield chunk


async def create_client(
    base_url: str,
    api_key: Optional[str] = None,
    timeout: Optional[int] = None,
) -> HttpClient:
    """
    Create configured HTTP client
    
    Args:
        base_url: Base URL
        api_key: API Key (used for Authorization header)
        timeout: Timeout duration
    
    Returns:
        HttpClient: Configured client instance
    """
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    return HttpClient(base_url=base_url, timeout=timeout, headers=headers)