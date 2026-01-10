"""
请求日志领域模型

定义请求日志相关的数据传输对象（DTO）。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RequestLogBase(BaseModel):
    """请求日志基础模型"""
    
    # 请求时间
    request_time: datetime = Field(..., description="请求时间")
    # API Key ID
    api_key_id: Optional[int] = Field(None, description="API Key ID")
    # API Key 名称
    api_key_name: Optional[str] = Field(None, description="API Key 名称")
    # 请求模型名
    requested_model: Optional[str] = Field(None, description="请求模型名")
    # 目标模型名
    target_model: Optional[str] = Field(None, description="目标模型名")
    # 供应商 ID
    provider_id: Optional[int] = Field(None, description="供应商 ID")
    # 供应商名称
    provider_name: Optional[str] = Field(None, description="供应商名称")


class RequestLogCreate(RequestLogBase):
    """创建请求日志模型"""
    
    # 重试次数
    retry_count: int = Field(0, description="重试次数")
    # 首字节延迟（毫秒）
    first_byte_delay_ms: Optional[int] = Field(None, description="首字节延迟")
    # 总耗时（毫秒）
    total_time_ms: Optional[int] = Field(None, description="总耗时")
    # 输入 Token 数
    input_tokens: Optional[int] = Field(None, description="输入 Token 数")
    # 输出 Token 数
    output_tokens: Optional[int] = Field(None, description="输出 Token 数")
    # 请求头（已脱敏）
    request_headers: Optional[dict[str, Any]] = Field(None, description="请求头")
    # 请求体
    request_body: Optional[dict[str, Any]] = Field(None, description="请求体")
    # 响应状态码
    response_status: Optional[int] = Field(None, description="响应状态码")
    # 响应体
    response_body: Optional[str] = Field(None, description="响应体")
    # 错误信息
    error_info: Optional[str] = Field(None, description="错误信息")
    # 匹配到的供应商数量
    matched_provider_count: Optional[int] = Field(None, description="匹配到的供应商数量")
    # 追踪 ID
    trace_id: Optional[str] = Field(None, description="追踪 ID")


class RequestLogModel(RequestLogCreate):
    """请求日志完整模型"""
    
    id: int = Field(..., description="日志 ID")
    
    class Config:
        from_attributes = True


class RequestLogResponse(RequestLogBase):
    """请求日志响应模型（列表展示）"""
    
    id: int = Field(..., description="日志 ID")
    retry_count: int = Field(0, description="重试次数")
    matched_provider_count: Optional[int] = None
    first_byte_delay_ms: Optional[int] = None
    total_time_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    response_status: Optional[int] = None
    trace_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class RequestLogDetailResponse(RequestLogModel):
    """请求日志详情响应模型"""

    response_body: Optional[Any] = Field(None, description="响应体（自动解析 JSON）")
    
    class Config:
        from_attributes = True


class RequestLogQuery(BaseModel):
    """请求日志查询条件"""
    
    # 时间范围
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    # 模型过滤
    requested_model: Optional[str] = Field(None, description="请求模型（模糊匹配）")
    target_model: Optional[str] = Field(None, description="目标模型（模糊匹配）")
    # 供应商过滤
    provider_id: Optional[int] = Field(None, description="供应商 ID")
    # 状态码过滤
    status_min: Optional[int] = Field(None, description="最小状态码")
    status_max: Optional[int] = Field(None, description="最大状态码")
    # 是否有错误
    has_error: Optional[bool] = Field(None, description="是否有错误")
    # API Key 过滤
    api_key_id: Optional[int] = Field(None, description="API Key ID")
    api_key_name: Optional[str] = Field(None, description="API Key 名称")
    # 重试次数过滤
    retry_count_min: Optional[int] = Field(None, description="最小重试次数")
    retry_count_max: Optional[int] = Field(None, description="最大重试次数")
    # Token 过滤
    input_tokens_min: Optional[int] = Field(None, description="最小输入 Token")
    input_tokens_max: Optional[int] = Field(None, description="最大输入 Token")
    # 耗时过滤
    total_time_min: Optional[int] = Field(None, description="最小耗时（毫秒）")
    total_time_max: Optional[int] = Field(None, description="最大耗时（毫秒）")
    # 分页
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
    # 排序
    sort_by: str = Field("request_time", description="排序字段")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="排序方向")
