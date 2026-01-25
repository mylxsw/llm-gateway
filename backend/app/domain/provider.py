"""
Provider Domain Model

Defines Provider related Data Transfer Objects (DTOs).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.common.provider_protocols import FRONTEND_PROTOCOL_PATTERN


class ProviderBase(BaseModel):
    """Provider Base Model"""
    
    # Provider Name
    name: str = Field(..., min_length=1, max_length=100, description="Provider Name")
    # Base URL
    base_url: str = Field(..., description="Base URL")
    # Protocol Type (frontend protocol)
    protocol: str = Field(..., pattern=FRONTEND_PROTOCOL_PATTERN, description="Protocol Type")
    # API Type: chat / completion / embedding
    api_type: str = Field("chat", description="API Type (deprecated)")
    # Extra Headers
    extra_headers: Optional[dict[str, str]] = Field(None, description="Extra Headers")
    # Proxy Enabled
    proxy_enabled: bool = Field(False, description="Proxy Enabled")
    # Proxy URL (schema://auth@host:port)
    proxy_url: Optional[str] = Field(None, description="Proxy URL")


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
    protocol: Optional[str] = Field(None, pattern=FRONTEND_PROTOCOL_PATTERN)
    api_type: Optional[str] = None
    api_key: Optional[str] = None
    extra_headers: Optional[dict[str, str]] = None
    is_active: Optional[bool] = None
    proxy_enabled: Optional[bool] = None
    proxy_url: Optional[str] = None


class Provider(ProviderBase):
    """Provider Complete Model"""
    
    id: int = Field(..., description="Provider ID")
    api_key: Optional[str] = Field(None, description="Provider API Key")
    extra_headers: Optional[dict[str, str]] = Field(None, description="Extra Headers")
    is_active: bool = Field(True, description="Is Active")
    created_at: datetime = Field(..., description="Creation Time")
    updated_at: datetime = Field(..., description="Update Time")
    
    model_config = ConfigDict(from_attributes=True)


class ProviderResponse(ProviderBase):
    """Provider Response Model (API Key Sanitized)"""
    
    id: int = Field(..., description="Provider ID")
    # API Key Sanitized Display
    api_key: Optional[str] = Field(None, description="Provider API Key (Sanitized)")
    extra_headers: Optional[dict[str, str]] = Field(None, description="Extra Headers")
    proxy_url: Optional[str] = Field(None, description="Proxy URL (Sanitized)")
    is_active: bool = Field(True, description="Is Active")
    created_at: datetime = Field(..., description="Creation Time")
    updated_at: datetime = Field(..., description="Update Time")
    
    model_config = ConfigDict(from_attributes=True)


class ProviderExport(ProviderCreate):
    """Provider Export Model (Includes API Key)"""
    pass
