"""
Google Gemini Native API Client

Implements Google Gemini native API request forwarding.
"""

import json
import logging
from typing import Any, AsyncGenerator, Optional

import httpx

from app.common.timer import Timer
from app.config import get_settings
from app.providers.base import ProviderClient, ProviderResponse

logger = logging.getLogger(__name__)


class GeminiClient(ProviderClient):
    """Google Gemini native API client."""

    def __init__(self):
        settings = get_settings()
        self.timeout = settings.HTTP_TIMEOUT

    def _prepare_headers(
        self,
        headers: dict[str, str],
        api_key: Optional[str],
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        new_headers = dict(headers)

        keys_to_remove = [
            "authorization",
            "x-api-key",
            "api-key",
            "x-goog-api-key",
            "content-length",
            "host",
            "content-type",
            "accept-encoding",
        ]
        for key in list(new_headers.keys()):
            if key.lower() in keys_to_remove:
                del new_headers[key]

        if api_key:
            new_headers["x-goog-api-key"] = api_key

        if extra_headers:
            new_headers.update(extra_headers)

        return new_headers

    @staticmethod
    def _build_url(base_url: str, path: str) -> str:
        cleaned_base = base_url.rstrip("/")
        cleaned_path = path if path.startswith("/") else f"/{path}"
        return f"{cleaned_base}{cleaned_path}"

    @staticmethod
    def _strip_model_name_prefix(body: Any) -> None:
        """Strip 'models/' prefix from model names in list_models response in-place."""
        if not isinstance(body, dict):
            return
        models = body.get("models")
        if not isinstance(models, list):
            return
        for model in models:
            if not isinstance(model, dict):
                continue
            name = model.get("name")
            if isinstance(name, str) and name.startswith("models/"):
                model["name"] = name[len("models/"):]

    async def forward(
        self,
        base_url: str,
        api_key: Optional[str],
        path: str,
        method: str,
        headers: dict[str, str],
        body: dict[str, Any],
        target_model: str,  # Gemini model is encoded in the URL path, not in body
        response_mode: str = "parsed",
        extra_headers: Optional[dict[str, str]] = None,
        proxy_config: Optional[dict[str, str]] = None,
    ) -> ProviderResponse:
        url = self._build_url(base_url, path)
        prepared_headers = self._prepare_headers(headers, api_key, extra_headers)
        prepared_headers["Content-Type"] = "application/json"

        logger.debug(
            "Gemini Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(body, ensure_ascii=False),
        )

        timer = Timer().start()

        try:
            proxy_url = proxy_config.get("all://") if proxy_config else None
            async with httpx.AsyncClient(timeout=self.timeout, proxy=proxy_url) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=prepared_headers,
                    json=body,
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
        url = self._build_url(base_url, "/v1beta/models")
        prepared_headers = self._prepare_headers({}, api_key, extra_headers)

        logger.debug(
            "Gemini List Models: url=%s headers=%s",
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

                # Strip "models/" prefix from model names
                self._strip_model_name_prefix(response_body)

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
        target_model: str,  # Gemini model is encoded in the URL path, not in body
        extra_headers: Optional[dict[str, str]] = None,
        proxy_config: Optional[dict[str, str]] = None,
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        url = self._build_url(base_url, path)
        prepared_headers = self._prepare_headers(headers, api_key, extra_headers)
        prepared_headers["Content-Type"] = "application/json"

        logger.debug(
            "Gemini Stream Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(body, ensure_ascii=False),
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
                    json=body,
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
