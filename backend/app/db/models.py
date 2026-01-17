"""
SQLAlchemy ORM Model Definitions

Defines all database table structures for the system, including:
- service_providers: Service Providers Table
- model_mappings: Model Mappings Table
- model_mapping_providers: Model-Provider Mappings Table
- api_keys: API Keys Table
- request_logs: Request Logs Table
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy ORM Base Class"""
    pass


class ServiceProvider(Base):
    """
    Service Providers Table
    
    Stores configuration for upstream LLM providers, including base URL, protocol type, etc.
    """
    __tablename__ = "service_providers"
    
    # Primary Key ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Provider Name, unique
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Base URL, e.g., https://api.openai.com
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Protocol type: openai or anthropic
    protocol: Mapped[str] = mapped_column(String(50), nullable=False)
    # API Type: chat / completion / embedding
    api_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Provider API Key (Encrypted storage recommended)
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Extra Headers (JSON format)
    extra_headers: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # Is Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Creation Time
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # Update Time
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationship: Model mappings under this provider
    model_mappings: Mapped[list["ModelMappingProvider"]] = relationship(
        "ModelMappingProvider", back_populates="provider"
    )


class ModelMapping(Base):
    """
    Model Mappings Table
    
    Keyed by requested_model (client requested model name),
    defines model selection strategy and matching rules.
    """
    __tablename__ = "model_mappings"
    
    # Requested model name as Primary Key
    requested_model: Mapped[str] = mapped_column(
        String(100), primary_key=True, nullable=False
    )
    # Selection strategy: round_robin or cost_first
    strategy: Mapped[str] = mapped_column(String(50), default="round_robin")
    # Model-level matching rules (JSON format)
    matching_rules: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # Model capabilities description (JSON format)
    capabilities: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # Default pricing (USD per 1,000,000 tokens)
    input_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    output_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    # Is Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Creation Time
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # Update Time
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Relationship: Provider mappings under this model
    providers: Mapped[list["ModelMappingProvider"]] = relationship(
        "ModelMappingProvider", back_populates="model_mapping"
    )


class ModelMappingProvider(Base):
    """
    Model-Provider Mappings Table
    
    Defines the target model name for the same requested_model under different providers.
    This is the core table supporting mapping of the same requested model to different actual models across providers.
    """
    __tablename__ = "model_mapping_providers"
    
    # Primary Key ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Requested Model Name (Foreign Key)
    requested_model: Mapped[str] = mapped_column(
        String(100), 
        ForeignKey("model_mappings.requested_model", ondelete="CASCADE"),
        nullable=False
    )
    # Provider ID (Foreign Key)
    provider_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("service_providers.id", ondelete="CASCADE"),
        nullable=False
    )
    # Target model name for this provider (actual model used for forwarding)
    target_model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Provider-level matching rules (JSON format)
    provider_rules: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # Provider override pricing (USD per 1,000,000 tokens)
    input_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    output_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    # Billing mode: token_flat / token_tiered / per_request (NULL treated as token_flat for backward compatibility)
    billing_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Per-request fixed price (USD)
    per_request_price: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    # Tiered pricing config (JSON). Used when billing_mode == "token_tiered"
    tiered_pricing: Mapped[Optional[list]] = mapped_column(SQLiteJSON, nullable=True)
    # Priority (Lower value means higher priority)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    # Weight (Used for weighted round-robin, currently unused)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    # Is Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Creation Time
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # Update Time
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # Unique Constraint: Only one mapping per provider for the same model
    __table_args__ = (
        UniqueConstraint("requested_model", "provider_id", name="uq_model_provider"),
    )
    
    # Relationships
    provider: Mapped["ServiceProvider"] = relationship(
        "ServiceProvider", back_populates="model_mappings"
    )
    model_mapping: Mapped["ModelMapping"] = relationship(
        "ModelMapping", back_populates="providers"
    )


class ApiKey(Base):
    """
    API Keys Table
    
    API Key entity used for client authentication.
    """
    __tablename__ = "api_keys"
    
    # Primary Key ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Key Name, unique, identifies usage
    key_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Key Value (randomly generated token), unique
    key_value: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Is Active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Creation Time
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # Last Used Time
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationship: Request logs for this Key
    logs: Mapped[list["RequestLog"]] = relationship("RequestLog", back_populates="api_key")


class RequestLog(Base):
    """
    Request Logs Table
    
    Records detailed information for all proxy requests, including time, model, provider, token usage, etc.
    """
    __tablename__ = "request_logs"
    
    # Primary Key ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Request Time
    request_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # API Key ID (Foreign Key)
    api_key_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("api_keys.id"), nullable=True
    )
    # API Key Name (Redundant field for easy querying)
    api_key_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Requested Model Name
    requested_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Target Model Name (Actually forwarded model)
    target_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Provider ID
    provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("service_providers.id"), nullable=True
    )
    # Provider Name (Redundant field)
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Retry Count
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    # Matched Provider Count
    matched_provider_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Time to First Byte (ms)
    first_byte_delay_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Total Time (ms)
    total_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Input Token Count
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Output Token Count
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Cost fields (USD, 4 decimals)
    total_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    input_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    output_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    # Price source: SupplierOverride / ModelFallback / DefaultZero
    price_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Request Headers (JSON format, sanitized)
    request_headers: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # Request Body (JSON format)
    request_body: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # Response Status Code
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Response Body
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Error Info
    error_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Trace ID
    trace_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Is Stream Request
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Indices for optimizing queries
    __table_args__ = (
        Index("idx_request_logs_time", "request_time"),
        Index("idx_request_logs_api_key", "api_key_id"),
        Index("idx_request_logs_model", "requested_model"),
        Index("idx_request_logs_provider", "provider_id"),
        Index("idx_request_logs_status", "response_status"),
    )
    
    # Relationships
    api_key: Mapped[Optional["ApiKey"]] = relationship("ApiKey", back_populates="logs")
