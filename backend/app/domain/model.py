"""
Model Mapping Domain Model

Defines Model Mapping and Model-Provider Mapping related Data Transfer Objects (DTOs).
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Literal


BillingMode = Literal["token_flat", "token_tiered", "per_request"]
SelectionStrategyType = Literal["round_robin", "cost_first", "priority"]
ModelType = Literal["chat", "speech", "transcription", "embedding", "images"]


class TokenTierPrice(BaseModel):
    """Tier price config (based on input token count)"""

    max_input_tokens: Optional[int] = Field(
        None,
        ge=1,
        description="Upper bound for input tokens (inclusive); None means no upper bound",
    )
    input_price: float = Field(..., ge=0, description="Input price ($/1M tokens)")
    output_price: float = Field(..., ge=0, description="Output price ($/1M tokens)")


class ModelMappingBase(BaseModel):
    """Model Mapping Base Model"""

    # Requested Model Name (Primary Key)
    requested_model: str = Field(
        ..., min_length=1, max_length=100, description="Requested Model Name"
    )
    # Selection Strategy: round_robin / cost_first / priority
    strategy: SelectionStrategyType = Field("round_robin", description="Selection Strategy")
    # Model Type: chat / speech / transcription / embedding / images
    model_type: ModelType = Field("chat", description="Model Type")
    # Model-level matching rules (JSON format)
    matching_rules: Optional[dict[str, Any]] = Field(
        None, description="Model Level Matching Rules"
    )


class ModelMappingCreate(ModelMappingBase):
    """Create Model Mapping Request Model"""

    # Model Capabilities Description
    capabilities: Optional[dict[str, Any]] = Field(None, description="Model Capabilities")
    # Is Active
    is_active: bool = Field(True, description="Is Active")
    # Default pricing (USD per 1,000,000 tokens)
    input_price: Optional[float] = Field(None, description="Input price ($/1M tokens)")
    output_price: Optional[float] = Field(None, description="Output price ($/1M tokens)")


class ModelMappingUpdate(BaseModel):
    """Update Model Mapping Request Model"""

    strategy: Optional[SelectionStrategyType] = None
    model_type: Optional[ModelType] = None
    matching_rules: Optional[dict[str, Any]] = None
    capabilities: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None


class ModelMapping(ModelMappingBase):
    """Model Mapping Complete Model"""

    capabilities: Optional[dict[str, Any]] = None
    is_active: bool = True
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelMappingResponse(ModelMapping):
    """Model Mapping Response Model (Includes Provider Count)"""
    
    # Associated Provider Count
    provider_count: int = Field(0, description="Associated Provider Count")
    # Associated Provider List (Returned in detail query)
    providers: Optional[list["ModelMappingProviderResponse"]] = None
    
    model_config = ConfigDict(from_attributes=True)


class ModelMatchRequest(BaseModel):
    """Model Match Request Model"""

    input_tokens: int = Field(..., ge=0, description="Input token count")
    headers: Optional[dict[str, str]] = Field(None, description="Request headers")
    api_key: Optional[str] = Field(None, description="API Key value")


class ModelMatchProviderResponse(BaseModel):
    """Model Match Provider Response Model"""

    provider_id: int = Field(..., description="Provider ID")
    provider_name: str = Field(..., description="Provider Name")
    target_model_name: str = Field(..., description="Target Model Name")
    protocol: str = Field(..., description="Provider Protocol")
    priority: int = Field(0, description="Priority")
    weight: int = Field(1, description="Weight")
    billing_mode: Optional[BillingMode] = Field(None, description="Billing mode")
    input_price: Optional[float] = Field(None, description="Input price override ($/1M tokens)")
    output_price: Optional[float] = Field(None, description="Output price override ($/1M tokens)")
    per_request_price: Optional[float] = Field(None, description="Per-request price ($)")
    tiered_pricing: Optional[list[TokenTierPrice]] = Field(
        None, description="Tiered pricing (based on input tokens)"
    )
    model_input_price: Optional[float] = Field(
        None, description="Model fallback input price ($/1M tokens)"
    )
    model_output_price: Optional[float] = Field(
        None, description="Model fallback output price ($/1M tokens)"
    )
    estimated_cost: Optional[float] = Field(
        None, description="Estimated cost based on input tokens"
    )


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
    # Provider override pricing (USD per 1,000,000 tokens)
    input_price: Optional[float] = Field(None, description="Input price override ($/1M tokens)")
    output_price: Optional[float] = Field(None, description="Output price override ($/1M tokens)")
    # Billing mode for this provider mapping
    billing_mode: BillingMode = Field("token_flat", description="Billing mode")
    # Per-request fixed price (USD), used when billing_mode == per_request
    per_request_price: Optional[float] = Field(None, ge=0, description="Per-request price ($)")
    # Tiered pricing config, used when billing_mode == token_tiered
    tiered_pricing: Optional[list[TokenTierPrice]] = Field(
        None, description="Tiered pricing (based on input tokens)"
    )

    @model_validator(mode="after")
    def _validate_billing(self) -> "ModelMappingProviderCreate":
        if self.billing_mode == "per_request" and self.per_request_price is None:
            raise ValueError("per_request_price is required when billing_mode=per_request")
        if self.billing_mode == "token_tiered" and not self.tiered_pricing:
            raise ValueError("tiered_pricing is required when billing_mode=token_tiered")
        if self.billing_mode == "token_flat":
            if self.input_price is None or self.output_price is None:
                raise ValueError("input_price and output_price are required when billing_mode=token_flat")
        return self


class ModelMappingProviderUpdate(BaseModel):
    """Update Model-Provider Mapping Request Model"""
    
    target_model_name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider_rules: Optional[dict[str, Any]] = None
    priority: Optional[int] = None
    weight: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    billing_mode: Optional[BillingMode] = None
    per_request_price: Optional[float] = Field(None, ge=0)
    tiered_pricing: Optional[list[TokenTierPrice]] = None


class ModelMappingProvider(ModelMappingProviderBase):
    """Model-Provider Mapping Complete Model"""
    
    id: int
    provider_rules: Optional[dict[str, Any]] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    billing_mode: Optional[BillingMode] = None
    per_request_price: Optional[float] = None
    tiered_pricing: Optional[list[TokenTierPrice]] = None
    priority: int = 0
    weight: int = 1
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ModelMappingProviderResponse(ModelMappingProvider):
    """Model-Provider Mapping Response Model (Includes Provider Name)"""
    
    # Provider Name
    provider_name: str = Field("", description="Provider Name")
    # Provider Protocol Type: openai or anthropic
    provider_protocol: Optional[str] = Field(None, description="Provider Protocol Type")
    
    model_config = ConfigDict(from_attributes=True)


class ModelProviderExport(BaseModel):
    """Model Provider Export Model (Uses Provider Name instead of ID)"""
    provider_name: str
    target_model_name: str
    provider_rules: Optional[dict[str, Any]] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    billing_mode: Optional[BillingMode] = None
    per_request_price: Optional[float] = None
    tiered_pricing: Optional[list[TokenTierPrice]] = None
    priority: int = 0
    weight: int = 1
    is_active: bool = True


class ModelExport(ModelMappingCreate):
    """Model Export Model"""
    providers: list[ModelProviderExport] = []


# Resolve circular reference
ModelMappingResponse.model_rebuild()
