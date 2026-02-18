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
