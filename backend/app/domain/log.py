"""
Request Log Domain Model

Defines Request Log related Data Transfer Objects (DTOs).
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.common.time import ensure_utc


class RequestLogBase(BaseModel):
    """Request Log Base Model"""
    
    # Request Time
    request_time: datetime = Field(..., description="Request Time")
    # API Key ID
    api_key_id: Optional[int] = Field(None, description="API Key ID")
    # API Key Name
    api_key_name: Optional[str] = Field(None, description="API Key Name")
    # Requested Model Name
    requested_model: Optional[str] = Field(None, description="Requested Model Name")
    # Target Model Name
    target_model: Optional[str] = Field(None, description="Target Model Name")
    # Provider ID
    provider_id: Optional[int] = Field(None, description="Provider ID")
    # Provider Name
    provider_name: Optional[str] = Field(None, description="Provider Name")

    @field_validator("request_time", mode="after")
    @classmethod
    def _request_time_utc(cls, v: datetime) -> datetime:
        dt = ensure_utc(v)
        assert dt is not None
        return dt


class RequestLogCreate(RequestLogBase):
    """Create Request Log Model"""

    # Retry Count
    retry_count: int = Field(0, description="Retry Count")
    # First Byte Delay (ms)
    first_byte_delay_ms: Optional[int] = Field(None, description="First Byte Delay")
    # Total Time (ms)
    total_time_ms: Optional[int] = Field(None, description="Total Time")
    # Input Token Count
    input_tokens: Optional[int] = Field(None, description="Input Token Count")
    # Output Token Count
    output_tokens: Optional[int] = Field(None, description="Output Token Count")
    # Cost fields (USD, 4 decimals)
    total_cost: Optional[float] = Field(None, description="Total cost ($)")
    input_cost: Optional[float] = Field(None, description="Input cost ($)")
    output_cost: Optional[float] = Field(None, description="Output cost ($)")
    # Price source: SupplierOverride / ModelFallback / DefaultZero
    price_source: Optional[str] = Field(None, description="Price source")
    # Request Headers (Sanitized)
    request_headers: Optional[dict[str, Any]] = Field(None, description="Request Headers")
    # Request Body
    request_body: Optional[dict[str, Any]] = Field(None, description="Request Body")
    # Response Status Code
    response_status: Optional[int] = Field(None, description="Response Status Code")
    # Response Body
    response_body: Optional[str] = Field(None, description="Response Body")
    # Error Info
    error_info: Optional[str] = Field(None, description="Error Info")
    # Matched Provider Count
    matched_provider_count: Optional[int] = Field(None, description="Matched Provider Count")
    # Trace ID
    trace_id: Optional[str] = Field(None, description="Trace ID")
    # Is Stream Request
    is_stream: bool = Field(False, description="Is Stream Request")
    # Protocol Conversion Fields (for debugging and analysis)
    # Client request protocol (openai/anthropic)
    request_protocol: Optional[str] = Field(None, description="Client Request Protocol")
    # Upstream supplier protocol (openai/anthropic)
    supplier_protocol: Optional[str] = Field(None, description="Upstream Supplier Protocol")
    # Converted request body (sent to upstream after protocol conversion)
    converted_request_body: Optional[dict[str, Any]] = Field(
        None, description="Converted Request Body (after protocol conversion)"
    )
    # Upstream response body (original response before protocol conversion)
    upstream_response_body: Optional[str] = Field(
        None, description="Upstream Response Body (before protocol conversion)"
    )


class RequestLogModel(RequestLogCreate):
    """Request Log Complete Model"""
    
    id: int = Field(..., description="Log ID")
    
    class Config:
        from_attributes = True


class RequestLogResponse(RequestLogBase):
    """Request Log Response Model (List View)"""
    
    id: int = Field(..., description="Log ID")
    retry_count: int = Field(0, description="Retry Count")
    matched_provider_count: Optional[int] = None
    first_byte_delay_ms: Optional[int] = None
    total_time_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_cost: Optional[float] = None
    input_cost: Optional[float] = None
    output_cost: Optional[float] = None
    response_status: Optional[int] = None
    trace_id: Optional[str] = None
    is_stream: bool = False
    
    class Config:
        from_attributes = True


class RequestLogDetailResponse(RequestLogModel):
    """Request Log Detail Response Model"""

    response_body: Optional[Any] = Field(None, description="Response Body (Auto-parsed JSON)")
    
    class Config:
        from_attributes = True


class RequestLogQuery(BaseModel):
    """Request Log Query Conditions"""
    
    # Time Range
    start_time: Optional[datetime] = Field(None, description="Start Time")
    end_time: Optional[datetime] = Field(None, description="End Time")
    # Model Filter
    requested_model: Optional[str] = Field(None, description="Requested Model (Fuzzy Match)")
    target_model: Optional[str] = Field(None, description="Target Model (Fuzzy Match)")
    # Provider Filter
    provider_id: Optional[int] = Field(None, description="Provider ID")
    # Status Code Filter
    status_min: Optional[int] = Field(None, description="Min Status Code")
    status_max: Optional[int] = Field(None, description="Max Status Code")
    # Error Filter
    has_error: Optional[bool] = Field(None, description="Has Error")
    # API Key Filter
    api_key_id: Optional[int] = Field(None, description="API Key ID")
    api_key_name: Optional[str] = Field(None, description="API Key Name")
    # Retry Count Filter
    retry_count_min: Optional[int] = Field(None, description="Min Retry Count")
    retry_count_max: Optional[int] = Field(None, description="Max Retry Count")
    # Token Filter
    input_tokens_min: Optional[int] = Field(None, description="Min Input Tokens")
    input_tokens_max: Optional[int] = Field(None, description="Max Input Tokens")
    # Time Filter
    total_time_min: Optional[int] = Field(None, description="Min Total Time (ms)")
    total_time_max: Optional[int] = Field(None, description="Max Total Time (ms)")
    # Pagination
    page: int = Field(1, ge=1, description="Page Number")
    page_size: int = Field(20, ge=1, le=100, description="Items Per Page")
    # Sorting
    sort_by: str = Field("request_time", description="Sort Field")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort Order")

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def _query_time_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return ensure_utc(v)


class LogCostStatsQuery(BaseModel):
    """Cost statistics query conditions"""

    # Time Range
    start_time: Optional[datetime] = Field(None, description="Start Time")
    end_time: Optional[datetime] = Field(None, description="End Time")
    # Core dimensions
    requested_model: Optional[str] = Field(None, description="Requested Model (Exact or fuzzy)")
    provider_id: Optional[int] = Field(None, description="Provider ID")
    api_key_id: Optional[int] = Field(None, description="API Key ID")
    api_key_name: Optional[str] = Field(None, description="API Key Name (Fuzzy Match)")
    # Bucket granularity: hour/day
    bucket: str = Field("day", pattern="^(hour|day)$", description="Trend bucket")
    # Timezone offset (minutes) applied to request_time before bucketing.
    # Example: UTC+8 => 480, UTC-8 => -480.
    tz_offset_minutes: int = Field(
        0,
        ge=-14 * 60,
        le=14 * 60,
        description="Timezone offset minutes for bucketing (UTC to local)",
    )

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def _stats_time_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        return ensure_utc(v)


class LogCostSummary(BaseModel):
    """Aggregated cost summary"""

    request_count: int = 0
    total_cost: float = 0.0
    input_cost: float = 0.0
    output_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class LogCostTrendPoint(BaseModel):
    """Cost trend point"""

    bucket: datetime
    request_count: int = 0
    total_cost: float = 0.0
    input_cost: float = 0.0
    output_cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error_count: int = 0
    success_count: int = 0

    @field_validator("bucket", mode="after")
    @classmethod
    def _bucket_utc(cls, v: datetime) -> datetime:
        dt = ensure_utc(v)
        assert dt is not None
        return dt


class LogCostByModel(BaseModel):
    """Cost grouped by requested model"""

    requested_model: str
    request_count: int = 0
    total_cost: float = 0.0


class LogCostStatsResponse(BaseModel):
    """Cost stats response"""

    summary: LogCostSummary
    trend: list[LogCostTrendPoint]
    by_model: list[LogCostByModel]


class ModelStats(BaseModel):
    """Aggregated model stats based on request logs"""

    requested_model: str
    avg_response_time_ms: Optional[float] = None
    avg_first_byte_time_ms: Optional[float] = None
    success_rate: float = 0.0
    failure_rate: float = 0.0


class ModelProviderStats(BaseModel):
    """Aggregated model/provider stats based on request logs"""

    requested_model: str
    target_model: str
    provider_name: str
    avg_first_byte_time_ms: Optional[float] = None
    avg_response_time_ms: Optional[float] = None
    success_rate: float = 0.0
    failure_rate: float = 0.0
