"""
模型映射领域模型

定义模型映射和模型-供应商映射相关的数据传输对象（DTO）。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelMappingBase(BaseModel):
    """模型映射基础模型"""
    
    # 请求模型名（主键）
    requested_model: str = Field(
        ..., min_length=1, max_length=100, description="请求模型名"
    )
    # 选择策略，当前仅支持 round_robin
    strategy: str = Field("round_robin", description="选择策略")


class ModelMappingCreate(ModelMappingBase):
    """创建模型映射请求模型"""
    
    # 模型级匹配规则
    matching_rules: Optional[dict[str, Any]] = Field(None, description="匹配规则")
    # 模型能力描述
    capabilities: Optional[dict[str, Any]] = Field(None, description="模型能力")
    # 是否激活
    is_active: bool = Field(True, description="是否激活")


class ModelMappingUpdate(BaseModel):
    """更新模型映射请求模型"""
    
    strategy: Optional[str] = None
    matching_rules: Optional[dict[str, Any]] = None
    capabilities: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class ModelMapping(ModelMappingBase):
    """模型映射完整模型"""
    
    matching_rules: Optional[dict[str, Any]] = None
    capabilities: Optional[dict[str, Any]] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ModelMappingResponse(ModelMapping):
    """模型映射响应模型（含供应商数量）"""
    
    # 关联的供应商数量
    provider_count: int = Field(0, description="关联供应商数量")
    # 关联的供应商列表（详情查询时返回）
    providers: Optional[list["ModelMappingProviderResponse"]] = None
    
    class Config:
        from_attributes = True


# ============ 模型-供应商映射 ============

class ModelMappingProviderBase(BaseModel):
    """模型-供应商映射基础模型"""
    
    # 请求模型名
    requested_model: str = Field(..., description="请求模型名")
    # 供应商 ID
    provider_id: int = Field(..., description="供应商 ID")
    # 目标模型名（该供应商使用的实际模型）
    target_model_name: str = Field(..., min_length=1, max_length=100, description="目标模型名")


class ModelMappingProviderCreate(ModelMappingProviderBase):
    """创建模型-供应商映射请求模型"""
    
    # 供应商级匹配规则
    provider_rules: Optional[dict[str, Any]] = Field(None, description="供应商级规则")
    # 优先级（数值越小优先级越高）
    priority: int = Field(0, description="优先级")
    # 权重
    weight: int = Field(1, ge=1, description="权重")
    # 是否激活
    is_active: bool = Field(True, description="是否激活")


class ModelMappingProviderUpdate(BaseModel):
    """更新模型-供应商映射请求模型"""
    
    target_model_name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider_rules: Optional[dict[str, Any]] = None
    priority: Optional[int] = None
    weight: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class ModelMappingProvider(ModelMappingProviderBase):
    """模型-供应商映射完整模型"""
    
    id: int
    provider_rules: Optional[dict[str, Any]] = None
    priority: int = 0
    weight: int = 1
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ModelMappingProviderResponse(ModelMappingProvider):
    """模型-供应商映射响应模型（含供应商名称）"""
    
    # 供应商名称
    provider_name: str = Field("", description="供应商名称")
    # 供应商协议类型：openai 或 anthropic
    provider_protocol: Optional[str] = Field(None, description="供应商协议类型")
    
    class Config:
        from_attributes = True


# 解决循环引用
ModelMappingResponse.model_rebuild()
