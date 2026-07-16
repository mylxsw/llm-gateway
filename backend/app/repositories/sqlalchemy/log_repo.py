"""
Log Repository SQLAlchemy Implementation

Provides concrete database operation implementation for request logs.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Integer, and_, case, cast, delete, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from app.common.time import ensure_utc, to_utc_naive, utc_now
from app.db.models import RequestLog as RequestLogORM
from app.db.models import RequestLogDetail as RequestLogDetailORM
from app.domain.log import (
    ApiKeyMonthlyCost,
    LogCostByModel,
    LogCostStatsQuery,
    LogCostStatsResponse,
    LogCostSummary,
    LogCostTrendPoint,
    ModelCallStats,
    ModelProviderStats,
    ModelStats,
    RequestLogCreate,
    RequestLogModel,
    RequestLogQuery,
    RequestLogSummary,
)
from app.repositories.log_repo import LogRepository


# Columns selected for list/summary queries (excludes large JSON/Text fields)
_SUMMARY_COLUMNS = [
    RequestLogORM.id,
    RequestLogORM.request_time,
    RequestLogORM.api_key_id,
    RequestLogORM.api_key_name,
    RequestLogORM.user_id,
    RequestLogORM.requested_model,
    RequestLogORM.target_model,
    RequestLogORM.provider_id,
    RequestLogORM.provider_name,
    RequestLogORM.retry_count,
    RequestLogORM.matched_provider_count,
    RequestLogORM.first_byte_delay_ms,
    RequestLogORM.total_time_ms,
    RequestLogORM.input_tokens,
    RequestLogORM.output_tokens,
    RequestLogORM.total_cost,
    RequestLogORM.input_cost,
    RequestLogORM.output_cost,
    RequestLogORM.response_status,
    RequestLogORM.trace_id,
    RequestLogORM.is_stream,
    RequestLogORM.is_completed,
]


def _pg_make_interval_minutes(minutes):
    # Use 6-arg signature (without seconds) and cast minutes to integer for PostgreSQL.
    return func.make_interval(0, 0, 0, 0, 0, cast(minutes, Integer))


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
        """Convert ORM entity to domain model (with detail data from relationship or fallback)"""
        request_time = ensure_utc(entity.request_time)
        detail = entity.detail
        detail_available = detail is not None or any(
            value is not None
            for value in (
                entity.request_headers,
                entity.response_headers,
                entity.request_body,
                entity.response_body,
                entity.usage_details,
                entity.error_info,
                entity.converted_request_body,
                entity.upstream_response_body,
            )
        )
        return RequestLogModel(
            id=entity.id,
            request_time=request_time,
            api_key_id=entity.api_key_id,
            api_key_name=entity.api_key_name,
            user_id=entity.user_id,
            requested_model=entity.requested_model,
            target_model=entity.target_model,
            provider_id=entity.provider_id,
            provider_name=entity.provider_name,
            retry_count=entity.retry_count,
            first_byte_delay_ms=entity.first_byte_delay_ms,
            total_time_ms=entity.total_time_ms,
            input_tokens=entity.input_tokens,
            output_tokens=entity.output_tokens,
            total_cost=float(entity.total_cost)
            if entity.total_cost is not None
            else None,
            input_cost=float(entity.input_cost)
            if entity.input_cost is not None
            else None,
            output_cost=float(entity.output_cost)
            if entity.output_cost is not None
            else None,
            price_source=entity.price_source,
            # Large fields: prefer detail table, fallback to main table (for unmigrated records)
            request_headers=detail.request_headers if detail else entity.request_headers,
            response_headers=detail.response_headers if detail else entity.response_headers,
            request_body=detail.request_body if detail else entity.request_body,
            response_status=entity.response_status,
            response_body=detail.response_body if detail else entity.response_body,
            usage_details=detail.usage_details if detail else entity.usage_details,
            error_info=detail.error_info if detail else entity.error_info,
            matched_provider_count=entity.matched_provider_count,
            trace_id=entity.trace_id,
            is_stream=entity.is_stream,
            is_completed=entity.is_completed,
            request_protocol=entity.request_protocol,
            supplier_protocol=entity.supplier_protocol,
            converted_request_body=detail.converted_request_body if detail else entity.converted_request_body,
            upstream_response_body=detail.upstream_response_body if detail else entity.upstream_response_body,
            request_path=entity.request_path,
            request_url=entity.request_url,
            request_method=entity.request_method,
            upstream_url=entity.upstream_url,
            detail_available=detail_available,
        )

    def _row_to_summary(self, row) -> RequestLogSummary:
        """Convert a column-selected row mapping to a summary domain model"""
        return RequestLogSummary(
            id=row["id"],
            request_time=ensure_utc(row["request_time"]),
            api_key_id=row["api_key_id"],
            api_key_name=row["api_key_name"],
            user_id=row["user_id"],
            requested_model=row["requested_model"],
            target_model=row["target_model"],
            provider_id=row["provider_id"],
            provider_name=row["provider_name"],
            retry_count=row["retry_count"],
            matched_provider_count=row["matched_provider_count"],
            first_byte_delay_ms=row["first_byte_delay_ms"],
            total_time_ms=row["total_time_ms"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            total_cost=float(row["total_cost"]) if row["total_cost"] is not None else None,
            input_cost=float(row["input_cost"]) if row["input_cost"] is not None else None,
            output_cost=float(row["output_cost"]) if row["output_cost"] is not None else None,
            response_status=row["response_status"],
            trace_id=row["trace_id"],
            is_stream=row["is_stream"],
            is_completed=row["is_completed"],
        )

    async def create(self, data: RequestLogCreate) -> RequestLogModel:
        """Create request log with detail separation"""
        # Main table: scalar/summary fields only, large fields set to NULL
        entity = RequestLogORM(
            request_time=to_utc_naive(data.request_time),
            api_key_id=data.api_key_id,
            api_key_name=data.api_key_name,
            user_id=data.user_id,
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
            response_status=data.response_status,
            trace_id=data.trace_id,
            is_stream=data.is_stream,
            is_completed=data.is_completed,
            request_protocol=data.request_protocol,
            supplier_protocol=data.supplier_protocol,
            request_path=data.request_path,
            request_url=data.request_url,
            request_method=data.request_method,
            upstream_url=data.upstream_url,
            # Large fields NULL on main table (stored in detail table)
            request_headers=None,
            response_headers=None,
            request_body=None,
            response_body=None,
            converted_request_body=None,
            upstream_response_body=None,
            usage_details=None,
            error_info=None,
        )
        self.session.add(entity)
        await self.session.flush()  # Get the ID without committing

        # Detail table: store full large field data
        detail_entity = RequestLogDetailORM(
            log_id=entity.id,
            request_body=data.request_body,
            response_body=data.response_body,
            request_headers=data.request_headers,
            response_headers=data.response_headers,
            converted_request_body=data.converted_request_body,
            upstream_response_body=data.upstream_response_body,
            usage_details=data.usage_details,
            error_info=data.error_info,
        )
        self.session.add(detail_entity)
        await self.session.commit()
        await self.session.refresh(entity)

        # Build domain model directly from entity + data (detail relationship
        # is not loaded after refresh due to lazy="noload")
        request_time = ensure_utc(entity.request_time)
        return RequestLogModel(
            id=entity.id,
            request_time=request_time,
            api_key_id=entity.api_key_id,
            api_key_name=entity.api_key_name,
            user_id=entity.user_id,
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
            request_headers=data.request_headers,
            response_headers=data.response_headers,
            request_body=data.request_body,
            response_status=entity.response_status,
            response_body=data.response_body,
            usage_details=data.usage_details,
            error_info=data.error_info,
            matched_provider_count=entity.matched_provider_count,
            trace_id=entity.trace_id,
            is_stream=entity.is_stream,
            is_completed=entity.is_completed,
            request_protocol=entity.request_protocol,
            supplier_protocol=entity.supplier_protocol,
            converted_request_body=data.converted_request_body,
            upstream_response_body=data.upstream_response_body,
            request_path=entity.request_path,
            request_url=entity.request_url,
            request_method=entity.request_method,
            upstream_url=entity.upstream_url,
            detail_available=True,
        )

    async def create_initial(self, data: RequestLogCreate) -> int:
        """Create a minimal log entry immediately when a request is received.
        Returns the new log ID for later update."""
        entity = RequestLogORM(
            request_time=to_utc_naive(data.request_time),
            api_key_id=data.api_key_id,
            api_key_name=data.api_key_name,
            user_id=data.user_id,
            requested_model=data.requested_model,
            target_model=data.target_model,
            trace_id=data.trace_id,
            is_stream=data.is_stream,
            is_completed=False,
            request_protocol=data.request_protocol,
            request_path=data.request_path,
            request_url=data.request_url,
            request_method=data.request_method,
            # All other fields remain NULL until update
        )
        self.session.add(entity)
        await self.session.flush()
        log_id = entity.id
        await self.session.commit()
        return log_id

    async def update(self, log_id: int, data: RequestLogCreate) -> RequestLogModel:
        """Complete an in-progress log without overwriting a concurrent cancel."""
        from sqlalchemy import update as sa_update

        from app.common.errors import NotFoundError

        stmt = (
            sa_update(RequestLogORM)
            .where(
                RequestLogORM.id == log_id,
                RequestLogORM.is_completed.is_(False),
            )
            .values(
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
                cached_input_cost=data.cached_input_cost,
                cached_output_cost=data.cached_output_cost,
                price_source=data.price_source,
                response_status=data.response_status,
                is_completed=True,
                target_model=data.target_model,
                supplier_protocol=data.supplier_protocol,
                upstream_url=data.upstream_url,
            )
        )
        update_result = await self.session.execute(stmt)

        if update_result.rowcount == 0:
            # A cancellation or another completion won the compare-and-set.
            # Never overwrite its status/detail payload.
            await self.session.rollback()
            existing = await self.get_by_id(log_id)
            if existing is None:
                raise NotFoundError(
                    message=f"Request log with id {log_id} not found",
                    code="log_not_found",
                )
            return existing

        # Upsert detail row
        detail = RequestLogDetailORM(
            log_id=log_id,
            request_body=data.request_body,
            response_body=data.response_body,
            request_headers=data.request_headers,
            response_headers=data.response_headers,
            converted_request_body=data.converted_request_body,
            upstream_response_body=data.upstream_response_body,
            usage_details=data.usage_details,
            error_info=data.error_info,
        )
        await self.session.merge(detail)
        await self.session.commit()

        # Re-fetch with joined detail
        result = await self.session.execute(
            select(RequestLogORM)
            .options(joinedload(RequestLogORM.detail))
            .where(RequestLogORM.id == log_id)
        )
        entity = result.unique().scalar_one()
        return self._to_domain(entity)

    async def cancel(self, log_id: int, error_info: str = "Request cancelled by admin") -> None:
        """Atomically mark an in-progress log as cancelled."""
        from sqlalchemy import update as sa_update

        from app.common.errors import NotFoundError

        stmt = (
            sa_update(RequestLogORM)
            .where(
                RequestLogORM.id == log_id,
                RequestLogORM.is_completed.is_(False),
            )
            .values(
                is_completed=True,
                response_status=499,  # Client Closed Request
            )
        )
        result = await self.session.execute(stmt)

        if result.rowcount == 0:
            await self.session.rollback()
            raise NotFoundError(
                message=f"No in-progress request found with id {log_id}",
                code="log_not_found_or_completed",
            )

        # Only the transaction that won the state transition may write details.
        error_detail = RequestLogDetailORM(
            log_id=log_id,
            error_info=error_info,
        )
        await self.session.merge(error_detail)
        await self.session.commit()

    async def cleanup_old_log_details(self, days_to_keep: int) -> int:
        """
        Delete detail rows older than specified days while keeping summary logs.

        Args:
            days_to_keep: Number of days to keep detail rows

        Returns:
            int: Number of deleted detail rows
        """
        cutoff_time = to_utc_naive(utc_now() - timedelta(days=days_to_keep))
        if cutoff_time is None:
            return 0

        subquery = select(RequestLogORM.id).where(RequestLogORM.request_time < cutoff_time)
        stmt = delete(RequestLogDetailORM).where(RequestLogDetailORM.log_id.in_(subquery))
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount or 0

    async def get_by_id(self, id: int) -> Optional[RequestLogModel]:
        """Get log by ID with full detail"""
        result = await self.session.execute(
            select(RequestLogORM)
            .options(joinedload(RequestLogORM.detail))
            .where(RequestLogORM.id == id)
        )
        entity = result.unique().scalar_one_or_none()
        return self._to_domain(entity) if entity else None

    async def get_by_trace_id(self, trace_id: str) -> Optional[RequestLogModel]:
        """Get the latest log by trace ID with full detail."""
        result = await self.session.execute(
            select(RequestLogORM)
            .options(joinedload(RequestLogORM.detail))
            .where(RequestLogORM.trace_id == trace_id)
            .order_by(RequestLogORM.id.desc())
            .limit(1)
        )
        entity = result.unique().scalars().first()
        return self._to_domain(entity) if entity else None

    async def find_latest_retry_candidate(
        self,
        *,
        min_id: int,
        api_key_id: int,
        request_path: str,
    ) -> Optional[RequestLogModel]:
        """Find the latest log created by a retried request."""
        result = await self.session.execute(
            select(RequestLogORM)
            .options(joinedload(RequestLogORM.detail))
            .where(
                RequestLogORM.id > min_id,
                RequestLogORM.api_key_id == api_key_id,
                RequestLogORM.request_path == request_path,
            )
            .order_by(RequestLogORM.id.desc())
            .limit(1)
        )
        entity = result.unique().scalar_one_or_none()
        return self._to_domain(entity) if entity else None

    async def query(self, query: RequestLogQuery) -> tuple[list[RequestLogSummary], int]:
        """
        Query log list (summary view, no large fields)

        Supports multi-condition filtering, pagination, and sorting.
        """
        # A trace represents one client request. The first row is the root row
        # created when the request arrives and later updated with the final result;
        # subsequent rows are failed provider attempts.
        earlier_log = aliased(RequestLogORM)
        is_trace_root = or_(
            RequestLogORM.trace_id.is_(None),
            RequestLogORM.trace_id == "",
            ~select(earlier_log.id)
            .where(
                earlier_log.trace_id == RequestLogORM.trace_id,
                earlier_log.id < RequestLogORM.id,
            )
            .correlate(RequestLogORM)
            .exists(),
        )
        # Build base query with only summary columns. Pagination is deliberately
        # applied to roots before retry attempt rows are loaded.
        stmt = select(*_SUMMARY_COLUMNS)
        count_stmt = select(func.count()).select_from(RequestLogORM)

        # Build filter conditions list
        conditions = [is_trace_root]

        # Time range filter
        if query.start_time:
            conditions.append(
                RequestLogORM.request_time >= to_utc_naive(query.start_time)
            )
        if query.end_time:
            conditions.append(
                RequestLogORM.request_time <= to_utc_naive(query.end_time)
            )

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

        # Has error (join detail table for error_info check)
        if query.has_error is not None:
            stmt = stmt.outerjoin(
                RequestLogDetailORM,
                RequestLogORM.id == RequestLogDetailORM.log_id,
            )
            count_stmt = count_stmt.outerjoin(
                RequestLogDetailORM,
                RequestLogORM.id == RequestLogDetailORM.log_id,
            )
            has_error_condition = or_(
                and_(
                    RequestLogDetailORM.error_info.isnot(None),
                    RequestLogDetailORM.error_info != "",
                ),
                # Fallback: check main table for unmigrated records
                and_(
                    RequestLogORM.error_info.isnot(None),
                    RequestLogORM.error_info != "",
                ),
                and_(
                    RequestLogORM.response_status.isnot(None),
                    RequestLogORM.response_status != 200,
                ),
            )
            if query.has_error:
                conditions.append(has_error_condition)
            else:
                conditions.append(not_(has_error_condition))

        # API Key filter
        if query.api_key_id:
            conditions.append(RequestLogORM.api_key_id == query.api_key_id)
        if query.api_key_name:
            conditions.append(
                RequestLogORM.api_key_name.ilike(f"%{query.api_key_name}%")
            )
        if query.user_id:
            conditions.append(RequestLogORM.user_id.ilike(f"%{query.user_id}%"))

        # Is Completed filter
        if query.is_completed is not None:
            conditions.append(RequestLogORM.is_completed == query.is_completed)

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
        stmt = stmt.where(and_(*conditions))
        count_stmt = count_stmt.where(and_(*conditions))

        # Get total count
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Sorting
        # Always surface in-progress requests (is_completed == False) before
        # completed ones so long-running requests are not buried on later pages
        # under a large volume, regardless of the user-selected sort. Booleans
        # order False < True, so is_completed ASC places in-progress rows first.
        #
        # Within the in-progress group we force oldest-first (request_time ASC)
        # so the longest-running requests stay at the very top of page 1 and can
        # be found and cancelled even when in-progress rows span multiple pages.
        # The user's chosen sort only governs the completed group.
        sort_column = getattr(RequestLogORM, query.sort_by, RequestLogORM.request_time)
        # NULL for in-progress rows keeps them ahead of (and unaffected by) the
        # user's sort; completed rows fall back to their request_time.
        in_progress_order = case(
            (RequestLogORM.is_completed.is_(False), RequestLogORM.request_time)
        )
        if query.sort_order == "asc":
            stmt = stmt.order_by(
                RequestLogORM.is_completed.asc(),
                in_progress_order.asc().nulls_last(),
                sort_column.asc(),
                RequestLogORM.id.asc(),
            )
        else:
            stmt = stmt.order_by(
                RequestLogORM.is_completed.asc(),
                in_progress_order.asc().nulls_last(),
                sort_column.desc(),
                RequestLogORM.id.desc(),
            )

        # Pagination
        stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)

        # Execute query
        result = await self.session.execute(stmt)
        rows = result.mappings().all()
        summaries = [self._row_to_summary(r) for r in rows]

        trace_roots = {
            summary.trace_id: summary
            for summary in summaries
            if summary.trace_id
        }
        if trace_roots:
            attempts_stmt = (
                select(*_SUMMARY_COLUMNS)
                .where(
                    RequestLogORM.trace_id.in_(list(trace_roots)),
                    RequestLogORM.id.notin_([summary.id for summary in trace_roots.values()]),
                )
                .order_by(RequestLogORM.id.asc())
            )
            attempt_result = await self.session.execute(attempts_stmt)
            for row in attempt_result.mappings().all():
                attempt = self._row_to_summary(row)
                root = trace_roots.get(attempt.trace_id)
                if root is not None:
                    root.retry_attempts.append(attempt)

            for root in trace_roots.values():
                root.retry_attempt_count = len(root.retry_attempts)

        return summaries, total

    async def cleanup_old_logs(self, days_to_keep: int) -> int:
        """
        Delete logs older than specified days (from both main and detail tables)

        Args:
            days_to_keep: Number of days to keep logs

        Returns:
            int: Number of deleted logs
        """
        cutoff_time = to_utc_naive(utc_now() - timedelta(days=days_to_keep))
        if cutoff_time is None:
            return 0

        # Get IDs of logs to delete (needed for detail table cleanup)
        id_stmt = select(RequestLogORM.id).where(
            RequestLogORM.request_time < cutoff_time
        )
        id_result = await self.session.execute(id_stmt)
        log_ids = [row[0] for row in id_result.all()]

        if not log_ids:
            return 0

        # Delete from detail table first (child records), in batches
        batch_size = 500
        for i in range(0, len(log_ids), batch_size):
            batch = log_ids[i : i + batch_size]
            await self.session.execute(
                delete(RequestLogDetailORM).where(
                    RequestLogDetailORM.log_id.in_(batch)
                )
            )

        # Delete from main table
        stmt = delete(RequestLogORM).where(RequestLogORM.request_time < cutoff_time)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_cost_stats(self, query: LogCostStatsQuery) -> LogCostStatsResponse:
        # In-progress rows have no final status, usage, or cost. Counting them
        # here would incorrectly classify them as successful requests.
        # A trace can also contain failed retry-attempt rows. Dashboard stats
        # count one client call per trace, so only the earliest (root) row is
        # included.
        earlier_log = aliased(RequestLogORM)
        is_trace_root = or_(
            RequestLogORM.trace_id.is_(None),
            RequestLogORM.trace_id == "",
            ~select(earlier_log.id)
            .where(
                earlier_log.trace_id == RequestLogORM.trace_id,
                earlier_log.id < RequestLogORM.id,
            )
            .correlate(RequestLogORM)
            .exists(),
        )
        later_log = aliased(RequestLogORM)
        has_later_trace_row = and_(
            RequestLogORM.trace_id.isnot(None),
            RequestLogORM.trace_id != "",
            select(later_log.id)
            .where(
                later_log.trace_id == RequestLogORM.trace_id,
                later_log.id > RequestLogORM.id,
            )
            .correlate(RequestLogORM)
            .exists(),
        )
        base_conditions = [RequestLogORM.is_completed.is_(True)]
        tz_offset_minutes = int(query.tz_offset_minutes or 0)

        if query.start_time:
            base_conditions.append(
                RequestLogORM.request_time >= to_utc_naive(query.start_time)
            )
        if query.end_time:
            base_conditions.append(
                RequestLogORM.request_time <= to_utc_naive(query.end_time)
            )
        if query.provider_id:
            base_conditions.append(RequestLogORM.provider_id == query.provider_id)
        if query.api_key_id:
            base_conditions.append(RequestLogORM.api_key_id == query.api_key_id)
        if query.api_key_name:
            base_conditions.append(
                RequestLogORM.api_key_name.ilike(f"%{query.api_key_name}%")
            )
        if query.user_id:
            base_conditions.append(RequestLogORM.user_id.ilike(f"%{query.user_id}%"))
        if query.requested_model:
            base_conditions.append(
                RequestLogORM.requested_model.ilike(f"%{query.requested_model}%")
            )

        # Summary, trends, costs, and token usage describe client requests and
        # therefore use one root row per trace.
        root_where_clause = and_(*base_conditions, is_trace_root)
        # Per-provider/model health describes actual upstream attempts. It must
        # include failed retry rows; otherwise a later successful fallback hides
        # the original model's 4xx/5xx failures.
        attempt_where_clause = and_(*base_conditions)

        sum_total = func.coalesce(func.sum(RequestLogORM.total_cost), 0)
        sum_input = func.coalesce(func.sum(RequestLogORM.input_cost), 0)
        sum_output = func.coalesce(func.sum(RequestLogORM.output_cost), 0)
        sum_in_tokens = func.coalesce(func.sum(RequestLogORM.input_tokens), 0)
        sum_out_tokens = func.coalesce(func.sum(RequestLogORM.output_tokens), 0)

        success_condition = and_(
            RequestLogORM.response_status >= 200,
            RequestLogORM.response_status < 400,
        )
        sum_success = func.coalesce(
            func.sum(case((success_condition, 1), else_=0)), 0
        )
        sum_failure = func.coalesce(
            func.sum(case((success_condition, 0), else_=1)), 0
        )
        is_upstream_attempt = or_(
            # Failed retry rows represent each actual unsuccessful upstream call.
            ~is_trace_root,
            # Successful attempts are stored only on the root row.
            success_condition,
            # Keep standalone failures that have no retry-attempt detail rows,
            # such as model resolution or forwarding setup failures.
            ~has_later_trace_row,
        )

        summary_stmt = select(
            func.count().label("request_count"),
            sum_success.label("success_count"),
            sum_failure.label("failure_count"),
            sum_total.label("total_cost"),
            sum_input.label("input_cost"),
            sum_output.label("output_cost"),
            sum_in_tokens.label("input_tokens"),
            sum_out_tokens.label("output_tokens"),
        )
        summary_stmt = summary_stmt.where(root_where_clause)

        summary_row = (await self.session.execute(summary_stmt)).mappings().one()
        request_count = int(summary_row["request_count"] or 0)
        success_count = int(summary_row["success_count"] or 0)
        failure_count = int(summary_row["failure_count"] or 0)
        summary = LogCostSummary(
            request_count=request_count,
            success_count=success_count,
            failure_count=failure_count,
            success_rate=success_count / request_count if request_count > 0 else 0.0,
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
                    RequestLogORM.request_time
                    + _pg_make_interval_minutes(tz_offset_minutes)
                )
        else:
            shifted_time_expr = RequestLogORM.request_time

        # Build bucket start timestamp in UTC (returned as a UTC-aware datetime at API boundary).
        # For timezone bucketing, we:
        # 1) shift request_time (UTC) into "local" (UTC + offset)
        # 2) truncate to bucket boundary in that local clock
        # 3) shift the bucket start back to UTC for stable API output
        if query.bucket == "minute":
            bucket_minutes = int(query.bucket_minutes or 1)
            if bucket_minutes < 1:
                bucket_minutes = 1
            if bucket_minutes > 1440:
                bucket_minutes = 1440

            if dialect_name == "sqlite":
                epoch_seconds = cast(func.strftime("%s", shifted_time_expr), Integer)
                bucket_seconds = bucket_minutes * 60
                bucket_local_start_expr = func.datetime(
                    (epoch_seconds / bucket_seconds) * bucket_seconds,
                    "unixepoch",
                )
            else:
                minutes_since_hour = func.extract("minute", shifted_time_expr)
                bucket_index = func.floor(minutes_since_hour / bucket_minutes)
                bucket_minute = bucket_index * bucket_minutes
                bucket_local_start_expr = func.date_trunc(
                    "hour", shifted_time_expr
                ) + _pg_make_interval_minutes(
                    bucket_minute  # type: ignore[arg-type]
                )
        elif query.bucket == "hour":
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
                bucket_start_utc_expr = (
                    bucket_local_start_expr
                    - _pg_make_interval_minutes(tz_offset_minutes)
                )
        else:
            bucket_start_utc_expr = bucket_local_start_expr

        trend_stmt = (
            select(
                bucket_start_utc_expr.label("bucket"),
                func.count().label("request_count"),
                sum_total.label("total_cost"),
                sum_input.label("input_cost"),
                sum_output.label("output_cost"),
                sum_in_tokens.label("input_tokens"),
                sum_out_tokens.label("output_tokens"),
                sum_failure.label("error_count"),
                sum_success.label("success_count"),
            )
            .group_by(bucket_start_utc_expr)
            .order_by(bucket_start_utc_expr)
        )
        trend_stmt = trend_stmt.where(root_where_clause)
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
                success_count=int(r["success_count"] or 0),
            )
            for r in trend_rows
        ]

        # Determine grouping column based on query.group_by
        # If group_by="provider_model", we group by target_model (the actual model used)
        # Otherwise default to requested_model
        group_column = RequestLogORM.requested_model
        if getattr(query, "group_by", "request_model") == "provider_model":
            group_column = RequestLogORM.target_model

        by_model_stmt = (
            select(
                func.coalesce(group_column, "").label("requested_model"),
                func.count().label("request_count"),
                sum_total.label("total_cost"),
                sum_in_tokens.label("input_tokens"),
                sum_out_tokens.label("output_tokens"),
            )
            .group_by(group_column)
            .order_by(sum_total.desc())
            .limit(50)
        )
        by_model_stmt = by_model_stmt.where(root_where_clause)
        model_rows = (await self.session.execute(by_model_stmt)).mappings().all()
        by_model = [
            LogCostByModel(
                requested_model=r["requested_model"] or "-",
                request_count=int(r["request_count"] or 0),
                total_cost=float(r["total_cost"] or 0),
                input_tokens=int(r["input_tokens"] or 0),
                output_tokens=int(r["output_tokens"] or 0),
            )
            for r in model_rows
        ]

        # By Model Tokens (Top 50 by usage)
        by_model_tokens_stmt = (
            select(
                func.coalesce(group_column, "").label("requested_model"),
                func.count().label("request_count"),
                sum_total.label("total_cost"),
                sum_in_tokens.label("input_tokens"),
                sum_out_tokens.label("output_tokens"),
            )
            .group_by(group_column)
            .order_by((sum_in_tokens + sum_out_tokens).desc())
            .limit(50)
        )
        by_model_tokens_stmt = by_model_tokens_stmt.where(root_where_clause)
        model_tokens_rows = (
            (await self.session.execute(by_model_tokens_stmt)).mappings().all()
        )
        by_model_tokens = [
            LogCostByModel(
                requested_model=r["requested_model"] or "-",
                request_count=int(r["request_count"] or 0),
                total_cost=float(r["total_cost"] or 0),
                input_tokens=int(r["input_tokens"] or 0),
                output_tokens=int(r["output_tokens"] or 0),
            )
            for r in model_tokens_rows
        ]

        provider_name_expr = func.coalesce(RequestLogORM.provider_name, "-")
        model_name_expr = func.coalesce(
            RequestLogORM.target_model,
            RequestLogORM.requested_model,
            "-",
        )
        stream_ttfb = case(
            (
                and_(
                    RequestLogORM.is_stream.is_(True),
                    RequestLogORM.first_byte_delay_ms.isnot(None),
                ),
                RequestLogORM.first_byte_delay_ms,
            )
        )
        model_call_stmt = (
            select(
                provider_name_expr.label("provider_name"),
                model_name_expr.label("model_name"),
                func.count().label("request_count"),
                sum_success.label("success_count"),
                sum_failure.label("failure_count"),
                func.avg(stream_ttfb).label("avg_first_byte_time_ms"),
                func.max(stream_ttfb).label("max_first_byte_time_ms"),
            )
            .group_by(provider_name_expr, model_name_expr)
            .order_by(func.count().desc(), provider_name_expr, model_name_expr)
        )
        model_call_stmt = model_call_stmt.where(
            attempt_where_clause,
            is_upstream_attempt,
        )
        model_call_rows = (
            (await self.session.execute(model_call_stmt)).mappings().all()
        )
        model_call_stats = []
        for row in model_call_rows:
            total = int(row["request_count"] or 0)
            successes = int(row["success_count"] or 0)
            model_call_stats.append(
                ModelCallStats(
                    provider_name=row["provider_name"] or "-",
                    model_name=row["model_name"] or "-",
                    request_count=total,
                    success_count=successes,
                    failure_count=int(row["failure_count"] or 0),
                    success_rate=successes / total if total > 0 else 0.0,
                    avg_first_byte_time_ms=(
                        float(row["avg_first_byte_time_ms"])
                        if row["avg_first_byte_time_ms"] is not None
                        else None
                    ),
                    max_first_byte_time_ms=(
                        float(row["max_first_byte_time_ms"])
                        if row["max_first_byte_time_ms"] is not None
                        else None
                    ),
                )
            )

        return LogCostStatsResponse(
            summary=summary,
            trend=trend,
            by_model=by_model,
            by_model_tokens=by_model_tokens,
            model_call_stats=model_call_stats,
        )

    async def get_model_stats(
        self, requested_model: str | None = None
    ) -> list[ModelStats]:
        cutoff_time = to_utc_naive(utc_now() - timedelta(days=7))
        conditions = []
        if cutoff_time:
            conditions.append(RequestLogORM.request_time >= cutoff_time)
        if requested_model:
            conditions.append(RequestLogORM.requested_model == requested_model)
        else:
            conditions.append(RequestLogORM.requested_model.isnot(None))

        where_clause = and_(*conditions) if conditions else None

        error_condition = RequestLogORM.response_status >= 400

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

        error_condition = RequestLogORM.response_status >= 400

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

    async def get_api_key_monthly_costs(
        self, api_key_ids: list[int] | None = None
    ) -> list[ApiKeyMonthlyCost]:
        """
        Get current month's total cost grouped by API Key ID

        Args:
            api_key_ids: Optional list of API Key IDs to filter.
                         If None, returns stats for all API Keys with costs.

        Returns:
            list[ApiKeyMonthlyCost]: List of API Key monthly cost summaries
        """
        # Calculate the start of the current month in UTC
        now = utc_now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_start_naive = to_utc_naive(month_start)

        conditions = [
            RequestLogORM.request_time >= month_start_naive,
            RequestLogORM.api_key_id.isnot(None),
        ]

        if api_key_ids is not None and len(api_key_ids) > 0:
            conditions.append(RequestLogORM.api_key_id.in_(api_key_ids))

        where_clause = and_(*conditions)

        sum_total = func.coalesce(func.sum(RequestLogORM.total_cost), 0)

        stmt = (
            select(
                RequestLogORM.api_key_id.label("api_key_id"),
                sum_total.label("total_cost"),
            )
            .where(where_clause)
            .group_by(RequestLogORM.api_key_id)
        )

        rows = (await self.session.execute(stmt)).mappings().all()
        return [
            ApiKeyMonthlyCost(
                api_key_id=int(row["api_key_id"]),
                total_cost=float(row["total_cost"] or 0),
            )
            for row in rows
        ]
