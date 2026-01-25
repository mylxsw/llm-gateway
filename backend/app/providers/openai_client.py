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
    - /v1/audio/*
    - /v1/images/generations
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
        multipart = self._split_multipart_body(prepared_body)
        prepared_headers = self._prepare_headers(headers, api_key, extra_headers)
        prepared_files = None
        prepared_data = None

        if multipart is not None:
            prepared_data, prepared_files = multipart
        else:
            # Ensure Content-Type is correct
            prepared_headers["Content-Type"] = "application/json"
        
        log_body = prepared_body
        if multipart is not None and isinstance(prepared_body, dict):
            safe_files = []
            for item in prepared_body.get("_files", []):
                if not isinstance(item, dict):
                    continue
                data = item.get("data")
                safe_files.append(
                    {
                        "field": item.get("field"),
                        "filename": item.get("filename"),
                        "content_type": item.get("content_type"),
                        "size": len(data) if isinstance(data, (bytes, bytearray)) else None,
                    }
                )
            log_body = {**prepared_body, "_files": safe_files}

        logger.debug(
            "OpenAI Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(log_body, ensure_ascii=False),
        )
        
        timer = Timer().start()
        
        try:
            proxy_url = proxy_config.get("all://") if proxy_config else None
            async with httpx.AsyncClient(timeout=self.timeout, proxy=proxy_url) as client:
                request_kwargs: dict[str, Any] = {
                    "method": method,
                    "url": url,
                    "headers": prepared_headers,
                }
                if prepared_files is not None:
                    request_kwargs["data"] = prepared_data
                    request_kwargs["files"] = prepared_files
                else:
                    request_kwargs["json"] = prepared_body

                response = await client.request(**request_kwargs)
                
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
        List available models from OpenAI-compatible provider
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
            "OpenAI List Models: url=%s headers=%s",
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
        multipart = self._split_multipart_body(prepared_body)
        prepared_headers = self._prepare_headers(headers, api_key, extra_headers)
        prepared_files = None
        prepared_data = None

        if multipart is not None:
            prepared_data, prepared_files = multipart
        else:
            prepared_headers["Content-Type"] = "application/json"
        
        log_body = prepared_body
        if multipart is not None and isinstance(prepared_body, dict):
            safe_files = []
            for item in prepared_body.get("_files", []):
                if not isinstance(item, dict):
                    continue
                data = item.get("data")
                safe_files.append(
                    {
                        "field": item.get("field"),
                        "filename": item.get("filename"),
                        "content_type": item.get("content_type"),
                        "size": len(data) if isinstance(data, (bytes, bytearray)) else None,
                    }
                )
            log_body = {**prepared_body, "_files": safe_files}

        logger.debug(
            "OpenAI Stream Request: method=%s url=%s headers=%s body=%s",
            method,
            url,
            prepared_headers,
            json.dumps(log_body, ensure_ascii=False),
        )
        
        timer = Timer().start()
        first_chunk = True
        
        try:
            proxy_url = proxy_config.get("all://") if proxy_config else None
            async with httpx.AsyncClient(timeout=self.timeout, proxy=proxy_url) as client:
                stream_kwargs: dict[str, Any] = {
                    "method": method,
                    "url": url,
                    "headers": prepared_headers,
                }
                if prepared_files is not None:
                    stream_kwargs["data"] = prepared_data
                    stream_kwargs["files"] = prepared_files
                else:
                    stream_kwargs["json"] = prepared_body

                async with client.stream(**stream_kwargs) as response:
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

    def _split_multipart_body(
        self, body: dict[str, Any]
    ) -> Optional[tuple[list[tuple[str, str]], list[tuple[str, tuple[str, bytes, str]]]]]:
        if not isinstance(body, dict) or "_files" not in body:
            return None

        files_payload: list[tuple[str, tuple[str, bytes, str]]] = []
        for item in body.get("_files", []):
            if not isinstance(item, dict):
                continue
            data = item.get("data")
            if not isinstance(data, (bytes, bytearray)):
                continue
            filename = item.get("filename") or "file"
            content_type = item.get("content_type") or "application/octet-stream"
            files_payload.append(
                (
                    item.get("field") or "file",
                    (filename, bytes(data), content_type),
                )
            )

        if not files_payload:
            return None

        data_payload: list[tuple[str, str]] = []
        for key, value in body.items():
            if key == "_files":
                continue
            if isinstance(value, list):
                for item in value:
                    data_payload.append((key, str(item)))
            elif value is not None:
                data_payload.append((key, str(value)))

        return data_payload, files_payload
