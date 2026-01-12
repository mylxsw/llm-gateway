"""
OpenAI Protocol Client

Implements OpenAI-compatible request forwarding.
"""

import json
import logging
from typing import Any, AsyncGenerator, Optional

import httpx

from app.common.timer import Timer
from app.config import get_settings
from app.providers.base import ProviderClient, ProviderResponse

logger = logging.getLogger(__name__)


class OpenAIClient(ProviderClient):
    """
    OpenAI Protocol Client
    
    Supports OpenAI-style API request forwarding, including:
    - /v1/chat/completions
    - /v1/completions
    - /v1/embeddings
    """
    
    def __init__(self):
        """Initialize client"""
        settings = get_settings()
        self.timeout = settings.HTTP_TIMEOUT
    
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
    ) -> ProviderResponse:
        """
        Forward request to OpenAI-compatible provider
        
        Args:
            base_url: Provider base URL
            api_key: Provider API Key
            path: Request path
            method: HTTP method
            headers: Request headers
            body: Request body
            target_model: Target model name
            response_mode: Response mode, "parsed" (parse JSON) or "raw" (return raw bytes)
            extra_headers: Extra headers
        
        Returns:
            ProviderResponse: Provider response
        """
        # Prepare request
        cleaned_base = base_url.rstrip('/')
        cleaned_path = path
        if cleaned_path.startswith('/v1/'):
            cleaned_path = cleaned_path[3:]
        elif cleaned_path == '/v1':
            cleaned_path = ''
        url = f"{cleaned_base}{cleaned_path}"
        prepared_body = self._prepare_body(body, target_model)
        prepared_headers = self._prepare_headers(headers, api_key, extra_headers)
        
        # Ensure Content-Type is correct
        prepared_headers["Content-Type"] = "application/json"
        
        logger.debug(
            "OpenAI Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(prepared_body, ensure_ascii=False),
        )
        
        timer = Timer().start()
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=prepared_headers,
                    json=prepared_body,
                )
                
                timer.mark_first_byte()
                
                if response_mode == "raw":
                    response_body: Any = response.content
                else:
                    response_body = response.text
                    try:
                        response_body = response.json()
                    except json.JSONDecodeError:
                        pass
                
                timer.stop()
                
                return ProviderResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response_body,
                    first_byte_delay_ms=timer.first_byte_delay_ms,
                    total_time_ms=timer.total_time_ms,
                )
        
        except httpx.TimeoutException as e:
            timer.stop()
            return ProviderResponse(
                status_code=504,
                error=f"Request timeout: {str(e)}",
                first_byte_delay_ms=timer.first_byte_delay_ms,
                total_time_ms=timer.total_time_ms,
            )
        
        except httpx.RequestError as e:
            timer.stop()
            return ProviderResponse(
                status_code=502,
                error=f"Request error: {str(e)}",
                first_byte_delay_ms=timer.first_byte_delay_ms,
                total_time_ms=timer.total_time_ms,
            )
        
        except Exception as e:
            timer.stop()
            return ProviderResponse(
                status_code=500,
                error=f"Unexpected error: {str(e)}",
                first_byte_delay_ms=timer.first_byte_delay_ms,
                total_time_ms=timer.total_time_ms,
            )
    
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
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        """
        Forward streaming request to OpenAI-compatible provider
        
        Args:
            base_url: Provider base URL
            api_key: Provider API Key
            path: Request path
            method: HTTP method
            headers: Request headers
            body: Request body
            target_model: Target model name
            extra_headers: Extra headers
        
        Yields:
            tuple[bytes, ProviderResponse]: (Data chunk, Response info)
        """
        # Prepare request
        cleaned_base = base_url.rstrip('/')
        cleaned_path = path
        if cleaned_path.startswith('/v1/'):
            cleaned_path = cleaned_path[3:]
        elif cleaned_path == '/v1':
            cleaned_path = ''
        url = f"{cleaned_base}{cleaned_path}"
        prepared_body = self._prepare_body(body, target_model)
        prepared_headers = self._prepare_headers(headers, api_key, extra_headers)
        prepared_headers["Content-Type"] = "application/json"
        
        logger.debug(
            "OpenAI Stream Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(prepared_body, ensure_ascii=False),
        )
        
        timer = Timer().start()
        first_chunk = True
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    method=method,
                    url=url,
                    headers=prepared_headers,
                    json=prepared_body,
                ) as response:
                    # Create response object
                    provider_response = ProviderResponse(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                    )
                    
                    async for chunk in response.aiter_bytes():
                        if first_chunk:
                            timer.mark_first_byte()
                            provider_response.first_byte_delay_ms = (
                                timer.first_byte_delay_ms
                            )
                            first_chunk = False
                        
                        yield chunk, provider_response
                    
                    timer.stop()
                    provider_response.total_time_ms = timer.total_time_ms
        
        except httpx.TimeoutException as e:
            timer.stop()
            yield b"", ProviderResponse(
                status_code=504,
                error=f"Request timeout: {str(e)}",
                first_byte_delay_ms=timer.first_byte_delay_ms,
                total_time_ms=timer.total_time_ms,
            )
        
        except httpx.RequestError as e:
            timer.stop()
            yield b"", ProviderResponse(
                status_code=502,
                error=f"Request error: {str(e)}",
                first_byte_delay_ms=timer.first_byte_delay_ms,
                total_time_ms=timer.total_time_ms,
            )