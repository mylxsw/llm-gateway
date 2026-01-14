"""
API Key Repository Interface

Defines the data access interface for API Keys.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from datetime import datetime

from app.domain.api_key import ApiKeyModel, ApiKeyCreate, ApiKeyUpdate


class ApiKeyRepository(ABC):
    """API Key Repository Interface"""
    
    @abstractmethod
    async def create(self, data: ApiKeyCreate, key_value: str) -> ApiKeyModel:
        """
        Create API Key
        
        Args:
            data: Creation data
            key_value: Generated key value (token)
            
        Returns:
            ApiKeyModel: Created API Key model
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[ApiKeyModel]:
        """Get API Key by ID"""
        pass
    
    @abstractmethod
    async def get_by_key_value(self, key_value: str) -> Optional[ApiKeyModel]:
        """Get API Key by Key Value (for authentication)"""
        pass
    
    @abstractmethod
    async def get_all(
        self, 
        page: int = 1, 
        page_size: int = 20,
        is_active: Optional[bool] = None
    ) -> Tuple[List[ApiKeyModel], int]:
        """
        Get API Key List (Pagination)
        
        Args:
            page: Page number
            page_size: Items per page
            is_active: Filter by active status
            
        Returns:
            Tuple[List[ApiKeyModel], int]: (List, Total count)
        """
        pass
    
    @abstractmethod
    async def update(self, id: int, data: ApiKeyUpdate) -> Optional[ApiKeyModel]:
        """Update API Key"""
        pass
    
    @abstractmethod
    async def update_last_used(self, id: int, last_used_at: datetime) -> None:
        """Update Last Used Time"""
        pass
    
    @abstractmethod
    async def delete(self, id: int) -> bool:
        """Delete API Key"""
        pass