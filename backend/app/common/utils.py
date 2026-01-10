"""
工具函数模块

提供通用的工具函数，如 API Key 生成、Trace ID 生成等。
"""

import json
import secrets
import uuid
from typing import Any, Optional

from app.config import get_settings


def generate_api_key(
    prefix: Optional[str] = None,
    length: Optional[int] = None
) -> str:
    """
    生成随机 API Key
    
    使用 secrets 模块生成密码学安全的随机 token。
    
    Args:
        prefix: Key 前缀，默认使用配置中的 API_KEY_PREFIX
        length: Key 长度（不含前缀），默认使用配置中的 API_KEY_LENGTH
    
    Returns:
        str: 生成的 API Key，格式如 "lgw-xxxxxxxxxxxx"
    
    Example:
        >>> generate_api_key()
        'lgw-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'
    """
    settings = get_settings()
    prefix = prefix or settings.API_KEY_PREFIX
    length = length or settings.API_KEY_LENGTH
    
    # 使用 secrets.token_hex 生成安全的随机字符串
    # token_hex 返回 hex 字符串，长度是字节数的两倍
    random_part = secrets.token_hex(length // 2)
    
    return f"{prefix}{random_part}"


def generate_trace_id() -> str:
    """
    生成请求追踪 ID
    
    使用 UUID4 生成唯一的追踪标识符，用于关联同一请求的日志。
    
    Returns:
        str: UUID 格式的追踪 ID
    
    Example:
        >>> generate_trace_id()
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    """
    return str(uuid.uuid4())


def extract_model_from_body(body: dict) -> Optional[str]:
    """
    从请求体中提取模型名称
    
    支持 OpenAI 和 Anthropic 格式的请求体。
    
    Args:
        body: 请求体字典
    
    Returns:
        Optional[str]: 模型名称，如果不存在则返回 None
    """
    return body.get("model")


def replace_model_in_body(body: dict, target_model: str) -> dict:
    """
    替换请求体中的模型名称
    
    仅修改 model 字段，其他字段保持不变。
    返回新字典，不修改原始数据。
    
    Args:
        body: 原始请求体
        target_model: 目标模型名
    
    Returns:
        dict: 替换后的请求体（新字典）
    """
    new_body = body.copy()
    new_body["model"] = target_model
    return new_body


def mask_string(s: str, visible_start: int = 4, visible_end: int = 2) -> str:
    """
    对字符串进行掩码处理
    
    保留开头和结尾的部分字符，中间用星号替换。
    
    Args:
        s: 原始字符串
        visible_start: 开头保留的字符数
        visible_end: 结尾保留的字符数
    
    Returns:
        str: 掩码后的字符串
    
    Example:
        >>> mask_string("abcdefghijklmnop")
        'abcd***...***op'
    """
    if len(s) <= visible_start + visible_end:
        return "***"
    return f"{s[:visible_start]}***...***{s[-visible_end:]}"


def try_parse_json_object(text: str) -> Any:
    """
    尝试把字符串解析为 JSON 对象/数组

    仅当字符串形态看起来像 JSON object/array（以 { 或 [ 开头）时才尝试解析，
    解析失败则返回原始字符串。
    """
    stripped = text.strip()
    if not stripped:
        return text
    if not (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    ):
        return text
    try:
        return json.loads(stripped)
    except Exception:
        return text
