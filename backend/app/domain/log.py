"""
Request Log Domain Model

Defines Request Log related Data Transfer Objects (DTOs).
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


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