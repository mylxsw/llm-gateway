"""
Provider Domain Model

Defines Provider related Data Transfer Objects (DTOs).
"""

import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.provider_protocols import FRONTEND_PROTOCOL_PATTERN
from app.common.url_validator import validate_provider_url_loose

logger = logging.getLogger(__name__)


class ProviderBase(BaseModel):
    """Provider Base Model"""

    # Provider Name
    name: str = Field(..., min_length=1, max_length=100, description="Provider Name")
    # Remark
    remark: Optional[str] = Field(None, max_length=500, description="Provider Remark")
    # Base URL
    base_url: str = Field(..., description="Base URL")
    # Protocol Type (frontend protocol)
    protocol: str = Field(..., pattern=FRONTEND_PROTOCOL_PATTERN, description="Protocol Type")
    # API Type: chat / completion / embedding
    api_type: str = Field("chat", description="API Type (deprecated)")
    # Extra Headers
    extra_headers: Optional[dict[str, str]] = Field(None, description="Extra Headers")
    # Provider Options (JSON format)
    provider_options: Optional[dict[str, Any]] = Field(
        None, description="Provider Options"
    )
    # Proxy Enabled
    proxy_enabled: bool = Field(False, description="Proxy Enabled")
    # Proxy URL (schema://auth@host:port)
    proxy_url: Optional[str] = Field(None, description="Proxy URL")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base_url to prevent SSRF"""
        try:
            return validate_provider_url_loose(v)
        except Exception as e:
            logger.warning("Provider base_url validation failed: %s", str(e))
            raise ValueError(f"Invalid base_url: {str(e)}")


class ProviderCreate(ProviderBase):
    """Create Provider Request Model"""
    
    # Provider API Key (Optional)
    api_key: Optional[str] = Field(None, description="Provider API Key")
    # Is Active
    is_active: bool = Field(True, description="Is Active")


class ProviderUpdate(BaseModel):
    """Update Provider Request Model (All fields optional)"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    remark: Optional[str] = Field(None, max_length=500)
    base_url: Optional[str] = None
    protocol: Optional[str] = Field(None, pattern=FRONTEND_PROTOCOL_PATTERN)
    api_type: Optional[str] = None
    api_key: Optional[str] = None
    extra_headers: Optional[dict[str, str]] = None
    provider_options: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    proxy_enabled: Optional[bool] = None
    proxy_url: Optional[str] = None


class Provider(ProviderBase):
    """Provider Complete Model"""
    
    id: int = Field(..., description="Provider ID")
    api_key: Optional[str] = Field(None, description="Provider API Key")
    extra_headers: Optional[dict[str, str]] = Field(None, description="Extra Headers")
    provider_options: Optional[dict[str, Any]] = Field(
        None, description="Provider Options"
    )
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
    provider_options: Optional[dict[str, Any]] = Field(
        None, description="Provider Options"
    )
    proxy_url: Optional[str] = Field(None, description="Proxy URL (Sanitized)")
    is_active: bool = Field(True, description="Is Active")
    created_at: datetime = Field(..., description="Creation Time")
    updated_at: datetime = Field(..., description="Update Time")
    
    model_config = ConfigDict(from_attributes=True)


class ProviderExport(ProviderCreate):
    """Provider Export Model (Includes API Key)"""
    pass
