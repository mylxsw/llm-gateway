"""
Jev Protocol Client

Implements TypeSafe Jev request forwarding.

The Jev protocol has a single inference endpoint (``POST /v1/systemone``) that
takes JSON and returns JSON. It has no streaming mode, no multipart uploads and
no tool calling, so this client is a thin JSON forwarder.
"""

import json
import logging
from typing import Any, AsyncGenerator, Optional

import httpx

from app.common.upstream_url import build_upstream_url
from app.common.timer import Timer
from app.config import get_settings
from app.providers.base import ProviderClient, ProviderResponse

logger = logging.getLogger(__name__)


class JevClient(ProviderClient):
    """
    Jev Protocol Client

    Supports the TypeSafe evaluation API:
    - /v1/systemone
    - /v1/models
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
        proxy_config: Optional[dict[str, str]] = None,
        response_timeout_seconds: Optional[int] = None,
    ) -> ProviderResponse:
        """
        Forward request to a Jev-compatible provider

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
            proxy_config: httpx proxy configuration
            response_timeout_seconds: No-response timeout in seconds

        Returns:
            ProviderResponse: Provider response
        """
        url = build_upstream_url(base_url, path)
        prepared_body = self._prepare_body(body, target_model)
        prepared_headers = self._prepare_headers(headers, api_key, extra_headers)
        prepared_headers["Content-Type"] = "application/json"

        logger.debug(
            "Jev Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(prepared_body, ensure_ascii=False),
        )

        timer = Timer().start()

        try:
            proxy_url = proxy_config.get("all://") if proxy_config else None
            timeout = self._resolve_timeout(response_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout, proxy=proxy_url) as client:
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
        List available models from a Jev-compatible provider

        Returns ``{"models": [{"name", "description", "release_date"}]}``, which
        ``ProviderService._extract_model_ids`` already understands.
        """
        url = build_upstream_url(base_url, "/v1/models")
        prepared_headers = self._prepare_headers({}, api_key, extra_headers)

        logger.debug(
            "Jev List Models: url=%s headers=%s",
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
        response_timeout_seconds: Optional[int] = None,
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        """
        Streaming is not part of the Jev protocol.

        Yields a single 400 response so the caller sees a normal upstream
        failure instead of an unhandled exception.
        """
        logger.warning("Jev protocol does not support streaming requests: path=%s", path)
        yield b"", ProviderResponse(
            status_code=400,
            error="Jev protocol does not support streaming requests",
        )
