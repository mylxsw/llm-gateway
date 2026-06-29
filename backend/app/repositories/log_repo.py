"""
Log Repository Interface

Defines the data access interface for request logs.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple

from app.domain.log import (
    RequestLogModel,
    RequestLogCreate,
    RequestLogQuery,
    RequestLogSummary,
    LogCostStatsQuery,
    LogCostStatsResponse,
    ModelStats,
    ModelProviderStats,
    ApiKeyMonthlyCost,
)


class LogRepository(ABC):
    """Log Repository Interface"""
    
    @abstractmethod
    async def create(self, data: RequestLogCreate) -> RequestLogModel:
        """
        Create Request Log

        Args:
            data: Log creation data

        Returns:
            RequestLogModel: Created log model
        """
        pass

    @abstractmethod
    async def create_initial(self, data: RequestLogCreate) -> int:
        """
        Create a minimal log entry (is_completed=False) when a request is received.
        Returns the new log ID for later update.

        Args:
            data: Log creation data (minimal fields)

        Returns:
            int: The ID of the created log entry
        """
        pass

    @abstractmethod
    async def update(self, log_id: int, data: RequestLogCreate) -> RequestLogModel:
        """
        Update an existing log entry with completion data, setting is_completed=True.

        Args:
            log_id: ID of the log entry to update
            data: Completion data

        Returns:
            RequestLogModel: Updated log model
        """
        pass

    @abstractmethod
    async def cancel(self, log_id: int, error_info: str = "Request cancelled by admin") -> None:
        """
        Mark an in-progress log as cancelled (is_completed=True, with error_info).
        
        Args:
            log_id: ID of the log entry to cancel
            error_info: Error message to record
            
        Raises:
            NotFoundError: If no in-progress request found with given ID
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, id: int) -> RequestLogModel | None:
        """
        Get Log Details by ID
        
        Args:
            id: Log ID
            
        Returns:
            RequestLogModel | None: Log model or None
        """
        pass

    @abstractmethod
    async def get_by_trace_id(self, trace_id: str) -> RequestLogModel | None:
        """
        Get Log Details by trace ID

        Args:
            trace_id: Request trace ID

        Returns:
            RequestLogModel | None: Log model or None
        """
        pass

    @abstractmethod
    async def find_latest_retry_candidate(
        self,
        *,
        min_id: int,
        api_key_id: int,
        request_path: str,
    ) -> RequestLogModel | None:
        """
        Find the latest log created after a given log ID for retry fallback.

        Args:
            min_id: Lower bound for new log ID
            api_key_id: API key ID used by the replayed request
            request_path: Original request path

        Returns:
            RequestLogModel | None: Candidate log or None
        """
        pass
    
    @abstractmethod
    async def query(self, query: RequestLogQuery) -> Tuple[List[RequestLogSummary], int]:
        """
        Query Logs (summary view, no large fields)

        Args:
            query: Query conditions

        Returns:
            Tuple[List[RequestLogSummary], int]: (Log summary list, Total count)
        """
        pass
    
    @abstractmethod
    async def cleanup_old_logs(self, days_to_keep: int) -> int:
        """
        Clean up old logs
        
        Args:
            days_to_keep: Number of days to keep logs
            
        Returns:
            int: Number of deleted logs
        """
        pass

    @abstractmethod
    async def cleanup_old_log_details(self, days_to_keep: int) -> int:
        """
        Clean up old log detail rows while keeping summary logs.

        Args:
            days_to_keep: Number of days to keep detailed payload data

        Returns:
            int: Number of deleted detail rows
        """
        pass

    @abstractmethod
    async def get_cost_stats(self, query: LogCostStatsQuery) -> LogCostStatsResponse:
        """Get aggregated cost stats for logs"""
        pass

    @abstractmethod
    async def get_model_stats(self, requested_model: str | None = None) -> list[ModelStats]:
        """Get aggregated model stats for logs"""
        pass

    @abstractmethod
    async def get_model_provider_stats(
        self, requested_model: str | None = None
    ) -> list[ModelProviderStats]:
        """Get aggregated model-provider stats for logs"""
        pass

    @abstractmethod
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
        pass
