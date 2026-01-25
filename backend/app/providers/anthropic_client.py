"""
Anthropic Protocol Client

Implements Anthropic-compatible request forwarding.
"""

import json
import logging
from typing import Any, AsyncGenerator, Optional

import httpx

from app.common.timer import Timer
from app.config import get_settings
from app.providers.base import ProviderClient, ProviderResponse

logger = logging.getLogger(__name__)


class AnthropicClient(ProviderClient):
    """
    Anthropic Protocol Client
    
    Supports Anthropic-style API request forwarding, including:
    - /v1/messages
    """
    
    # Anthropic API Version
    ANTHROPIC_VERSION = "2023-06-01"
    
    def __init__(self):
        """Initialize client"""
        settings = get_settings()
        self.timeout = settings.HTTP_TIMEOUT
    
    def _prepare_headers(
        self,
        headers: dict[str, str],
        api_key: Optional[str],
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        """
        Prepare Anthropic request headers
        
        Anthropic uses x-api-key header for authentication.
        
        Args:
            headers: Original request headers
            api_key: Provider API Key
            extra_headers: Extra headers
        
        Returns:
            dict: Processed request headers
        """
        new_headers = dict(headers)
        
        # Remove original authentication headers and auto-generated headers
        keys_to_remove = ["authorization", "x-api-key", "api-key", "content-length", "host", "content-type", "accept-encoding"]
        for key in list(new_headers.keys()):
            if key.lower() in keys_to_remove:
                del new_headers[key]
        
        # Add Anthropic specific header
        if api_key:
            new_headers["x-api-key"] = api_key
        
        # Ensure Anthropic version is set
        if "anthropic-version" not in [k.lower() for k in new_headers.keys()]:
            new_headers["anthropic-version"] = self.ANTHROPIC_VERSION
            
        # Merge extra headers (overwrite existing)
        if extra_headers:
            new_headers.update(extra_headers)
        
        return new_headers
    
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
        Forward request to Anthropic-compatible provider
        
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
            "Anthropic Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(prepared_body, ensure_ascii=False),
        )
        
        timer = Timer().start()
        
        try:
            proxy_url = proxy_config.get("all://") if proxy_config else None
            async with httpx.AsyncClient(timeout=self.timeout, proxy=proxy_url) as client:
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
    
    async def list_models(
        self,
        base_url: str,
        api_key: Optional[str],
        extra_headers: Optional[dict[str, str]] = None,
        proxy_config: Optional[dict[str, str]] = None,
    ) -> ProviderResponse:
        """
        List available models from Anthropic-compatible provider
        """
        cleaned_base = base_url.rstrip('/')
        cleaned_path = "/v1/models"
        if cleaned_path.startswith('/v1/'):
            cleaned_path = cleaned_path[3:]
        elif cleaned_path == '/v1':
            cleaned_path = ''
        url = f"{cleaned_base}{cleaned_path}"
        prepared_headers = self._prepare_headers({}, api_key, extra_headers)

        logger.debug(
            "Anthropic List Models: url=%s headers=%s",
            url,
            prepared_headers,
        )

        timer = Timer().start()

        try:
            proxy_url = proxy_config.get("all://") if proxy_config else None
            async with httpx.AsyncClient(timeout=self.timeout, proxy=proxy_url) as client:
                response = await client.request(
                    method="GET",
                    url=url,
                    headers=prepared_headers,
                )

                timer.mark_first_byte()

                response_body: Any = response.text
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
        proxy_config: Optional[dict[str, str]] = None,
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        """
        Forward streaming request to Anthropic-compatible provider
        
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
            "Anthropic Stream Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(prepared_body, ensure_ascii=False),
        )
        
        timer = Timer().start()
        first_chunk = True
        
        try:
            proxy_url = proxy_config.get("all://") if proxy_config else None
            async with httpx.AsyncClient(timeout=self.timeout, proxy=proxy_url) as client:
                async with client.stream(
                    method=method,
                    url=url,
                    headers=prepared_headers,
                    json=prepared_body,
                ) as response:
                    provider_response = ProviderResponse(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                    )

                    if response.status_code >= 400:
                        body_bytes = await response.aread()
                        timer.mark_first_byte()
                        timer.stop()
                        provider_response.first_byte_delay_ms = timer.first_byte_delay_ms
                        provider_response.total_time_ms = timer.total_time_ms
                        provider_response.body = body_bytes
                        reason = response.reason_phrase or "Upstream error"
                        provider_response.error = f"{response.status_code} {reason}"
                        yield body_bytes or b"", provider_response
                        return
                    
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
