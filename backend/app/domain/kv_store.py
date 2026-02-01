"""
Key-Value Store Domain Model

Defines KV Store related Data Transfer Objects (DTOs).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class KeyValueModel(BaseModel):
    """Key-Value Complete Model"""
    
    key: str = Field(..., description="Key")
    value: str = Field(..., description="Value")
    expires_at: Optional[datetime] = Field(None, description="Expiration Time")
    created_at: datetime = Field(..., description="Creation Time")
    updated_at: datetime = Field(..., description="Update Time")
    
    model_config = ConfigDict(from_attributes=True)
