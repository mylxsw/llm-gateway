"""
上游供应商客户端基类

定义供应商客户端的抽象接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Optional


@dataclass
class ProviderResponse:
    """
    供应商响应数据类
    
    封装上游供应商的响应信息。
    """
    
    # HTTP 状态码
    status_code: int
    # 响应头
    headers: dict[str, str] = field(default_factory=dict)
    # 响应体
    body: Any = None
    # 首字节延迟（毫秒）
    first_byte_delay_ms: Optional[int] = None
    # 总耗时（毫秒）
    total_time_ms: Optional[int] = None
    # 错误信息
    error: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        """是否成功响应"""
        return 200 <= self.status_code < 400
    
    @property
    def is_server_error(self) -> bool:
        """是否是服务端错误（状态码 >= 500）"""
        return self.status_code >= 500


class ProviderClient(ABC):
    """
    上游供应商客户端抽象基类
    
    定义供应商客户端的通用接口，包括普通请求和流式请求。
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
    ) -> ProviderResponse:
        """
        转发请求到上游供应商
        
        注意：只允许修改 body 中的 model 字段，其他字段原样转发。
        
        Args:
            base_url: 供应商基础 URL
            api_key: 供应商 API Key
            path: 请求路径（如 /v1/chat/completions）
            method: HTTP 方法
            headers: 请求头（已移除客户端 Authorization）
            body: 请求体
            target_model: 目标模型名
        
        Returns:
            ProviderResponse: 供应商响应
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
    ) -> AsyncGenerator[tuple[bytes, ProviderResponse], None]:
        """
        转发流式请求到上游供应商
        
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
        pass
    
    def _prepare_body(self, body: dict[str, Any], target_model: str) -> dict[str, Any]:
        """
        准备请求体
        
        仅替换 model 字段，其他字段保持不变。
        
        Args:
            body: 原始请求体
            target_model: 目标模型名
        
        Returns:
            dict: 处理后的请求体（新字典）
        """
        new_body = body.copy()
        new_body["model"] = target_model
        return new_body
    
    def _prepare_headers(
        self,
        headers: dict[str, str],
        api_key: Optional[str],
    ) -> dict[str, str]:
        """
        准备请求头
        
        添加供应商 API Key 到 Authorization 头。
        
        Args:
            headers: 原始请求头
            api_key: 供应商 API Key
        
        Returns:
            dict: 处理后的请求头（新字典）
        """
        new_headers = dict(headers)
        
        # 移除原有的认证头和自动生成的头
        keys_to_remove = ["authorization", "x-api-key", "api-key", "content-length", "host", "content-type"]
        for key in list(new_headers.keys()):
            if key.lower() in keys_to_remove:
                del new_headers[key]
        
        # 添加供应商 API Key
        if api_key:
            new_headers["Authorization"] = f"Bearer {api_key}"
        
        return new_headers
