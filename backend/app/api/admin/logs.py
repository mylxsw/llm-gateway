"""
Log Query API

Provides request log query endpoints.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import LogServiceDep, require_admin_auth
from app.common.errors import AppError
from app.common.utils import try_parse_json_object
from app.config import get_settings
from app.domain.log import (
    RequestLogQuery,
    RequestLogResponse,
    RequestLogDetailResponse,
    LogCostStatsQuery,
    LogCostStatsResponse,
)

router = APIRouter(
    prefix="/admin/logs",
    tags=["Admin - Logs"],
    dependencies=[Depends(require_admin_auth)],
)


_TIMELINE_MINUTES: dict[str, int] = {
    "1h": 60, "3h": 180, "6h": 360,
    "12h": 720, "24h": 1440, "1w": 10080,
}


class PaginatedLogResponse(BaseModel):
    """Log Pagination Response"""
    items: list[RequestLogResponse]
    total: int
    page: int
    page_size: int


class CleanupResponse(BaseModel):
    """Log Cleanup Response"""
    deleted_count: int
    message: str


@router.get("/stats", response_model=LogCostStatsResponse)
async def get_log_cost_stats(
    service: LogServiceDep,
    start_time: Optional[datetime] = Query(None, description="Start Time"),
    end_time: Optional[datetime] = Query(None, description="End Time"),
    timeline: Optional[str] = Query(
        None,
        pattern="^(1h|3h|6h|12h|24h|1w)$",
        description="Relative time range (e.g. 24h). Ignored when start_time is set.",
    ),
    requested_model: Optional[str] = Query(None, description="Requested Model (Fuzzy Match)"),
    provider_id: Optional[int] = Query(None, description="Provider ID"),
    api_key_id: Optional[int] = Query(None, description="API Key ID"),
    api_key_name: Optional[str] = Query(None, description="API Key Name (Fuzzy Match)"),
    bucket: Optional[str] = Query(
        None,
        pattern="^(minute|hour|day)$",
        description="Trend bucket override (minute/hour/day). If omitted, server picks a default.",
    ),
    bucket_minutes: Optional[int] = Query(
        None,
        ge=1,
        le=1440,
        description="Minute bucket size (used when bucket=minute)",
    ),
    tz_offset_minutes: int = Query(
        0,
        ge=-14 * 60,
        le=14 * 60,
        description="Timezone offset minutes for bucketing (UTC to local). Example: UTC+8 => 480",
    ),
    group_by: str = Query(
        "request_model",
        pattern="^(request_model|provider_model)$",
        description="Group by dimension for model stats",
    ),
):
    """
    Aggregated cost stats for logs.

    Dimensions: time range, model, provider, API key.
    """
    try:
        # Resolve timeline to start_time when no explicit start_time is provided
        effective_start = start_time
        if not effective_start and timeline:
            minutes = _TIMELINE_MINUTES[timeline]
            effective_start = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        resolved_bucket = bucket
        if not resolved_bucket:
            resolved_bucket = "day"
            if effective_start and end_time:
                delta = end_time - effective_start
                if delta.total_seconds() <= 48 * 3600:
                    resolved_bucket = "hour"
            elif effective_start and not end_time and timeline:
                # For timeline presets, use the preset duration to pick bucket
                tl_minutes = _TIMELINE_MINUTES[timeline]
                if tl_minutes * 60 <= 48 * 3600:
                    resolved_bucket = "hour"

        query = LogCostStatsQuery(
            start_time=effective_start,
            end_time=end_time,
            timeline=timeline,
            requested_model=requested_model,
            provider_id=provider_id,
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            bucket=resolved_bucket,
            bucket_minutes=bucket_minutes,
            tz_offset_minutes=tz_offset_minutes,
            group_by=group_by,
        )
        return await service.get_cost_stats(query)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("", response_model=PaginatedLogResponse)
async def list_logs(
    service: LogServiceDep,
    start_time: Optional[datetime] = Query(None, description="Start Time"),
    end_time: Optional[datetime] = Query(None, description="End Time"),
    timeline: Optional[str] = Query(
        None,
        pattern="^(1h|3h|6h|12h|24h|1w)$",
        description="Relative time range (e.g. 24h). Ignored when start_time is set.",
    ),
    requested_model: Optional[str] = Query(None, description="Requested Model (Fuzzy Match)"),
    target_model: Optional[str] = Query(None, description="Target Model (Fuzzy Match)"),
    provider_id: Optional[int] = Query(None, description="Provider ID"),
    status_min: Optional[int] = Query(None, description="Min Status Code"),
    status_max: Optional[int] = Query(None, description="Max Status Code"),
    has_error: Optional[bool] = Query(None, description="Has Error"),
    api_key_id: Optional[int] = Query(None, description="API Key ID"),
    api_key_name: Optional[str] = Query(None, description="API Key Name"),
    retry_count_min: Optional[int] = Query(None, description="Min Retry Count"),
    retry_count_max: Optional[int] = Query(None, description="Max Retry Count"),
    input_tokens_min: Optional[int] = Query(None, description="Min Input Tokens"),
    input_tokens_max: Optional[int] = Query(None, description="Max Input Tokens"),
    total_time_min: Optional[int] = Query(None, description="Min Total Time (ms)"),
    total_time_max: Optional[int] = Query(None, description="Max Total Time (ms)"),
    page: int = Query(1, ge=1, description="Page Number"),
    page_size: int = Query(20, ge=1, le=100, description="Items Per Page"),
    sort_by: str = Query("request_time", description="Sort Field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort Order"),
):
    """
    Query request log list

    Supports multi-condition filtering, pagination, and sorting.
    """
    try:
        # Resolve timeline to start_time when no explicit start_time is provided
        effective_start = start_time
        if not effective_start and timeline:
            minutes = _TIMELINE_MINUTES[timeline]
            effective_start = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        query = RequestLogQuery(
            start_time=effective_start,
            end_time=end_time,
            timeline=timeline,
            requested_model=requested_model,
            target_model=target_model,
            provider_id=provider_id,
            status_min=status_min,
            status_max=status_max,
            has_error=has_error,
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            retry_count_min=retry_count_min,
            retry_count_max=retry_count_max,
            input_tokens_min=input_tokens_min,
            input_tokens_max=input_tokens_max,
            total_time_min=total_time_min,
            total_time_max=total_time_max,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        items, total = await service.query(query)
        return PaginatedLogResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/{log_id}", response_model=RequestLogDetailResponse)
async def get_log(
    log_id: int,
    service: LogServiceDep,
):
    """
    Get Log Details
    
    Includes full request/response info (authorization sanitized).
    """
    try:
        log = await service.get_by_id(log_id)
        return RequestLogDetailResponse(
            **log.model_dump(exclude={"response_body"}),
            response_body=try_parse_json_object(log.response_body)
            if log.response_body
            else None,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_logs(
    service: LogServiceDep,
    days: Optional[int] = Query(None, ge=1, description="Retention days (defaults to config)"),
):
    """
    Manually trigger log cleanup

    Deletes logs older than specified days. If days not specified, uses configured default retention days.
    """
    try:
        settings = get_settings()
        retention_days = days if days is not None else settings.LOG_RETENTION_DAYS

        deleted_count = await service.cleanup_old_logs(retention_days)
        return CleanupResponse(
            deleted_count=deleted_count,
            message=f"Successfully deleted {deleted_count} logs older than {retention_days} days",
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
