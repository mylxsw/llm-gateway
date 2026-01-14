"""
Provider Domain Model

Defines Provider related Data Transfer Objects (DTOs).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ProviderBase(BaseModel):
    """Provider Base Model"""
    
    # Provider Name
    name: str = Field(..., min_length=1, max_length=100, description="Provider Name")
    # Base URL
    base_url: str = Field(..., description="Base URL")
    # Protocol Type: openai or anthropic
    protocol: str = Field(..., pattern="^(openai|anthropic)$", description="Protocol Type")
    # API Type: chat / completion / embedding
    api_type: str = Field(..., description="API Type")
    # Extra Headers
    extra_headers: Optional[dict[str, str]] = Field(None, description="Extra Headers")


class ProviderCreate(ProviderBase):
    """Create Provider Request Model"""
    
    # Provider API Key (Optional)
    api_key: Optional[str] = Field(None, description="Provider API Key")
    # Is Active
    is_active: bool = Field(True, description="Is Active")


class ProviderUpdate(BaseModel):
    """Update Provider Request Model (All fields optional)"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    base_url: Optional[str] = None
    protocol: Optional[str] = Field(None, pattern="^(openai|anthropic)$")
    api_type: Optional[str] = None
    api_key: Optional[str] = None
    extra_headers: Optional[dict[str, str]] = None
    is_active: Optional[bool] = None


class Provider(ProviderBase):
    """Provider Complete Model"""
    
    id: int = Field(..., description="Provider ID")
    api_key: Optional[str] = Field(None, description="Provider API Key")
    extra_headers: Optional[dict[str, str]] = Field(None, description="Extra Headers")
    is_active: bool = Field(True, description="Is Active")
    created_at: datetime = Field(..., description="Creation Time")
    updated_at: datetime = Field(..., description="Update Time")
    
    class Config:
        from_attributes = True


class ProviderResponse(ProviderBase):
    """Provider Response Model (API Key Sanitized)"""
    
    id: int = Field(..., description="Provider ID")
    # API Key Sanitized Display
    api_key: Optional[str] = Field(None, description="Provider API Key (Sanitized)")
    extra_headers: Optional[dict[str, str]] = Field(None, description="Extra Headers")
    is_active: bool = Field(True, description="Is Active")
    created_at: datetime = Field(..., description="Creation Time")
    updated_at: datetime = Field(..., description="Update Time")
    
    class Config:
        from_attributes = True


class ProviderExport(ProviderCreate):
    """Provider Export Model (Includes API Key)"""
    pass