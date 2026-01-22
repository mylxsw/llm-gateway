"""
Log Repository SQLAlchemy Implementation

Provides concrete database operation implementation for request logs.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, select, and_, or_, delete, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import ensure_utc, to_utc_naive, utc_now
from app.db.models import RequestLog as RequestLogORM
from app.domain.log import (
    RequestLogModel,
    RequestLogCreate,
    RequestLogQuery,
    LogCostStatsQuery,
    LogCostStatsResponse,
    LogCostSummary,
    LogCostTrendPoint,
    LogCostByModel,
    ModelStats,
    ModelProviderStats,
)
from app.repositories.log_repo import LogRepository


def _pg_make_interval_minutes(minutes: int):
    return func.make_interval(0, 0, 0, 0, 0, minutes, 0)


class SQLAlchemyLogRepository(LogRepository):
    """
    Log Repository SQLAlchemy Implementation
    
    Uses SQLAlchemy ORM to implement database operations for request logs.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Repository
        
        Args:
            session: Async database session
        """
        self.session = session
    
    def _to_domain(self, entity: RequestLogORM) -> RequestLogModel:
        """Convert ORM entity to domain model"""
        request_time = ensure_utc(entity.request_time)
        return RequestLogModel(
            id=entity.id,
            request_time=request_time,
            api_key_id=entity.api_key_id,
            api_key_name=entity.api_key_name,
            requested_model=entity.requested_model,
            target_model=entity.target_model,
            provider_id=entity.provider_id,
            provider_name=entity.provider_name,
            retry_count=entity.retry_count,
            first_byte_delay_ms=entity.first_byte_delay_ms,
            total_time_ms=entity.total_time_ms,
            input_tokens=entity.input_tokens,
            output_tokens=entity.output_tokens,
            total_cost=float(entity.total_cost) if entity.total_cost is not None else None,
            input_cost=float(entity.input_cost) if entity.input_cost is not None else None,
            output_cost=float(entity.output_cost) if entity.output_cost is not None else None,
            price_source=entity.price_source,
            request_headers=entity.request_headers,
            response_headers=entity.response_headers,
            request_body=entity.request_body,
            response_status=entity.response_status,
            response_body=entity.response_body,
            error_info=entity.error_info,
            matched_provider_count=entity.matched_provider_count,
            trace_id=entity.trace_id,
            is_stream=entity.is_stream,
            request_protocol=entity.request_protocol,
            supplier_protocol=entity.supplier_protocol,
            converted_request_body=entity.converted_request_body,
            upstream_response_body=entity.upstream_response_body,
        )
    
    async def create(self, data: RequestLogCreate) -> RequestLogModel:
        """Create request log"""
        entity = RequestLogORM(
            request_time=to_utc_naive(data.request_time),
            api_key_id=data.api_key_id,
            api_key_name=data.api_key_name,
            requested_model=data.requested_model,
            target_model=data.target_model,
            provider_id=data.provider_id,
            provider_name=data.provider_name,
            retry_count=data.retry_count,
            matched_provider_count=data.matched_provider_count,
            first_byte_delay_ms=data.first_byte_delay_ms,
            total_time_ms=data.total_time_ms,
            input_tokens=data.input_tokens,
            output_tokens=data.output_tokens,
            total_cost=data.total_cost,
            input_cost=data.input_cost,
            output_cost=data.output_cost,
            price_source=data.price_source,
            request_headers=data.request_headers,
            response_headers=data.response_headers,
            request_body=data.request_body,
            response_status=data.response_status,
            response_body=data.response_body,
            error_info=data.error_info,
            trace_id=data.trace_id,
            is_stream=data.is_stream,
            request_protocol=data.request_protocol,
            supplier_protocol=data.supplier_protocol,
            converted_request_body=data.converted_request_body,
            upstream_response_body=data.upstream_response_body,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def get_by_id(self, id: int) -> Optional[RequestLogModel]:
        """Get log by ID"""
        result = await self.session.execute(
            select(RequestLogORM).where(RequestLogORM.id == id)
        )
        entity = result.scalar_one_or_none()
        return self._to_domain(entity) if entity else None
    
    async def query(self, query: RequestLogQuery) -> tuple[list[RequestLogModel], int]:
        """
        Query log list
        
        Supports multi-condition filtering, pagination, and sorting.
        """
        # Build base query
        stmt = select(RequestLogORM)
        count_stmt = select(func.count()).select_from(RequestLogORM)
        
        # Build filter conditions list
        conditions = []
        
        # Time range filter
        if query.start_time:
            conditions.append(RequestLogORM.request_time >= to_utc_naive(query.start_time))
        if query.end_time:
            conditions.append(RequestLogORM.request_time <= to_utc_naive(query.end_time))
        
        # Model filter (fuzzy match)
        if query.requested_model:
            conditions.append(
                RequestLogORM.requested_model.ilike(f"%{query.requested_model}%")
            )
        if query.target_model:
            conditions.append(
                RequestLogORM.target_model.ilike(f"%{query.target_model}%")
            )
        
        # Provider filter
        if query.provider_id:
            conditions.append(RequestLogORM.provider_id == query.provider_id)
        
        # Status code filter
        if query.status_min is not None:
            conditions.append(RequestLogORM.response_status >= query.status_min)
        if query.status_max is not None:
            conditions.append(RequestLogORM.response_status <= query.status_max)
        
        # Has error
        if query.has_error is not None:
            if query.has_error:
                conditions.append(
                    or_(
                        RequestLogORM.error_info.isnot(None),
                        RequestLogORM.error_info != "",
                    )
                )
            else:
                conditions.append(
                    or_(
                        RequestLogORM.error_info.is_(None),
                        RequestLogORM.error_info == "",
                    )
                )
        
        # API Key filter
        if query.api_key_id:
            conditions.append(RequestLogORM.api_key_id == query.api_key_id)
        if query.api_key_name:
            conditions.append(
                RequestLogORM.api_key_name.ilike(f"%{query.api_key_name}%")
            )
        
        # Retry count filter
        if query.retry_count_min is not None:
            conditions.append(RequestLogORM.retry_count >= query.retry_count_min)
        if query.retry_count_max is not None:
            conditions.append(RequestLogORM.retry_count <= query.retry_count_max)
        
        # Token filter
        if query.input_tokens_min is not None:
            conditions.append(RequestLogORM.input_tokens >= query.input_tokens_min)
        if query.input_tokens_max is not None:
            conditions.append(RequestLogORM.input_tokens <= query.input_tokens_max)
        
        # Duration filter
        if query.total_time_min is not None:
            conditions.append(RequestLogORM.total_time_ms >= query.total_time_min)
        if query.total_time_max is not None:
            conditions.append(RequestLogORM.total_time_ms <= query.total_time_max)
        
        # Apply filter conditions
        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))
        
        # Get total count
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # Sorting
        sort_column = getattr(RequestLogORM, query.sort_by, RequestLogORM.request_time)
        if query.sort_order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())
        
        # Pagination
        stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)
        
        # Execute query
        result = await self.session.execute(stmt)
        entities = result.scalars().all()

        return [self._to_domain(e) for e in entities], total

    async def cleanup_old_logs(self, days_to_keep: int) -> int:
        """
        Delete logs older than specified days

        Args:
            days_to_keep: Number of days to keep logs

        Returns:
            int: Number of deleted logs
        """
        cutoff_time = to_utc_naive(utc_now() - timedelta(days=days_to_keep))
        if cutoff_time is None:
            return 0
        stmt = delete(RequestLogORM).where(RequestLogORM.request_time < cutoff_time)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_cost_stats(self, query: LogCostStatsQuery) -> LogCostStatsResponse:
        conditions = []
        tz_offset_minutes = int(query.tz_offset_minutes or 0)

        if query.start_time:
            conditions.append(RequestLogORM.request_time >= to_utc_naive(query.start_time))
        if query.end_time:
            conditions.append(RequestLogORM.request_time <= to_utc_naive(query.end_time))
        if query.provider_id:
            conditions.append(RequestLogORM.provider_id == query.provider_id)
        if query.api_key_id:
            conditions.append(RequestLogORM.api_key_id == query.api_key_id)
        if query.api_key_name:
            conditions.append(RequestLogORM.api_key_name.ilike(f"%{query.api_key_name}%"))
        if query.requested_model:
            conditions.append(
                RequestLogORM.requested_model.ilike(f"%{query.requested_model}%")
            )

        where_clause = and_(*conditions) if conditions else None

        sum_total = func.coalesce(func.sum(RequestLogORM.total_cost), 0)
        sum_input = func.coalesce(func.sum(RequestLogORM.input_cost), 0)
        sum_output = func.coalesce(func.sum(RequestLogORM.output_cost), 0)
        sum_in_tokens = func.coalesce(func.sum(RequestLogORM.input_tokens), 0)
        sum_out_tokens = func.coalesce(func.sum(RequestLogORM.output_tokens), 0)

        error_condition = or_(
            RequestLogORM.error_info.isnot(None),
            RequestLogORM.response_status >= 400,
        )
        sum_error = func.coalesce(func.sum(case((error_condition, 1), else_=0)), 0)

        summary_stmt = select(
            func.count().label("request_count"),
            sum_total.label("total_cost"),
            sum_input.label("input_cost"),
            sum_output.label("output_cost"),
            sum_in_tokens.label("input_tokens"),
            sum_out_tokens.label("output_tokens"),
        )
        if where_clause is not None:
            summary_stmt = summary_stmt.where(where_clause)

        summary_row = (await self.session.execute(summary_stmt)).mappings().one()
        summary = LogCostSummary(
            request_count=int(summary_row["request_count"] or 0),
            total_cost=float(summary_row["total_cost"] or 0),
            input_cost=float(summary_row["input_cost"] or 0),
            output_cost=float(summary_row["output_cost"] or 0),
            input_tokens=int(summary_row["input_tokens"] or 0),
            output_tokens=int(summary_row["output_tokens"] or 0),
        )

        bind = self.session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else "sqlite"

        if tz_offset_minutes != 0:
            if dialect_name == "sqlite":
                shifted_time_expr = func.datetime(
                    RequestLogORM.request_time, f"{tz_offset_minutes:+d} minutes"
                )
            else:
                shifted_time_expr = (
                    RequestLogORM.request_time + _pg_make_interval_minutes(tz_offset_minutes)
                )
        else:
            shifted_time_expr = RequestLogORM.request_time

        # Build bucket start timestamp in UTC (returned as a UTC-aware datetime at API boundary).
        # For timezone bucketing, we:
        # 1) shift request_time (UTC) into "local" (UTC + offset)
        # 2) truncate to bucket boundary in that local clock
        # 3) shift the bucket start back to UTC for stable API output
        if query.bucket == "hour":
            if dialect_name == "sqlite":
                bucket_local_start_expr = func.strftime(
                    "%Y-%m-%d %H:00:00", shifted_time_expr
                )
            else:
                bucket_local_start_expr = func.date_trunc("hour", shifted_time_expr)
        else:
            if dialect_name == "sqlite":
                bucket_local_start_expr = func.strftime(
                    "%Y-%m-%d 00:00:00", shifted_time_expr
                )
            else:
                bucket_local_start_expr = func.date_trunc("day", shifted_time_expr)

        if tz_offset_minutes != 0:
            if dialect_name == "sqlite":
                bucket_start_utc_expr = func.datetime(
                    bucket_local_start_expr, f"{-tz_offset_minutes:+d} minutes"
                )
            else:
                bucket_start_utc_expr = bucket_local_start_expr - _pg_make_interval_minutes(
                    tz_offset_minutes
                )
        else:
            bucket_start_utc_expr = bucket_local_start_expr

        trend_stmt = select(
            bucket_start_utc_expr.label("bucket"),
            func.count().label("request_count"),
            sum_total.label("total_cost"),
            sum_input.label("input_cost"),
            sum_output.label("output_cost"),
            sum_in_tokens.label("input_tokens"),
            sum_out_tokens.label("output_tokens"),
            sum_error.label("error_count"),
        ).group_by(bucket_start_utc_expr).order_by(bucket_start_utc_expr)
        if where_clause is not None:
            trend_stmt = trend_stmt.where(where_clause)
        trend_rows = (await self.session.execute(trend_stmt)).mappings().all()
        trend = [
            LogCostTrendPoint(
                bucket=ensure_utc(
                    datetime.fromisoformat(r["bucket"])
                    if isinstance(r["bucket"], str)
                    else r["bucket"]
                ),
                request_count=int(r["request_count"] or 0),
                total_cost=float(r["total_cost"] or 0),
                input_cost=float(r["input_cost"] or 0),
                output_cost=float(r["output_cost"] or 0),
                input_tokens=int(r["input_tokens"] or 0),
                output_tokens=int(r["output_tokens"] or 0),
                error_count=int(r["error_count"] or 0),
                success_count=max(
                    0,
                    int(r["request_count"] or 0) - int(r["error_count"] or 0),
                ),
            )
            for r in trend_rows
        ]

        by_model_stmt = (
            select(
                func.coalesce(RequestLogORM.requested_model, "").label("requested_model"),
                func.count().label("request_count"),
                sum_total.label("total_cost"),
            )
            .group_by(RequestLogORM.requested_model)
            .order_by(sum_total.desc())
            .limit(50)
        )
        if where_clause is not None:
            by_model_stmt = by_model_stmt.where(where_clause)
        model_rows = (await self.session.execute(by_model_stmt)).mappings().all()
        by_model = [
            LogCostByModel(
                requested_model=r["requested_model"] or "-",
                request_count=int(r["request_count"] or 0),
                total_cost=float(r["total_cost"] or 0),
            )
            for r in model_rows
        ]

        return LogCostStatsResponse(summary=summary, trend=trend, by_model=by_model)

    async def get_model_stats(self, requested_model: str | None = None) -> list[ModelStats]:
        cutoff_time = to_utc_naive(utc_now() - timedelta(days=7))
        conditions = []
        if cutoff_time:
            conditions.append(RequestLogORM.request_time >= cutoff_time)
        if requested_model:
            conditions.append(RequestLogORM.requested_model == requested_model)
        else:
            conditions.append(RequestLogORM.requested_model.isnot(None))

        where_clause = and_(*conditions) if conditions else None

        error_condition = or_(
            RequestLogORM.error_info.isnot(None),
            RequestLogORM.response_status >= 400,
        )

        avg_total_time = func.avg(RequestLogORM.total_time_ms)
        avg_first_byte = func.avg(
            case((RequestLogORM.is_stream.is_(True), RequestLogORM.first_byte_delay_ms))
        )
        failure_count = func.coalesce(func.sum(case((error_condition, 1), else_=0)), 0)

        stmt = select(
            RequestLogORM.requested_model.label("requested_model"),
            func.count().label("request_count"),
            avg_total_time.label("avg_total_time_ms"),
            avg_first_byte.label("avg_first_byte_time_ms"),
            failure_count.label("failure_count"),
        ).group_by(RequestLogORM.requested_model)

        if where_clause is not None:
            stmt = stmt.where(where_clause)

        rows = (await self.session.execute(stmt)).mappings().all()
        results: list[ModelStats] = []
        for row in rows:
            total = int(row["request_count"] or 0)
            failures = int(row["failure_count"] or 0)
            successes = max(total - failures, 0)
            success_rate = successes / total if total > 0 else 0.0
            failure_rate = failures / total if total > 0 else 0.0
            results.append(
                ModelStats(
                    requested_model=row["requested_model"] or "-",
                    avg_response_time_ms=(
                        float(row["avg_total_time_ms"])
                        if row["avg_total_time_ms"] is not None
                        else None
                    ),
                    avg_first_byte_time_ms=(
                        float(row["avg_first_byte_time_ms"])
                        if row["avg_first_byte_time_ms"] is not None
                        else None
                    ),
                    success_rate=success_rate,
                    failure_rate=failure_rate,
                )
            )
        return results

    async def get_model_provider_stats(
        self, requested_model: str | None = None
    ) -> list[ModelProviderStats]:
        cutoff_time = to_utc_naive(utc_now() - timedelta(days=7))
        conditions = []
        if cutoff_time:
            conditions.append(RequestLogORM.request_time >= cutoff_time)
        if requested_model:
            conditions.append(RequestLogORM.requested_model == requested_model)
        else:
            conditions.append(RequestLogORM.requested_model.isnot(None))
        conditions.append(RequestLogORM.provider_name.isnot(None))
        conditions.append(RequestLogORM.target_model.isnot(None))

        where_clause = and_(*conditions) if conditions else None

        error_condition = or_(
            RequestLogORM.error_info.isnot(None),
            RequestLogORM.response_status >= 400,
        )

        avg_total_time = func.avg(RequestLogORM.total_time_ms)
        avg_first_byte = func.avg(
            case((RequestLogORM.is_stream.is_(True), RequestLogORM.first_byte_delay_ms))
        )
        failure_count = func.coalesce(func.sum(case((error_condition, 1), else_=0)), 0)

        stmt = select(
            RequestLogORM.requested_model.label("requested_model"),
            RequestLogORM.target_model.label("target_model"),
            RequestLogORM.provider_name.label("provider_name"),
            func.count().label("request_count"),
            avg_total_time.label("avg_total_time_ms"),
            avg_first_byte.label("avg_first_byte_time_ms"),
            failure_count.label("failure_count"),
        ).group_by(
            RequestLogORM.requested_model,
            RequestLogORM.target_model,
            RequestLogORM.provider_name,
        )

        if where_clause is not None:
            stmt = stmt.where(where_clause)

        rows = (await self.session.execute(stmt)).mappings().all()
        results: list[ModelProviderStats] = []
        for row in rows:
            total = int(row["request_count"] or 0)
            failures = int(row["failure_count"] or 0)
            successes = max(total - failures, 0)
            success_rate = successes / total if total > 0 else 0.0
            failure_rate = failures / total if total > 0 else 0.0
            results.append(
                ModelProviderStats(
                    requested_model=row["requested_model"] or "-",
                    target_model=row["target_model"] or "-",
                    provider_name=row["provider_name"] or "-",
                    avg_first_byte_time_ms=(
                        float(row["avg_first_byte_time_ms"])
                        if row["avg_first_byte_time_ms"] is not None
                        else None
                    ),
                    avg_response_time_ms=(
                        float(row["avg_total_time_ms"])
                        if row["avg_total_time_ms"] is not None
                        else None
                    ),
                    success_rate=success_rate,
                    failure_rate=failure_rate,
                )
            )
        return results
