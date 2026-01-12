"""
供应商领域模型

定义供应商相关的数据传输对象（DTO）。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ProviderBase(BaseModel):
    """供应商基础模型"""
    
    # 供应商名称
    name: str = Field(..., min_length=1, max_length=100, description="供应商名称")
    # 接口基础地址
    base_url: str = Field(..., description="接口基础地址")
    # 协议类型：openai 或 anthropic
    protocol: str = Field(..., pattern="^(openai|anthropic)$", description="协议类型")
    # API 类型：chat / completion / embedding
    api_type: str = Field(..., description="API 类型")
    # 额外请求头
    extra_headers: Optional[dict[str, str]] = Field(None, description="额外请求头")


class ProviderCreate(ProviderBase):
    """创建供应商请求模型"""
    
    # 供应商的 API Key（可选）
    api_key: Optional[str] = Field(None, description="供应商 API Key")
    # 是否激活
    is_active: bool = Field(True, description="是否激活")


class ProviderUpdate(BaseModel):
    """更新供应商请求模型（所有字段可选）"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = None
    protocol: Optional[str] = Field(None, pattern="^(openai|anthropic)$")
    api_type: Optional[str] = None
    api_key: Optional[str] = None
    extra_headers: Optional[dict[str, str]] = None
    is_active: Optional[bool] = None


class Provider(ProviderBase):
    """供应商完整模型"""
    
    id: int = Field(..., description="供应商 ID")
    api_key: Optional[str] = Field(None, description="供应商 API Key")
    extra_headers: Optional[dict[str, str]] = Field(None, description="额外请求头")
    is_active: bool = Field(True, description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True


class ProviderResponse(ProviderBase):
    """供应商响应模型（API Key 脱敏）"""
    
    id: int = Field(..., description="供应商 ID")
    # API Key 脱敏显示
    api_key: Optional[str] = Field(None, description="供应商 API Key（脱敏）")
    extra_headers: Optional[dict[str, str]] = Field(None, description="额外请求头")
    is_active: bool = Field(True, description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    class Config:
        from_attributes = True
