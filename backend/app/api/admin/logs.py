"""
Log Query API

Provides request log query endpoints.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.api.deps import (
    ApiKeyServiceDep,
    LogServiceDep,
    ProxyServiceDep,
    require_admin_auth,
)
from app.common.provider_protocols import (
    ANTHROPIC_PROTOCOL,
    GEMINI_PROTOCOL,
    OPENAI_RESPONSES_PROTOCOL,
    resolve_implementation_protocol,
)
from app.common.errors import AppError, ValidationError
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


class RetryLogResponse(BaseModel):
    """Retry log response payload"""

    response_status: int
    response_body: object | str | None
    new_log_id: int | None = None
    trace_id: str | None = None


class PlaygroundExecuteRequest(BaseModel):
    """Editable playground request payload"""

    protocol: str | None = None
    request_path: str | None = None
    request_headers: dict[str, str] | None = None
    request_body: dict[str, Any] | list[Any] | str | int | float | bool | None = None


class PlaygroundExecuteResponse(BaseModel):
    """Playground execution response payload"""

    response_status: int
    response_body: object | str | None
    trace_id: str | None = None
    provider_name: str | None = None
    target_model: str | None = None
    first_byte_delay_ms: int | None = None
    total_time_ms: int | None = None


def _build_retry_headers(
    log: RequestLogDetailResponse,
    raw_key: str,
) -> tuple[dict[str, str], dict[str, str]]:
    original_headers = log.request_headers or {}
    sanitized_lower_headers = {
        str(k).lower(): str(v) for k, v in original_headers.items()
    }

    retry_headers: dict[str, str] = {}
    for key, value in original_headers.items():
        lower_key = str(key).lower()
        if lower_key in {
            "authorization",
            "x-api-key",
            "api-key",
            "host",
            "content-length",
        }:
            continue
        retry_headers[str(key)] = str(value)

    if (
        log.request_protocol == "anthropic"
        or "x-api-key" in sanitized_lower_headers
        or "api-key" in sanitized_lower_headers
    ):
        retry_headers["x-api-key"] = raw_key
    else:
        retry_headers["Authorization"] = f"Bearer {raw_key}"

    if (
        "content-type" not in sanitized_lower_headers
        and "Content-Type" not in retry_headers
    ):
        retry_headers["Content-Type"] = "application/json"

    return retry_headers, sanitized_lower_headers


def _build_retry_target(
    log: RequestLogDetailResponse,
    sanitized_lower_headers: dict[str, str],
) -> tuple[str, str]:
    path_with_query = log.request_path or "/"
    base_url = "http://retry.internal"

    if log.request_url:
        parsed = urlsplit(log.request_url)
        if parsed.scheme and parsed.netloc:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        if parsed.path:
            path_with_query = parsed.path
            if parsed.query:
                path_with_query = f"{path_with_query}?{parsed.query}"
        return base_url, path_with_query

    forwarded_proto = sanitized_lower_headers.get("x-forwarded-proto")
    forwarded_host = sanitized_lower_headers.get("x-forwarded-host")
    host = sanitized_lower_headers.get("host")
    origin = sanitized_lower_headers.get("origin")
    if forwarded_proto and forwarded_host:
        base_url = f"{forwarded_proto}://{forwarded_host}"
    elif host:
        base_url = f"{forwarded_proto or 'http'}://{host}"
    elif origin:
        base_url = origin
    return base_url, path_with_query


async def _resolve_retry_log_id(
    *,
    log_service,
    original_log_id: int,
    api_key_id: int,
    request_path: str,
    trace_id: str | None,
) -> int | None:
    if trace_id:
        try:
            retried_log = await log_service.get_by_trace_id(trace_id)
            return retried_log.id
        except AppError:
            pass

    retry_candidate = await log_service.find_latest_retry_candidate(
        min_id=original_log_id,
        api_key_id=api_key_id,
        request_path=request_path,
    )
    return retry_candidate.id if retry_candidate else None


def _sse_event(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sanitize_playground_headers(
    original_headers: dict[str, str] | None,
    overridden_headers: dict[str, str] | None,
) -> dict[str, str]:
    headers = dict(original_headers or {})
    if overridden_headers is not None:
        headers = dict(overridden_headers)

    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = str(key).lower()
        if lower_key in {"authorization", "x-api-key", "api-key", "host", "content-length"}:
            continue
        sanitized[str(key)] = str(value)

    if not any(str(key).lower() == "content-type" for key in sanitized):
        sanitized["Content-Type"] = "application/json"

    return sanitized


def _build_playground_request_path(
    protocol: str | None,
    request_body: Any,
    fallback_path: str | None,
) -> str:
    implementation = resolve_implementation_protocol(protocol)

    if implementation == ANTHROPIC_PROTOCOL:
        return "/v1/messages"

    if implementation == OPENAI_RESPONSES_PROTOCOL:
        return "/v1/responses"

    if implementation == GEMINI_PROTOCOL:
        if not isinstance(request_body, dict):
            raise ValidationError(
                message="Gemini requests require a JSON object request body",
                code="playground_gemini_body_invalid",
            )
        model = request_body.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValidationError(
                message="Gemini requests require a model field",
                code="playground_gemini_model_missing",
            )
        is_stream = bool(request_body.get("stream"))
        action = "streamGenerateContent?alt=sse" if is_stream else "generateContent"
        return f"/v1beta/models/{model}:{action}"

    return fallback_path or "/v1/chat/completions"


def _is_playground_stream(
    protocol: str | None,
    request_body: Any,
    request_path: str,
) -> bool:
    implementation = resolve_implementation_protocol(protocol)
    if implementation == GEMINI_PROTOCOL:
        return "streamGenerateContent" in request_path or "alt=sse" in request_path
    return isinstance(request_body, dict) and bool(request_body.get("stream"))


@router.post("/{log_id}/playground")
async def execute_playground_request(
    log_id: int,
    data: PlaygroundExecuteRequest,
    log_service: LogServiceDep,
    proxy_service: ProxyServiceDep,
):
    """
    Execute a debug request based on an existing log with editable request data.
    """
    try:
        log = await log_service.get_by_id(log_id)

        if not log.api_key_id:
            raise ValidationError(
                message="API key is missing for this log",
                code="playground_api_key_missing",
            )

        protocol = (data.protocol or log.request_protocol or "openai").strip()
        request_body = data.request_body
        request_path = data.request_path or _build_playground_request_path(
            protocol=protocol,
            request_body=request_body,
            fallback_path=log.request_path,
        )
        request_headers = _sanitize_playground_headers(
            log.request_headers,
            data.request_headers,
        )
        method = (log.request_method or "POST").upper()
        is_stream = _is_playground_stream(protocol, request_body, request_path)

        if is_stream:
            async def event_stream():
                initial_response, stream_gen, log_info = await proxy_service.process_request_stream(
                    api_key_id=log.api_key_id,
                    api_key_name=log.api_key_name,
                    request_protocol=protocol,
                    path=request_path,
                    request_url=request_path,
                    method=method,
                    headers=request_headers,
                    body=request_body,
                )

                yield _sse_event(
                    "status",
                    {
                        "response_status": initial_response.status_code,
                        "trace_id": log_info.get("trace_id") if log_info else None,
                        "provider_name": log_info.get("provider_name") if log_info else None,
                        "target_model": log_info.get("target_model") if log_info else None,
                        "first_byte_delay_ms": initial_response.first_byte_delay_ms,
                    },
                )

                if not initial_response.is_success:
                    yield _sse_event(
                        "done",
                        {
                            "response_status": initial_response.status_code,
                            "response_body": initial_response.body,
                            "trace_id": log_info.get("trace_id") if log_info else None,
                            "provider_name": log_info.get("provider_name") if log_info else None,
                            "target_model": log_info.get("target_model") if log_info else None,
                            "first_byte_delay_ms": initial_response.first_byte_delay_ms,
                            "total_time_ms": initial_response.total_time_ms,
                        },
                    )
                    return

                streamed_content = ""
                async for chunk in stream_gen:
                    if isinstance(chunk, bytes):
                        text_chunk = chunk.decode("utf-8", errors="ignore")
                    else:
                        text_chunk = str(chunk)
                    if not text_chunk:
                        continue
                    streamed_content += text_chunk
                    yield _sse_event("chunk", {"content": text_chunk})

                yield _sse_event(
                    "done",
                    {
                        "response_status": initial_response.status_code,
                        "response_body": streamed_content,
                        "trace_id": log_info.get("trace_id") if log_info else None,
                        "provider_name": log_info.get("provider_name") if log_info else None,
                        "target_model": log_info.get("target_model") if log_info else None,
                        "first_byte_delay_ms": initial_response.first_byte_delay_ms,
                        "total_time_ms": initial_response.total_time_ms,
                    },
                )

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        response, log_info = await proxy_service.process_request(
            api_key_id=log.api_key_id,
            api_key_name=log.api_key_name,
            request_protocol=protocol,
            path=request_path,
            request_url=request_path,
            method=method,
            headers=request_headers,
            body=request_body,
            force_parse_response=True,
        )

        return PlaygroundExecuteResponse(
            response_status=response.status_code,
            response_body=response.body,
            trace_id=log_info.get("trace_id") if log_info else None,
            provider_name=log_info.get("provider_name") if log_info else None,
            target_model=log_info.get("target_model") if log_info else None,
            first_byte_delay_ms=response.first_byte_delay_ms,
            total_time_ms=response.total_time_ms,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


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


@router.post("/{log_id}/retry")
async def retry_log(
    log_id: int,
    request: Request,
    log_service: LogServiceDep,
    api_key_service: ApiKeyServiceDep,
):
    """
    Replay a previously recorded request through the original proxy controller.
    """
    try:
        log = await log_service.get_by_id(log_id)
        original_log_id = log.id

        if not log.request_path:
            raise ValidationError(
                message="Request path is missing for this log",
                code="retry_request_path_missing",
            )
        if not log.api_key_id:
            raise ValidationError(
                message="API key is missing for this log",
                code="retry_api_key_missing",
            )
        if isinstance(log.request_body, dict) and log.request_body.get("_files"):
            raise ValidationError(
                message="Multipart requests cannot be retried from logs",
                code="retry_multipart_unsupported",
            )

        raw_key = await api_key_service.get_raw_key_value(log.api_key_id)
        retry_headers, sanitized_lower_headers = _build_retry_headers(log, raw_key)
        base_url, path_with_query = _build_retry_target(log, sanitized_lower_headers)
        timeout = httpx.Timeout(300.0, connect=30.0)

        transport = httpx.ASGITransport(app=request.app)
        method = (log.request_method or "POST").upper()

        if log.is_stream:
            async def event_stream():
                trace_id: str | None = None
                response_status: int | None = None
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url=base_url,
                    timeout=timeout,
                ) as client:
                    async with client.stream(
                        method=method,
                        url=path_with_query,
                        headers=retry_headers,
                        json=log.request_body,
                    ) as response:
                        trace_id = response.headers.get("x-lgw-trace-id")
                        response_status = response.status_code
                        yield _sse_event(
                            "status",
                            {"response_status": response.status_code},
                        )
                        async for chunk in response.aiter_text():
                            if not chunk:
                                continue
                            yield _sse_event("chunk", {"content": chunk})

                new_log_id = await _resolve_retry_log_id(
                    log_service=log_service,
                    original_log_id=original_log_id,
                    api_key_id=log.api_key_id,
                    request_path=log.request_path,
                    trace_id=trace_id,
                )
                yield _sse_event(
                    "done",
                    {
                        "response_status": response_status,
                        "new_log_id": new_log_id,
                        "trace_id": trace_id,
                    },
                )

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )

        async with httpx.AsyncClient(
            transport=transport,
            base_url=base_url,
            timeout=timeout,
        ) as client:
            response = await client.request(
                method=method,
                url=path_with_query,
                headers=retry_headers,
                json=log.request_body,
            )

        trace_id = response.headers.get("x-lgw-trace-id")
        new_log_id = await _resolve_retry_log_id(
            log_service=log_service,
            original_log_id=original_log_id,
            api_key_id=log.api_key_id,
            request_path=log.request_path,
            trace_id=trace_id,
        )

        return RetryLogResponse(
            response_status=response.status_code,
            response_body=try_parse_json_object(response.text) if response.text else None,
            new_log_id=new_log_id,
            trace_id=trace_id,
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
