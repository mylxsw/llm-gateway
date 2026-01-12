"""
Log Repository SQLAlchemy Implementation

Provides concrete database operation implementation for request logs.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequestLog as RequestLogORM
from app.domain.log import RequestLogModel, RequestLogCreate, RequestLogQuery
from app.repositories.log_repo import LogRepository


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
        request_time = entity.request_time
        if request_time and request_time.tzinfo is None:
            request_time = request_time.replace(tzinfo=timezone.utc)
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
            request_headers=entity.request_headers,
            request_body=entity.request_body,
            response_status=entity.response_status,
            response_body=entity.response_body,
            error_info=entity.error_info,
            matched_provider_count=entity.matched_provider_count,
            trace_id=entity.trace_id,
            is_stream=entity.is_stream,
        )
    
    async def create(self, data: RequestLogCreate) -> RequestLogModel:
        """Create request log"""
        entity = RequestLogORM(
            request_time=data.request_time,
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
            request_headers=data.request_headers,
            request_body=data.request_body,
            response_status=data.response_status,
            response_body=data.response_body,
            error_info=data.error_info,
            trace_id=data.trace_id,
            is_stream=data.is_stream,
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
            conditions.append(RequestLogORM.request_time >= query.start_time)
        if query.end_time:
            conditions.append(RequestLogORM.request_time <= query.end_time)
        
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
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        stmt = delete(RequestLogORM).where(RequestLogORM.request_time < cutoff_time)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount
