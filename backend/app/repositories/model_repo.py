"""
Model Repository Interface

Defines the data access interface for Model Mappings and Model-Provider Mappings.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple

from app.domain.model import (
    ModelMapping,
    ModelMappingCreate,
    ModelMappingUpdate,
    ModelMappingProvider,
    ModelMappingProviderCreate,
    ModelMappingProviderUpdate,
    ModelMappingProviderResponse,
)


class ModelRepository(ABC):
    """Model Repository Interface"""
    
    # ============ Model Mapping ============
    
    @abstractmethod
    async def create_mapping(self, data: ModelMappingCreate) -> ModelMapping:
        """Create Model Mapping"""
        pass
    
    @abstractmethod
    async def get_mapping(self, requested_model: str) -> Optional[ModelMapping]:
        """Get Model Mapping"""
        pass
    
    @abstractmethod
    async def get_all_mappings(
        self,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ModelMapping], int]:
        """Get Model Mapping List"""
        pass
    
    @abstractmethod
    async def update_mapping(self, requested_model: str, data: ModelMappingUpdate) -> Optional[ModelMapping]:
        """Update Model Mapping"""
        pass
    
    @abstractmethod
    async def delete_mapping(self, requested_model: str) -> bool:
        """Delete Model Mapping (Cascades delete associated provider mappings)"""
        pass
    
    # ============ Model-Provider Mapping ============
    
    @abstractmethod
    async def add_provider_mapping(
        self, data: ModelMappingProviderCreate
    ) -> ModelMappingProviderResponse:
        """Add Model-Provider Mapping"""
        pass
    
    @abstractmethod
    async def get_provider_mapping(self, id: int) -> Optional[ModelMappingProvider]:
        """Get Single Model-Provider Mapping"""
        pass
    
    @abstractmethod
    async def get_provider_mappings(
        self, 
        requested_model: str,
        is_active: Optional[bool] = None
    ) -> List[ModelMappingProviderResponse]:
        """
        Get all provider mappings under a requested model
        
        Returns:
            List containing provider details
        """
        pass
    
    @abstractmethod
    async def get_all_provider_mappings(
        self,
        requested_model: Optional[str] = None,
        provider_id: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> List[ModelMappingProviderResponse]:
        """Get all model-provider mappings (supports filtering)"""
        pass

    @abstractmethod
    async def get_provider_count(self, requested_model: str) -> int:
        """Get the count of providers associated with the model"""
        pass
    
    @abstractmethod
    async def update_provider_mapping(self, id: int, data: ModelMappingProviderUpdate) -> Optional[ModelMappingProvider]:
        """Update Model-Provider Mapping"""
        pass
    
    @abstractmethod
    async def delete_provider_mapping(self, id: int) -> bool:
        """Delete Model-Provider Mapping"""
        pass
