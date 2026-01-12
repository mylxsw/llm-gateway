"""
Log Repository Interface

Defines the data access interface for request logs.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple

from app.domain.log import RequestLogModel, RequestLogCreate, RequestLogQuery


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
    async def query(self, query: RequestLogQuery) -> Tuple[List[RequestLogModel], int]:
        """
        Query Logs
        
        Args:
            query: Query conditions
            
        Returns:
            Tuple[List[RequestLogModel], int]: (Log list, Total count)
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