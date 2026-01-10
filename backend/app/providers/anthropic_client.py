"""
Anthropic 协议客户端

实现 Anthropic 兼容的请求转发。
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
    Anthropic 协议客户端
    
    支持 Anthropic 风格的 API 请求转发，包括：
    - /v1/messages
    """
    
    # Anthropic API 版本
    ANTHROPIC_VERSION = "2023-06-01"
    
    def __init__(self):
        """初始化客户端"""
        settings = get_settings()
        self.timeout = settings.HTTP_TIMEOUT
    
    def _prepare_headers(
        self,
        headers: dict[str, str],
        api_key: Optional[str],
    ) -> dict[str, str]:
        """
        准备 Anthropic 请求头
        
        Anthropic 使用 x-api-key 头进行认证。
        
        Args:
            headers: 原始请求头
            api_key: 供应商 API Key
        
        Returns:
            dict: 处理后的请求头
        """
        new_headers = dict(headers)
        
        # 移除原有的认证头和自动生成的头
        keys_to_remove = ["authorization", "x-api-key", "api-key", "content-length", "host", "content-type"]
        for key in list(new_headers.keys()):
            if key.lower() in keys_to_remove:
                del new_headers[key]
        
        # 添加 Anthropic 特定头
        if api_key:
            new_headers["x-api-key"] = api_key
        
        # 确保设置 Anthropic 版本
        if "anthropic-version" not in [k.lower() for k in new_headers.keys()]:
            new_headers["anthropic-version"] = self.ANTHROPIC_VERSION
        
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
    ) -> ProviderResponse:
        """
        转发请求到 Anthropic 兼容供应商
        
        Args:
            base_url: 供应商基础 URL
            api_key: 供应商 API Key
            path: 请求路径
            method: HTTP 方法
            headers: 请求头
            body: 请求体
            target_model: 目标模型名
        
        Returns:
            ProviderResponse: 供应商响应
        """
        cleaned_base = base_url.rstrip('/')
        cleaned_path = path
        if cleaned_path.startswith('/v1/'):
            cleaned_path = cleaned_path[3:]
        elif cleaned_path == '/v1':
            cleaned_path = ''
        url = f"{cleaned_base}{cleaned_path}"
        prepared_body = self._prepare_body(body, target_model)
        prepared_headers = self._prepare_headers(headers, api_key)
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=prepared_headers,
                    json=prepared_body,
                )
                
                timer.mark_first_byte()
                
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
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        """
        转发流式请求到 Anthropic 兼容供应商
        
        Args:
            base_url: 供应商基础 URL
            api_key: 供应商 API Key
            path: 请求路径
            method: HTTP 方法
            headers: 请求头
            body: 请求体
            target_model: 目标模型名
        
        Yields:
            tuple[bytes, ProviderResponse]: (数据块, 响应信息)
        """
        cleaned_base = base_url.rstrip('/')
        cleaned_path = path
        if cleaned_path.startswith('/v1/'):
            cleaned_path = cleaned_path[3:]
        elif cleaned_path == '/v1':
            cleaned_path = ''
        url = f"{cleaned_base}{cleaned_path}"
        prepared_body = self._prepare_body(body, target_model)
        prepared_headers = self._prepare_headers(headers, api_key)
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
            async with httpx.AsyncClient(timeout=self.timeout) as client:
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
