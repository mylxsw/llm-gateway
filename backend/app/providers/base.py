"""
Upstream Provider Client Base Class

Defines the abstract interface for provider clients.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional


@dataclass
class ProviderResponse:
    """
    Provider Response Data Class
    
    Encapsulates response information from the upstream provider.
    """
    
    # HTTP status code
    status_code: int
    # Response headers
    headers: dict[str, str] = field(default_factory=dict)
    # Response body
    body: Any = None
    # Time to first byte (ms)
    first_byte_delay_ms: Optional[int] = None
    # Total time (ms)
    total_time_ms: Optional[int] = None
    # Error message
    error: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """Whether the response is successful"""
        return 200 <= self.status_code < 400
    
    @property
    def is_server_error(self) -> bool:
        """Whether it is a server error (status code >= 500)"""
        return self.status_code >= 500


class ProviderClient(ABC):
    """
    Upstream Provider Client Abstract Base Class
    
    Defines the common interface for provider clients, including normal requests and streaming requests.
    """
    
    @abstractmethod
    async def forward(
        self,
        base_url: str,
        api_key: Optional[str],
        path: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
        target_model: str,
        response_mode: str = "parsed",
        extra_headers: Optional[dict[str, str]] = None,
        proxy_config: Optional[dict[str, str]] = None,
    ) -> ProviderResponse:
        """
        Forward request to upstream provider
        
        Note: Only the 'model' field in the body is allowed to be modified; other fields are forwarded as-is.
        
        Args:
            base_url: Provider base URL
            api_key: Provider API Key
            path: Request path (e.g., /v1/chat/completions)
            method: HTTP method
            headers: Request headers (client Authorization removed)
            body: Request body
            target_model: Target model name
            response_mode: Response mode, "parsed" (parse JSON) or "raw" (return raw bytes)
            extra_headers: Extra headers
            proxy_config: httpx proxy configuration
        
        Returns:
            ProviderResponse: Provider response
        """
        pass
    
    @abstractmethod
    async def forward_stream(
        self,
        base_url: str,
        api_key: Optional[str],
        path: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
        target_model: str,
        extra_headers: Optional[dict[str, str]] = None,
        proxy_config: Optional[dict[str, str]] = None,
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        """
        Forward streaming request to upstream provider
        
        Args:
            base_url: Provider base URL
            api_key: Provider API Key
            path: Request path
            method: HTTP method
            headers: Request headers
            body: Request body
            target_model: Target model name
            extra_headers: Extra headers
            proxy_config: httpx proxy configuration
        
        Yields:
            tuple[bytes, ProviderResponse]: (Data chunk, Response info)
        """
        pass
    
    def _prepare_body(self, body: dict[str, Any], target_model: str) -> dict[str, Any]:
        """
        Prepare request body
        
        Only replaces the 'model' field, other fields remain unchanged.
        
        Args:
            body: Original request body
            target_model: Target model name
        
        Returns:
            dict: Processed request body (new dictionary)
        """
        new_body = body.copy()
        new_body["model"] = target_model
        return new_body
    
    def _prepare_headers(
        self,
        headers: dict[str, str],
        api_key: Optional[str],
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        """
        Prepare request headers
        
        Adds provider API Key to Authorization header.
        
        Args:
            headers: Original request headers
            api_key: Provider API Key
            extra_headers: Extra headers
        
        Returns:
            dict: Processed request headers (new dictionary)
        """
        new_headers = dict(headers)
        
        # Remove original authentication headers and auto-generated headers
        keys_to_remove = ["authorization", "x-api-key", "api-key", "content-length", "host", "content-type"]
        for key in list(new_headers.keys()):
            if key.lower() in keys_to_remove:
                del new_headers[key]
        
        # Add provider API Key
        if api_key:
            new_headers["Authorization"] = f"Bearer {api_key}"
            
        # Merge extra headers (overwrite existing)
        if extra_headers:
            new_headers.update(extra_headers)
        
        return new_headers
