"""Unit tests for billing mode validation in model domain DTOs."""

import pytest
from app.domain.model import (
    ModelMappingCreate,
    ModelMappingProviderCreate,
    ModelProviderBulkUpgradeRequest,
    TokenTierPrice,
)


# ============ ModelMappingProviderCreate ============


def test_per_image_billing_mode_requires_per_image_price():
    with pytest.raises(ValueError, match="per_image_price is required"):
        ModelMappingProviderCreate(
            requested_model="dall-e-3",
            provider_id=1,
            target_model_name="dall-e-3",
            billing_mode="per_image",
        )


def test_per_image_billing_mode_valid():
    obj = ModelMappingProviderCreate(
        requested_model="dall-e-3",
        provider_id=1,
        target_model_name="dall-e-3",
        billing_mode="per_image",
        per_image_price=0.04,
    )
    assert obj.billing_mode == "per_image"
    assert obj.per_image_price == 0.04


def test_per_image_billing_mode_zero_price_valid():
    obj = ModelMappingProviderCreate(
        requested_model="dall-e-3",
        provider_id=1,
        target_model_name="dall-e-3",
        billing_mode="per_image",
        per_image_price=0.0,
    )
    assert obj.per_image_price == 0.0


def test_per_image_billing_mode_negative_price_rejected():
    with pytest.raises(Exception):
        ModelMappingProviderCreate(
            requested_model="dall-e-3",
            provider_id=1,
            target_model_name="dall-e-3",
            billing_mode="per_image",
            per_image_price=-1.0,
        )


def test_token_flat_billing_still_works():
    obj = ModelMappingProviderCreate(
        requested_model="gpt-4",
        provider_id=1,
        target_model_name="gpt-4",
        billing_mode="token_flat",
        input_price=5.0,
        output_price=15.0,
    )
    assert obj.billing_mode == "token_flat"


def test_per_request_billing_still_works():
    obj = ModelMappingProviderCreate(
        requested_model="dall-e-3",
        provider_id=1,
        target_model_name="dall-e-3",
        billing_mode="per_request",
        per_request_price=0.04,
    )
    assert obj.billing_mode == "per_request"


# ============ ModelProviderBulkUpgradeRequest ============


def test_bulk_upgrade_per_image_requires_per_image_price():
    with pytest.raises(ValueError, match="per_image_price is required"):
        ModelProviderBulkUpgradeRequest(
            provider_id=1,
            current_target_model_name="old-model",
            new_target_model_name="new-model",
            billing_mode="per_image",
        )


def test_bulk_upgrade_per_image_valid():
    obj = ModelProviderBulkUpgradeRequest(
        provider_id=1,
        current_target_model_name="old-model",
        new_target_model_name="new-model",
        billing_mode="per_image",
        per_image_price=0.02,
    )
    assert obj.billing_mode == "per_image"
    assert obj.per_image_price == 0.02


# ============ ModelMappingCreate (model-level billing) ============


def test_model_create_no_billing_mode_allows_empty():
    """billing_mode=None is the legacy default, should not require any billing fields."""
    obj = ModelMappingCreate(requested_model="test-model")
    assert obj.billing_mode is None
    assert obj.input_price is None
    assert obj.per_request_price is None


def test_model_create_per_request_requires_price():
    with pytest.raises(ValueError, match="per_request_price is required"):
        ModelMappingCreate(
            requested_model="test-model",
            billing_mode="per_request",
        )


def test_model_create_per_request_valid():
    obj = ModelMappingCreate(
        requested_model="test-model",
        billing_mode="per_request",
        per_request_price=0.05,
    )
    assert obj.billing_mode == "per_request"
    assert obj.per_request_price == 0.05


def test_model_create_per_image_requires_price():
    with pytest.raises(ValueError, match="per_image_price is required"):
        ModelMappingCreate(
            requested_model="dall-e-3",
            billing_mode="per_image",
        )


def test_model_create_per_image_valid():
    obj = ModelMappingCreate(
        requested_model="dall-e-3",
        billing_mode="per_image",
        per_image_price=0.04,
    )
    assert obj.billing_mode == "per_image"
    assert obj.per_image_price == 0.04


def test_model_create_token_tiered_requires_tiers():
    with pytest.raises(ValueError, match="tiered_pricing is required"):
        ModelMappingCreate(
            requested_model="test-model",
            billing_mode="token_tiered",
        )


def test_model_create_token_tiered_valid():
    obj = ModelMappingCreate(
        requested_model="test-model",
        billing_mode="token_tiered",
        tiered_pricing=[
            TokenTierPrice(max_input_tokens=32768, input_price=1.0, output_price=2.0),
        ],
    )
    assert obj.billing_mode == "token_tiered"
    assert len(obj.tiered_pricing) == 1


def test_model_create_token_flat_requires_both_prices():
    with pytest.raises(ValueError, match="input_price and output_price"):
        ModelMappingCreate(
            requested_model="test-model",
            billing_mode="token_flat",
        )


def test_model_create_token_flat_valid():
    obj = ModelMappingCreate(
        requested_model="test-model",
        billing_mode="token_flat",
        input_price=5.0,
        output_price=15.0,
    )
    assert obj.billing_mode == "token_flat"
    assert obj.input_price == 5.0


def test_model_create_per_image_negative_rejected():
    with pytest.raises(Exception):
        ModelMappingCreate(
            requested_model="dall-e-3",
            billing_mode="per_image",
            per_image_price=-1.0,
        )
