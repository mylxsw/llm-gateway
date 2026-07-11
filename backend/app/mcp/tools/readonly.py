"""
MCP read-only tools

These tools expose the gateway's management data to an authenticated MCP admin.
Following Scheme A, they return raw database rows (redacted for secrets) so the
agent sees as much diagnostic detail as possible with minimal per-field code.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.common.mcp_auth import current_principal
from app.db.models import (
    ApiKey,
    ModelMapping,
    ModelMappingProvider,
    RequestLog,
    ServiceProvider,
)
from app.domain.log import LogCostStatsQuery
from app.mcp.redaction import serialize_model, serialize_row, serialize_rows
from app.mcp.tools import audit, db_session
from app.repositories.sqlalchemy import (
    SQLAlchemyLogRepository,
    SQLAlchemyProviderRepository,
)
from app.services import LogService, ProviderService

_TIMELINE_MINUTES = {
    "1h": 60,
    "3h": 180,
    "6h": 360,
    "12h": 720,
    "24h": 1440,
    "1w": 10080,
}


def _clamp_page_size(page_size: int, maximum: int = 200) -> int:
    return max(1, min(page_size, maximum))


# ----------------------------- Identity -----------------------------


async def whoami() -> dict[str, Any]:
    """Return the identity and privileges of the current MCP caller."""
    principal = current_principal()
    if principal is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "api_key_id": principal.id,
        "key_name": principal.key_name,
        "is_mcp_admin": principal.is_mcp_admin,
    }


# ----------------------------- Providers -----------------------------


async def list_providers(
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """List service providers (raw rows; upstream api_key is redacted)."""
    page_size = _clamp_page_size(page_size)
    async with db_session() as session:
        stmt = select(ServiceProvider)
        if is_active is not None:
            stmt = stmt.where(ServiceProvider.is_active == is_active)
        stmt = stmt.order_by(ServiceProvider.id).offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    audit("list_providers", count=len(rows))
    return {"items": serialize_rows(rows), "page": page, "page_size": page_size}


async def get_provider(provider_id: int) -> dict[str, Any]:
    """Get a single service provider by id (raw row; api_key redacted)."""
    async with db_session() as session:
        row = (
            await session.execute(
                select(ServiceProvider).where(ServiceProvider.id == provider_id)
            )
        ).scalar_one_or_none()
    audit("get_provider", provider_id=provider_id, found=bool(row))
    if row is None:
        return {"error": f"Provider {provider_id} not found"}
    return serialize_row(row)


async def list_provider_upstream_models(provider_id: int) -> dict[str, Any]:
    """Probe the upstream provider for the models it currently exposes."""
    async with db_session() as session:
        service = ProviderService(SQLAlchemyProviderRepository(session))
        provider, models, error = await service.list_upstream_models(provider_id)
    audit("list_provider_upstream_models", provider_id=provider_id, count=len(models))
    return {
        "provider_id": provider.id,
        "provider_name": provider.name,
        "models": models,
        "error": error,
    }


# ----------------------------- Models -----------------------------


async def list_models(
    is_active: Optional[bool] = None,
    requested_model: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """List model mappings with their per-provider mappings (raw rows)."""
    page_size = _clamp_page_size(page_size)
    async with db_session() as session:
        stmt = select(ModelMapping).options(selectinload(ModelMapping.providers))
        if is_active is not None:
            stmt = stmt.where(ModelMapping.is_active == is_active)
        if requested_model:
            stmt = stmt.where(ModelMapping.requested_model.ilike(f"%{requested_model}%"))
        stmt = (
            stmt.order_by(ModelMapping.requested_model)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        mappings = (await session.execute(stmt)).scalars().all()
        items = []
        for m in mappings:
            row = serialize_row(m)
            row["providers"] = serialize_rows(m.providers)
            items.append(row)
    audit("list_models", count=len(items))
    return {"items": items, "page": page, "page_size": page_size}


async def get_model(requested_model: str) -> dict[str, Any]:
    """Get a single model mapping and its provider mappings (raw rows)."""
    async with db_session() as session:
        m = (
            await session.execute(
                select(ModelMapping)
                .where(ModelMapping.requested_model == requested_model)
                .options(selectinload(ModelMapping.providers))
            )
        ).scalar_one_or_none()
        if m is None:
            audit("get_model", requested_model=requested_model, found=False)
            return {"error": f"Model mapping '{requested_model}' not found"}
        row = serialize_row(m)
        row["providers"] = serialize_rows(m.providers)
    audit("get_model", requested_model=requested_model, found=True)
    return row


async def get_model_stats(requested_model: Optional[str] = None) -> dict[str, Any]:
    """Aggregated call stats grouped by requested model."""
    async with db_session() as session:
        service = LogService(SQLAlchemyLogRepository(session))
        stats = await service.get_model_stats(requested_model)
    audit("get_model_stats", count=len(stats))
    return {"items": [serialize_model(s) for s in stats]}


async def get_model_provider_stats(
    requested_model: Optional[str] = None,
) -> dict[str, Any]:
    """Aggregated call stats grouped by provider+model."""
    async with db_session() as session:
        service = LogService(SQLAlchemyLogRepository(session))
        stats = await service.get_model_provider_stats(requested_model)
    audit("get_model_provider_stats", count=len(stats))
    return {"items": [serialize_model(s) for s in stats]}


# ----------------------------- API Keys -----------------------------


async def list_api_keys(
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """List API keys (raw rows; key_value is redacted)."""
    page_size = _clamp_page_size(page_size)
    async with db_session() as session:
        stmt = select(ApiKey)
        if is_active is not None:
            stmt = stmt.where(ApiKey.is_active == is_active)
        stmt = stmt.order_by(ApiKey.id).offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()
    audit("list_api_keys", count=len(rows))
    return {"items": serialize_rows(rows), "page": page, "page_size": page_size}


async def get_api_key(key_id: int) -> dict[str, Any]:
    """Get a single API key by id (raw row; key_value redacted)."""
    async with db_session() as session:
        row = (
            await session.execute(select(ApiKey).where(ApiKey.id == key_id))
        ).scalar_one_or_none()
    audit("get_api_key", key_id=key_id, found=bool(row))
    if row is None:
        return {"error": f"API key {key_id} not found"}
    return serialize_row(row)


# ----------------------------- Request Logs -----------------------------


def _resolve_start_time(
    start_time: Optional[str], timeline: Optional[str]
) -> Optional[datetime]:
    if start_time:
        return datetime.fromisoformat(start_time)
    if timeline and timeline in _TIMELINE_MINUTES:
        return datetime.now(timezone.utc) - timedelta(minutes=_TIMELINE_MINUTES[timeline])
    return None


async def list_request_logs(
    timeline: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    requested_model: Optional[str] = None,
    target_model: Optional[str] = None,
    provider_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
    api_key_name: Optional[str] = None,
    user_id: Optional[str] = None,
    status_min: Optional[int] = None,
    status_max: Optional[int] = None,
    has_error: Optional[bool] = None,
    is_completed: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "request_time",
    sort_order: str = "desc",
) -> dict[str, Any]:
    """Query request-log summary rows with multi-dimensional filters.

    Time filters accept ISO-8601 strings or a `timeline` preset
    (1h/3h/6h/12h/24h/1w). This is the primary tool for diagnosing traffic.
    """
    page_size = _clamp_page_size(page_size, maximum=100)
    from app.domain.log import RequestLogQuery

    query = RequestLogQuery(
        start_time=_resolve_start_time(start_time, timeline),
        end_time=datetime.fromisoformat(end_time) if end_time else None,
        timeline=timeline,
        requested_model=requested_model,
        target_model=target_model,
        provider_id=provider_id,
        api_key_id=api_key_id,
        api_key_name=api_key_name,
        user_id=user_id,
        status_min=status_min,
        status_max=status_max,
        has_error=has_error,
        is_completed=is_completed,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    async with db_session() as session:
        service = LogService(SQLAlchemyLogRepository(session))
        items, total = await service.query(query)
    audit("list_request_logs", total=total, returned=len(items))
    return {
        "items": [serialize_model(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_request_log(log_id: int) -> dict[str, Any]:
    """Get one request log with full detail (bodies included; headers redacted)."""
    async with db_session() as session:
        row = (
            await session.execute(
                select(RequestLog)
                .where(RequestLog.id == log_id)
                .options(joinedload(RequestLog.detail))
            )
        ).unique().scalar_one_or_none()
        if row is None:
            audit("get_request_log", log_id=log_id, found=False)
            return {"error": f"Request log {log_id} not found"}
        result = serialize_row(row)
        detail = getattr(row, "detail", None)
        result["detail"] = serialize_row(detail) if detail is not None else None
    audit("get_request_log", log_id=log_id, found=True)
    return result


async def get_log_cost_stats(
    timeline: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    requested_model: Optional[str] = None,
    provider_id: Optional[int] = None,
    api_key_id: Optional[int] = None,
    user_id: Optional[str] = None,
    group_by: str = "request_model",
    tz_offset_minutes: int = 0,
) -> dict[str, Any]:
    """Aggregated cost/usage stats across time, model, provider, and API key."""
    effective_start = _resolve_start_time(start_time, timeline)
    effective_end = datetime.fromisoformat(end_time) if end_time else None
    bucket = "day"
    if effective_start and effective_end:
        if (effective_end - effective_start).total_seconds() <= 48 * 3600:
            bucket = "hour"
    elif timeline and _TIMELINE_MINUTES.get(timeline, 0) * 60 <= 48 * 3600:
        bucket = "hour"

    query = LogCostStatsQuery(
        start_time=effective_start,
        end_time=effective_end,
        timeline=timeline,
        requested_model=requested_model,
        provider_id=provider_id,
        api_key_id=api_key_id,
        user_id=user_id,
        bucket=bucket,
        tz_offset_minutes=tz_offset_minutes,
        group_by=group_by,
    )
    async with db_session() as session:
        service = LogService(SQLAlchemyLogRepository(session))
        stats = await service.get_cost_stats(query)
    audit("get_log_cost_stats", group_by=group_by)
    return serialize_model(stats)
