"""
Provider Repository Interface

Defines the data access interface for Providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple

from app.domain.provider import Provider, ProviderCreate, ProviderUpdate


class ProviderRepository(ABC):
    """Provider Repository Interface"""
    
    @abstractmethod
    async def create(self, data: ProviderCreate) -> Provider:
        """Create Provider"""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[Provider]:
        """Get Provider by ID"""
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Provider]:
        """Get Provider by Name"""
        pass
    
    @abstractmethod
    async def get_all(
        self, 
        page: int = 1, 
        page_size: int = 20, 
        is_active: Optional[bool] = None,
        name: Optional[str] = None,
        protocol: Optional[str] = None
    ) -> Tuple[List[Provider], int]:
        """Get Provider List (Pagination)"""
        pass
    
    @abstractmethod
    async def update(self, id: int, data: ProviderUpdate) -> Optional[Provider]:
        """Update Provider"""
        pass
    
    @abstractmethod
    async def delete(self, id: int) -> bool:
        """Delete Provider"""
        pass

    @abstractmethod
    async def has_model_mappings(self, id: int) -> bool:
        """Check if provider has associated model mappings"""
        pass