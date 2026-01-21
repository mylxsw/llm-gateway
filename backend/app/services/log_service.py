"""
Log Service Module

Provides business logic processing for request logs.
"""

import logging
from typing import Optional

from app.common.errors import NotFoundError
from app.domain.log import (
    RequestLogModel,
    RequestLogCreate,
    RequestLogResponse,
    RequestLogQuery,
    LogCostStatsQuery,
    LogCostStatsResponse,
    ModelStats,
    ModelProviderStats,
)
from app.repositories.log_repo import LogRepository

logger = logging.getLogger(__name__)


class LogService:
    """
    Log Service
    
    Handles business logic related to request logs.
    """
    
    def __init__(self, repo: LogRepository):
        """
        Initialize Service
        
        Args:
            repo: Log Repository
        """
        self.repo = repo
    
    async def create(self, data: RequestLogCreate) -> RequestLogModel:
        """
        Create Request Log
        
        Args:
            data: Creation data
        
        Returns:
            RequestLogModel: Created log
        """
        return await self.repo.create(data)
    
    async def get_by_id(self, id: int) -> RequestLogModel:
        """
        Get Log Details by ID
        
        Args:
            id: Log ID
        
        Returns:
            RequestLogModel: Log details
        
        Raises:
            NotFoundError: Log not found
        """
        log = await self.repo.get_by_id(id)
        if not log:
            raise NotFoundError(
                message=f"Request log with id {id} not found",
                code="log_not_found",
            )
        return log
    
    async def query(
        self, query: RequestLogQuery
    ) -> tuple[list[RequestLogResponse], int]:
        """
        Query Log List
        
        Args:
            query: Query conditions
        
        Returns:
            tuple[list[RequestLogResponse], int]: (Log list, Total count)
        """
        logs, total = await self.repo.query(query)
        
        # Convert to response model (list view does not include detailed request/response body)
        responses = [
            RequestLogResponse(
                id=log.id,
                request_time=log.request_time,
                api_key_id=log.api_key_id,
                api_key_name=log.api_key_name,
                requested_model=log.requested_model,
                target_model=log.target_model,
                provider_id=log.provider_id,
                provider_name=log.provider_name,
                retry_count=log.retry_count,
                first_byte_delay_ms=log.first_byte_delay_ms,
                total_time_ms=log.total_time_ms,
                input_tokens=log.input_tokens,
                output_tokens=log.output_tokens,
                total_cost=log.total_cost,
                input_cost=log.input_cost,
                output_cost=log.output_cost,
                response_status=log.response_status,
                trace_id=log.trace_id,
                is_stream=log.is_stream,
            )
            for log in logs
        ]

        return responses, total

    async def cleanup_old_logs(self, retention_days: int) -> int:
        """
        Clean up old logs older than specified days

        Args:
            retention_days: Number of days to keep

        Returns:
            int: Number of deleted logs
        """
        try:
            deleted_count = await self.repo.cleanup_old_logs(retention_days)
            logger.info(
                f"Log cleanup completed: {deleted_count} logs older than {retention_days} days deleted"
            )
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {str(e)}", exc_info=True)
            raise

    async def get_cost_stats(self, query: LogCostStatsQuery) -> LogCostStatsResponse:
        return await self.repo.get_cost_stats(query)

    async def get_model_stats(self, requested_model: str | None = None) -> list[ModelStats]:
        return await self.repo.get_model_stats(requested_model)

    async def get_model_provider_stats(
        self, requested_model: str | None = None
    ) -> list[ModelProviderStats]:
        return await self.repo.get_model_provider_stats(requested_model)
