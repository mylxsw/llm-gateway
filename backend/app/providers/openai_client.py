"""
OpenAI 协议客户端

实现 OpenAI 兼容的请求转发。
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
    OpenAI 协议客户端
    
    支持 OpenAI 风格的 API 请求转发，包括：
    - /v1/chat/completions
    - /v1/completions
    - /v1/embeddings
    """
    
    def __init__(self):
        """初始化客户端"""
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
        转发请求到 OpenAI 兼容供应商
        
        Args:
            base_url: 供应商基础 URL
            api_key: 供应商 API Key
            path: 请求路径
            method: HTTP 方法
            headers: 请求头
            body: 请求体
            target_model: 目标模型名
            response_mode: 响应模式，"parsed" (解析 JSON) 或 "raw" (返回原始 bytes)
            extra_headers: 额外请求头
        
        Returns:
            ProviderResponse: 供应商响应
        """
        # 准备请求
        # 准备请求
        cleaned_base = base_url.rstrip('/')
        cleaned_path = path
        if cleaned_path.startswith('/v1/'):
            cleaned_path = cleaned_path[3:]
        elif cleaned_path == '/v1':
            cleaned_path = ''
        url = f"{cleaned_base}{cleaned_path}"
        prepared_body = self._prepare_body(body, target_model)
        prepared_headers = self._prepare_headers(headers, api_key, extra_headers)
        
        # 确保 Content-Type 正确
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
        转发流式请求到 OpenAI 兼容供应商
        
        Args:
            base_url: 供应商基础 URL
            api_key: 供应商 API Key
            path: 请求路径
            method: HTTP 方法
            headers: 请求头
            body: 请求体
            target_model: 目标模型名
            extra_headers: 额外请求头
        
        Yields:
            tuple[bytes, ProviderResponse]: (数据块, 响应信息)
        """
        # 准备请求
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
                    # 创建响应对象
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