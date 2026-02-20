"""
Tests for inherit_model_default billing mode in resolve_billing.

When a provider has billing_mode="inherit_model_default", it should
behave as if the provider has no billing_mode — falling back to the
model's billing configuration.
"""

import pytest
from app.common.costs import (
    BILLING_MODE_PER_IMAGE,
    BILLING_MODE_PER_REQUEST,
    BILLING_MODE_TOKEN_FLAT,
    BILLING_MODE_TOKEN_TIERED,
    PRICE_SOURCE_DEFAULT_ZERO,
    PRICE_SOURCE_MODEL_FALLBACK,
    calculate_cost_from_billing,
    resolve_billing,
)


class TestInheritModelDefaultFallback:
    """Test that inherit_model_default falls back to model billing."""

    def test_inherit_falls_back_to_model_token_flat(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=2.0,
            model_output_price=3.0,
            model_billing_mode="token_flat",
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_FLAT
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.input_price == 2.0
        assert billing.output_price == 3.0

    def test_inherit_falls_back_to_model_token_tiered(self):
        tiers = [
            {"max_input_tokens": 5000, "input_price": 1.0, "output_price": 2.0},
            {"max_input_tokens": None, "input_price": 3.0, "output_price": 4.0},
        ]
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=None,
            model_output_price=None,
            model_billing_mode="token_tiered",
            model_tiered_pricing=tiers,
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_TIERED
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.input_price == 1.0
        assert billing.output_price == 2.0

    def test_inherit_falls_back_to_model_token_tiered_second_tier(self):
        tiers = [
            {"max_input_tokens": 5000, "input_price": 1.0, "output_price": 2.0},
            {"max_input_tokens": None, "input_price": 3.0, "output_price": 4.0},
        ]
        billing = resolve_billing(
            input_tokens=10000,
            model_input_price=None,
            model_output_price=None,
            model_billing_mode="token_tiered",
            model_tiered_pricing=tiers,
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_TIERED
        assert billing.input_price == 3.0
        assert billing.output_price == 4.0

    def test_inherit_falls_back_to_model_per_request(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=0.0,
            model_output_price=0.0,
            model_billing_mode="per_request",
            model_per_request_price=0.05,
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_PER_REQUEST
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.per_request_price == 0.05

    def test_inherit_falls_back_to_model_per_image(self):
        billing = resolve_billing(
            input_tokens=0,
            model_input_price=0.0,
            model_output_price=0.0,
            model_billing_mode="per_image",
            model_per_image_price=0.04,
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_per_image_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_PER_IMAGE
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.per_image_price == 0.04

    def test_inherit_with_model_cache_billing(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            model_cache_billing_enabled=True,
            model_cached_input_price=1.0,
            model_cached_output_price=3.0,
            provider_billing_mode="inherit_model_default",
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

    def test_inherit_ignores_provider_prices(self):
        """Even if provider has input/output prices, inherit mode should use model prices."""
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=2.0,
            model_output_price=3.0,
            model_billing_mode="token_flat",
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=10.0,
            provider_output_price=20.0,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_FLAT
        assert billing.price_source == PRICE_SOURCE_MODEL_FALLBACK
        assert billing.input_price == 2.0
        assert billing.output_price == 3.0

    def test_inherit_with_no_model_billing(self):
        """When both inherit and no model billing → default to token_flat with zero."""
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=None,
            model_output_price=None,
            model_billing_mode=None,
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.billing_mode == BILLING_MODE_TOKEN_FLAT
        assert billing.price_source == PRICE_SOURCE_DEFAULT_ZERO
        assert billing.input_price == 0.0
        assert billing.output_price == 0.0


class TestInheritModelDefaultCostCalculation:
    """End-to-end cost calculation with inherit mode."""

    def test_inherit_cost_calculation_token_flat(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        cost = calculate_cost_from_billing(
            input_tokens=1_000_000,
            output_tokens=500_000,
            billing=billing,
        )
        assert cost.input_cost == 5.0
        assert cost.output_cost == 7.5
        assert cost.total_cost == 12.5

    def test_inherit_cost_calculation_per_request(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=0.0,
            model_output_price=0.0,
            model_billing_mode="per_request",
            model_per_request_price=0.01,
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        cost = calculate_cost_from_billing(
            input_tokens=1000,
            output_tokens=500,
            billing=billing,
        )
        assert cost.total_cost == 0.01

    def test_inherit_cost_calculation_per_image(self):
        billing = resolve_billing(
            input_tokens=0,
            model_input_price=0.0,
            model_output_price=0.0,
            model_billing_mode="per_image",
            model_per_image_price=0.04,
            provider_billing_mode="inherit_model_default",
            provider_per_request_price=None,
            provider_per_image_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        cost = calculate_cost_from_billing(
            input_tokens=0,
            output_tokens=0,
            billing=billing,
            image_count=3,
        )
        assert cost.total_cost == pytest.approx(0.12)

    def test_inherit_cost_calculation_with_cache(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            model_cache_billing_enabled=True,
            model_cached_input_price=1.0,
            provider_billing_mode="inherit_model_default",
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
