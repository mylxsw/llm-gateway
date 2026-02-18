"""
Tests for model-level billing mode fallback in resolve_billing.

When a provider has no billing_mode set, the model's billing_mode
should be used as fallback. Provider billing always takes priority.
"""

import pytest
from app.common.costs import (
    BILLING_MODE_PER_IMAGE,
    BILLING_MODE_PER_REQUEST,
    BILLING_MODE_TOKEN_FLAT,
    BILLING_MODE_TOKEN_TIERED,
    PRICE_SOURCE_DEFAULT_ZERO,
    PRICE_SOURCE_MODEL_FALLBACK,
    PRICE_SOURCE_SUPPLIER_OVERRIDE,
    calculate_cost_from_billing,
    resolve_billing,
)


class TestModelLevelBillingFallback:
    """Test that model-level billing_mode works as fallback when provider has none."""

    def test_model_per_request_as_fallback(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=2.0,
            model_output_price=3.0,
            model_billing_mode="per_request",
            model_per_request_price=0.05,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_PER_REQUEST
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.per_request_price == 0.05

    def test_model_per_image_as_fallback(self):
        billing = resolve_billing(
            input_tokens=0,
            model_input_price=0.0,
            model_output_price=0.0,
            model_billing_mode="per_image",
            model_per_image_price=0.04,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_per_image_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_PER_IMAGE
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.per_image_price == 0.04
        # Verify cost calculation with image_count
        cost = calculate_cost_from_billing(
            input_tokens=0,
            output_tokens=0,
            billing=billing,
            image_count=3,
        )
        assert cost.total_cost == pytest.approx(0.12)

    def test_model_token_tiered_as_fallback(self):
        tiers = [
            {"max_input_tokens": 32768, "input_price": 1.0, "output_price": 2.0},
            {"max_input_tokens": None, "input_price": 3.0, "output_price": 4.0},
        ]
        billing = resolve_billing(
            input_tokens=50000,
            model_input_price=0.0,
            model_output_price=0.0,
            model_billing_mode="token_tiered",
            model_tiered_pricing=tiers,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_TIERED
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        # 50000 > 32768 → falls into 2nd tier
        assert billing.input_price == 3.0
        assert billing.output_price == 4.0

    def test_model_token_flat_as_fallback(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_FLAT
        # token_flat with model_billing_mode still goes through resolve_price
        assert billing.input_price == 5.0
        assert billing.output_price == 15.0


class TestProviderOverridesModelBilling:
    """Test that provider billing always takes priority over model billing."""

    def test_provider_overrides_model_per_request(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=2.0,
            model_output_price=3.0,
            model_billing_mode="per_request",
            model_per_request_price=0.10,
            provider_billing_mode="token_flat",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=10.0,
            provider_output_price=20.0,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_FLAT
        assert billing.price_source == PRICE_SOURCE_SUPPLIER_OVERRIDE
        assert billing.input_price == 10.0
        assert billing.output_price == 20.0

    def test_provider_per_image_overrides_model_per_request(self):
        billing = resolve_billing(
            input_tokens=0,
            model_input_price=0.0,
            model_output_price=0.0,
            model_billing_mode="per_request",
            model_per_request_price=0.10,
            provider_billing_mode="per_image",
            provider_per_request_price=None,
            provider_per_image_price=0.02,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_PER_IMAGE
        assert billing.price_source == PRICE_SOURCE_SUPPLIER_OVERRIDE
        assert billing.per_image_price == 0.02


class TestNoModelNoProviderBilling:
    """Test fallback when neither model nor provider set billing_mode."""

    def test_defaults_to_token_flat_with_zero(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=None,
            model_output_price=None,
            model_billing_mode=None,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_FLAT
        assert billing.price_source == PRICE_SOURCE_DEFAULT_ZERO
        assert billing.input_price == 0.0
        assert billing.output_price == 0.0

    def test_model_fallback_prices_used_without_billing_mode(self):
        """When model has input/output prices but no billing_mode, they serve as token_flat fallback."""
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode=None,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_FLAT
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.input_price == 5.0
        assert billing.output_price == 15.0


class TestBackwardCompatibility:
    """Test that existing calls without model_billing_mode params work unchanged."""

    def test_call_without_model_billing_params(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=2.0,
            model_output_price=3.0,
            provider_billing_mode="per_request",
            provider_per_request_price=0.01,
            provider_tiered_pricing=None,
            provider_input_price=9.9,
            provider_output_price=9.9,
        )
        assert billing.billing_mode == BILLING_MODE_PER_REQUEST
        assert billing.per_request_price == 0.01

    def test_call_without_model_billing_params_per_image(self):
        billing = resolve_billing(
            input_tokens=0,
            model_input_price=0.0,
            model_output_price=0.0,
            provider_billing_mode="per_image",
            provider_per_request_price=None,
            provider_per_image_price=0.05,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_PER_IMAGE
        assert billing.per_image_price == 0.05


class TestModelLevelCacheBillingFallback:
    """Test model-level cache billing fields are used as fallback."""

    def test_model_cache_billing_used_when_provider_has_none(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            model_cache_billing_enabled=True,
            model_cached_input_price=1.0,
            model_cached_output_price=3.0,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_FLAT
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.cache_billing_enabled is True
        assert billing.cached_input_price == 1.0
        assert billing.cached_output_price == 3.0

    def test_provider_cache_overrides_model_cache(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            model_cache_billing_enabled=True,
            model_cached_input_price=1.0,
            provider_billing_mode="token_flat",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=3.0,
            provider_output_price=10.0,
            provider_cache_billing_enabled=True,
            provider_cached_input_price=0.5,
        )
        assert billing.price_source == PRICE_SOURCE_SUPPLIER_OVERRIDE
        assert billing.cache_billing_enabled is True
        assert billing.cached_input_price == 0.5  # provider wins

    def test_model_tiered_cache_billing_fallback(self):
        tiers = [
            {"max_input_tokens": 32768, "input_price": 1.0, "output_price": 2.0,
             "cached_input_price": 0.5},
            {"max_input_tokens": None, "input_price": 3.0, "output_price": 4.0,
             "cached_input_price": 1.5},
        ]
        billing = resolve_billing(
            input_tokens=50000,
            model_input_price=0.0,
            model_output_price=0.0,
            model_billing_mode="token_tiered",
            model_tiered_pricing=tiers,
            model_cache_billing_enabled=True,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_TIERED
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.cache_billing_enabled is True
        assert billing.cached_input_price == 1.5  # tier 2
        assert billing.input_price == 3.0

    def test_cache_billing_with_cost_calculation(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            model_cache_billing_enabled=True,
            model_cached_input_price=1.0,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        cost = calculate_cost_from_billing(
            input_tokens=1_000_000,
            output_tokens=500_000,
            billing=billing,
            cached_input_tokens=300_000,
        )
        # non-cached input: 700k/1M * 5 = 3.5
        # cached input: 300k/1M * 1 = 0.3
        # output: 500k/1M * 15 = 7.5
        assert cost.input_cost == 3.8
        assert cost.cached_input_cost == 0.3
        assert cost.output_cost == 7.5
        assert cost.total_cost == 11.3
