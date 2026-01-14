"""
Model Mapping Domain Model

Defines Model Mapping and Model-Provider Mapping related Data Transfer Objects (DTOs).
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelMappingBase(BaseModel):
    """Model Mapping Base Model"""
    
    # Requested Model Name (Primary Key)
    requested_model: str = Field(
        ..., min_length=1, max_length=100, description="Requested Model Name"
    )
    # Selection Strategy, currently only supports round_robin
    strategy: str = Field("round_robin", description="Selection Strategy")


class ModelMappingCreate(ModelMappingBase):
    """Create Model Mapping Request Model"""
    
    # Model Level Matching Rules
    matching_rules: Optional[dict[str, Any]] = Field(None, description="Matching Rules")
    # Model Capabilities Description
    capabilities: Optional[dict[str, Any]] = Field(None, description="Model Capabilities")
    # Is Active
    is_active: bool = Field(True, description="Is Active")


class ModelMappingUpdate(BaseModel):
    """Update Model Mapping Request Model"""
    
    strategy: Optional[str] = None
    matching_rules: Optional[dict[str, Any]] = None
    capabilities: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class ModelMapping(ModelMappingBase):
    """Model Mapping Complete Model"""
    
    matching_rules: Optional[dict[str, Any]] = None
    capabilities: Optional[dict[str, Any]] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ModelMappingResponse(ModelMapping):
    """Model Mapping Response Model (Includes Provider Count)"""
    
    # Associated Provider Count
    provider_count: int = Field(0, description="Associated Provider Count")
    # Associated Provider List (Returned in detail query)
    providers: Optional[list["ModelMappingProviderResponse"]] = None
    
    class Config:
        from_attributes = True


# ============ Model-Provider Mapping ============

class ModelMappingProviderBase(BaseModel):
    """Model-Provider Mapping Base Model"""
    
    # Requested Model Name
    requested_model: str = Field(..., description="Requested Model Name")
    # Provider ID
    provider_id: int = Field(..., description="Provider ID")
    # Target Model Name (Actual model used by this provider)
    target_model_name: str = Field(..., min_length=1, max_length=100, description="Target Model Name")


class ModelMappingProviderCreate(ModelMappingProviderBase):
    """Create Model-Provider Mapping Request Model"""
    
    # Provider Level Matching Rules
    provider_rules: Optional[dict[str, Any]] = Field(None, description="Provider Level Rules")
    # Priority (Lower value means higher priority)
    priority: int = Field(0, description="Priority")
    # Weight
    weight: int = Field(1, ge=1, description="Weight")
    # Is Active
    is_active: bool = Field(True, description="Is Active")


class ModelMappingProviderUpdate(BaseModel):
    """Update Model-Provider Mapping Request Model"""
    
    target_model_name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider_rules: Optional[dict[str, Any]] = None
    priority: Optional[int] = None
    weight: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class ModelMappingProvider(ModelMappingProviderBase):
    """Model-Provider Mapping Complete Model"""
    
    id: int
    provider_rules: Optional[dict[str, Any]] = None
    priority: int = 0
    weight: int = 1
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ModelMappingProviderResponse(ModelMappingProvider):
    """Model-Provider Mapping Response Model (Includes Provider Name)"""
    
    # Provider Name
    provider_name: str = Field("", description="Provider Name")
    # Provider Protocol Type: openai or anthropic
    provider_protocol: Optional[str] = Field(None, description="Provider Protocol Type")
    
    class Config:
        from_attributes = True


class ModelProviderExport(BaseModel):
    """Model Provider Export Model (Uses Provider Name instead of ID)"""
    provider_name: str
    target_model_name: str
    provider_rules: Optional[dict[str, Any]] = None
    priority: int = 0
    weight: int = 1
    is_active: bool = True


class ModelExport(ModelMappingCreate):
    """Model Export Model"""
    providers: list[ModelProviderExport] = []


# Resolve circular reference
ModelMappingResponse.model_rebuild()