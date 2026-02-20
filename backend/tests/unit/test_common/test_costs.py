from app.common.costs import (
    BILLING_MODE_PER_IMAGE,
    BILLING_MODE_PER_REQUEST,
    BILLING_MODE_TOKEN_FLAT,
    BILLING_MODE_TOKEN_TIERED,
    ResolvedBilling,
    calculate_cost,
    calculate_cost_from_billing,
    resolve_billing,
    resolve_price,
)


def test_calculate_cost_rounds_up_to_4_decimals():
    # 1 token at $1 / 1,000,000 => 0.000001 should ceil to 0.0001
    cost = calculate_cost(input_tokens=1, output_tokens=0, input_price=1.0, output_price=0.0)
    assert cost.input_cost == 0.0001
    assert cost.output_cost == 0.0
    assert cost.total_cost == 0.0001


def test_resolve_price_provider_override_then_model_fallback_then_zero():
    # Provider override wins (per-direction), missing direction falls back to model.
    resolved = resolve_price(
        model_input_price=2.0,
        model_output_price=3.0,
        provider_input_price=5.0,
        provider_output_price=None,
    )
    assert resolved.input_price == 5.0
    assert resolved.output_price == 3.0
    assert resolved.price_source == "SupplierOverride"

    resolved = resolve_price(
        model_input_price=2.0,
        model_output_price=3.0,
        provider_input_price=None,
        provider_output_price=None,
    )
    assert resolved.input_price == 2.0
    assert resolved.output_price == 3.0
    assert resolved.price_source == "ModelFallback"

    resolved = resolve_price(
        model_input_price=None,
        model_output_price=None,
        provider_input_price=None,
        provider_output_price=None,
    )
    assert resolved.input_price == 0.0
    assert resolved.output_price == 0.0
    assert resolved.price_source == "DefaultZero"


def test_per_request_billing_overrides_token_pricing():
    billing = resolve_billing(
        input_tokens=123,
        model_input_price=2.0,
        model_output_price=3.0,
        provider_billing_mode=BILLING_MODE_PER_REQUEST,
        provider_per_request_price=0.01,
        provider_tiered_pricing=None,
        provider_input_price=9.9,
        provider_output_price=9.9,
    )
    assert billing.billing_mode == BILLING_MODE_PER_REQUEST
    assert billing.price_source == "SupplierOverride"

    cost = calculate_cost_from_billing(
        input_tokens=123,
        output_tokens=456,
        billing=billing,
    )
    assert cost.total_cost == 0.01
    assert cost.input_cost == 0.0
    assert cost.output_cost == 0.0


def test_token_tiered_billing_selects_by_input_tokens():
    tiers = [
        {"max_input_tokens": 32768, "input_price": 1.0, "output_price": 2.0},
        {"max_input_tokens": None, "input_price": 3.0, "output_price": 4.0},
    ]

    billing_small = resolve_billing(
        input_tokens=1000,
        model_input_price=0.0,
        model_output_price=0.0,
        provider_billing_mode=BILLING_MODE_TOKEN_TIERED,
        provider_per_request_price=None,
        provider_tiered_pricing=tiers,
        provider_input_price=None,
        provider_output_price=None,
    )
    cost_small = calculate_cost_from_billing(
        input_tokens=1000,
        output_tokens=500,
        billing=billing_small,
    )
    assert cost_small.input_cost == 0.001
    assert cost_small.output_cost == 0.001
    assert cost_small.total_cost == 0.002

    billing_large = resolve_billing(
        input_tokens=50000,
        model_input_price=0.0,
        model_output_price=0.0,
        provider_billing_mode=BILLING_MODE_TOKEN_TIERED,
        provider_per_request_price=None,
        provider_tiered_pricing=tiers,
        provider_input_price=None,
        provider_output_price=None,
    )
    cost_large = calculate_cost_from_billing(
        input_tokens=50000,
        output_tokens=1,
        billing=billing_large,
    )
    assert cost_large.input_cost == 0.15
    # 1 token at $4 / 1M => 0.000004 should ceil to 0.0001
    assert cost_large.output_cost == 0.0001


def test_per_image_billing_multiplies_by_image_count():
    """Per-image billing: cost = per_image_price * n"""
    billing = resolve_billing(
        input_tokens=100,
        model_input_price=2.0,
        model_output_price=3.0,
        provider_billing_mode=BILLING_MODE_PER_IMAGE,
        provider_per_request_price=None,
        provider_per_image_price=0.04,
        provider_tiered_pricing=None,
        provider_input_price=None,
        provider_output_price=None,
    )
    assert billing.billing_mode == BILLING_MODE_PER_IMAGE
    assert billing.price_source == "SupplierOverride"
    assert billing.per_image_price == 0.04

    # n=4 images
    cost = calculate_cost_from_billing(
        input_tokens=100,
        output_tokens=200,
        billing=billing,
        image_count=4,
    )
    assert cost.total_cost == 0.16  # 0.04 * 4
    assert cost.input_cost == 0.0
    assert cost.output_cost == 0.0


def test_per_image_billing_defaults_to_1_image():
    """When image_count is None, default to 1 image"""
    billing = resolve_billing(
        input_tokens=0,
        model_input_price=0.0,
        model_output_price=0.0,
        provider_billing_mode=BILLING_MODE_PER_IMAGE,
        provider_per_request_price=None,
        provider_per_image_price=0.02,
        provider_tiered_pricing=None,
        provider_input_price=None,
        provider_output_price=None,
    )

    cost = calculate_cost_from_billing(
        input_tokens=0,
        output_tokens=0,
        billing=billing,
        image_count=None,
    )
    assert cost.total_cost == 0.02  # 0.02 * 1


def test_per_image_billing_zero_price_is_free():
    """Per-image with price 0 should produce zero cost"""
    billing = resolve_billing(
        input_tokens=0,
        model_input_price=0.0,
        model_output_price=0.0,
        provider_billing_mode=BILLING_MODE_PER_IMAGE,
        provider_per_request_price=None,
        provider_per_image_price=0.0,
        provider_tiered_pricing=None,
        provider_input_price=None,
        provider_output_price=None,
    )

    cost = calculate_cost_from_billing(
        input_tokens=0,
        output_tokens=0,
        billing=billing,
        image_count=5,
    )
    assert cost.total_cost == 0.0


def test_per_image_billing_rounds_up_to_4_decimals():
    """Per-image billing should round up to 4 decimal places"""
    billing = resolve_billing(
        input_tokens=0,
        model_input_price=0.0,
        model_output_price=0.0,
        provider_billing_mode=BILLING_MODE_PER_IMAGE,
        provider_per_request_price=None,
        provider_per_image_price=0.00003,
        provider_tiered_pricing=None,
        provider_input_price=None,
        provider_output_price=None,
    )

    cost = calculate_cost_from_billing(
        input_tokens=0,
        output_tokens=0,
        billing=billing,
        image_count=1,
    )
    assert cost.total_cost == 0.0001  # 0.00003 rounds up to 0.0001


def test_per_image_billing_ignores_tokens():
    """Per-image billing ignores token counts entirely"""
    billing = resolve_billing(
        input_tokens=1000000,
        model_input_price=10.0,
        model_output_price=20.0,
        provider_billing_mode=BILLING_MODE_PER_IMAGE,
        provider_per_request_price=None,
        provider_per_image_price=0.05,
        provider_tiered_pricing=None,
        provider_input_price=5.0,
        provider_output_price=10.0,
    )

    cost = calculate_cost_from_billing(
        input_tokens=1000000,
        output_tokens=500000,
        billing=billing,
        image_count=2,
    )
    # Should be 0.05 * 2 = 0.10, not affected by tokens
    assert cost.total_cost == 0.1
    assert cost.input_cost == 0.0
    assert cost.output_cost == 0.0


# ==================== Cached Token Billing Tests ====================


class TestCacheBillingSplitsInputTokens:
    """When cache_billing_enabled, cached tokens are billed at cached_input_price."""

    def test_basic_split(self):
        """500k cached @ $1/1M + 500k regular @ $5/1M = $0.50 + $2.50 = $3.00"""
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            input_price=5.0,
            output_price=0.0,
            cache_billing_enabled=True,
            cached_input_tokens=500_000,
            cached_input_price=1.0,
        )
        # non-cached: 500000/1M * 5.0 = 2.5
        # cached: 500000/1M * 1.0 = 0.5
        # total input = 3.0
        assert cost.input_cost == 3.0
        assert cost.cached_input_cost == 0.5
        assert cost.total_cost == 3.0

    def test_all_cached(self):
        """All tokens cached"""
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            input_price=5.0,
            output_price=0.0,
            cache_billing_enabled=True,
            cached_input_tokens=1_000_000,
            cached_input_price=1.0,
        )
        assert cost.cached_input_cost == 1.0
        assert cost.input_cost == 1.0
        assert cost.total_cost == 1.0

    def test_no_cached_tokens(self):
        """Cache billing enabled but no cached tokens"""
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            input_price=5.0,
            output_price=0.0,
            cache_billing_enabled=True,
            cached_input_tokens=0,
            cached_input_price=1.0,
        )
        assert cost.input_cost == 5.0
        assert cost.cached_input_cost == 0.0
        assert cost.total_cost == 5.0

    def test_with_output_tokens(self):
        """Cached input + regular output"""
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=500_000,
            input_price=5.0,
            output_price=15.0,
            cache_billing_enabled=True,
            cached_input_tokens=600_000,
            cached_input_price=1.0,
        )
        # non-cached input: 400000/1M * 5 = 2.0
        # cached input: 600000/1M * 1 = 0.6
        # input_cost = 2.6
        # output: 500000/1M * 15 = 7.5
        assert cost.input_cost == 2.6
        assert cost.cached_input_cost == 0.6
        assert cost.output_cost == 7.5
        assert cost.total_cost == 10.1

    def test_cached_exceeds_input(self):
        """cached_input_tokens capped at input_tokens"""
        cost = calculate_cost(
            input_tokens=100_000,
            output_tokens=0,
            input_price=5.0,
            output_price=0.0,
            cache_billing_enabled=True,
            cached_input_tokens=200_000,  # More than input_tokens
            cached_input_price=1.0,
        )
        # capped: 100000 cached, 0 non-cached
        assert cost.cached_input_cost == 0.1  # 100000/1M * 1.0
        assert cost.input_cost == 0.1
        assert cost.total_cost == 0.1


class TestCacheBillingFallbackToInputPrice:
    """When cached_input_price is None, cached tokens use input_price."""

    def test_none_cached_price(self):
        """No cached price set = same as regular input price"""
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            input_price=5.0,
            output_price=0.0,
            cache_billing_enabled=True,
            cached_input_tokens=500_000,
            cached_input_price=None,  # Falls back to input_price
        )
        # All tokens at $5/1M = $5
        assert cost.input_cost == 5.0
        assert cost.cached_input_cost == 2.5
        assert cost.total_cost == 5.0


class TestCacheBillingDisabledIgnoresCachedTokens:
    """When cache_billing_enabled=False, all tokens use input_price."""

    def test_disabled(self):
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            input_price=5.0,
            output_price=0.0,
            cache_billing_enabled=False,
            cached_input_tokens=500_000,
            cached_input_price=1.0,
        )
        assert cost.input_cost == 5.0
        assert cost.cached_input_cost == 0.0
        assert cost.total_cost == 5.0

    def test_default_disabled(self):
        """Default (no cache params) = disabled"""
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=0,
            input_price=5.0,
            output_price=0.0,
        )
        assert cost.input_cost == 5.0
        assert cost.cached_input_cost == 0.0


class TestCacheBillingPerRequestIgnoresCache:
    """per_request mode never uses cache billing."""

    def test_per_request_ignores(self):
        billing = ResolvedBilling(
            billing_mode=BILLING_MODE_PER_REQUEST,
            price_source="SupplierOverride",
            input_price=0.0,
            output_price=0.0,
            per_request_price=0.01,
            cache_billing_enabled=True,
            cached_input_price=1.0,
        )
        cost = calculate_cost_from_billing(
            input_tokens=1_000_000,
            output_tokens=500_000,
            billing=billing,
            cached_input_tokens=500_000,
        )
        assert cost.total_cost == 0.01
        assert cost.cached_input_cost == 0.0


class TestCacheBillingTieredWithCachedPrices:
    """token_tiered mode with per-tier cached prices."""

    def test_tiered_with_cached_prices(self):
        tiers = [
            {
                "max_input_tokens": 32768,
                "input_price": 1.0,
                "output_price": 2.0,
                "cached_input_price": 0.5,
            },
            {
                "max_input_tokens": None,
                "input_price": 3.0,
                "output_price": 4.0,
                "cached_input_price": 1.5,
            },
        ]

        # Small input → tier 1
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=0.0,
            model_output_price=0.0,
            provider_billing_mode=BILLING_MODE_TOKEN_TIERED,
            provider_per_request_price=None,
            provider_tiered_pricing=tiers,
            provider_input_price=None,
            provider_output_price=None,
            provider_cache_billing_enabled=True,
        )
        assert billing.cache_billing_enabled is True
        assert billing.cached_input_price == 0.5

        cost = calculate_cost_from_billing(
            input_tokens=1_000_000,
            output_tokens=0,
            billing=billing,
            cached_input_tokens=600_000,
        )
        # non-cached: 400000/1M * 1.0 = 0.4
        # cached: 600000/1M * 0.5 = 0.3
        assert cost.input_cost == 0.7
        assert cost.cached_input_cost == 0.3

    def test_tiered_large_input_selects_correct_tier(self):
        tiers = [
            {
                "max_input_tokens": 32768,
                "input_price": 1.0,
                "output_price": 2.0,
                "cached_input_price": 0.5,
            },
            {
                "max_input_tokens": None,
                "input_price": 3.0,
                "output_price": 4.0,
                "cached_input_price": 1.5,
            },
        ]

        # Large input → tier 2
        billing = resolve_billing(
            input_tokens=50000,
            model_input_price=0.0,
            model_output_price=0.0,
            provider_billing_mode=BILLING_MODE_TOKEN_TIERED,
            provider_per_request_price=None,
            provider_tiered_pricing=tiers,
            provider_input_price=None,
            provider_output_price=None,
            provider_cache_billing_enabled=True,
        )
        assert billing.cached_input_price == 1.5
        assert billing.input_price == 3.0

    def test_tiered_without_per_tier_cached_prices_uses_global(self):
        """When tiers don't have cached prices, fall back to global."""
        tiers = [
            {"max_input_tokens": 32768, "input_price": 1.0, "output_price": 2.0},
            {"max_input_tokens": None, "input_price": 3.0, "output_price": 4.0},
        ]

        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=0.0,
            model_output_price=0.0,
            provider_billing_mode=BILLING_MODE_TOKEN_TIERED,
            provider_per_request_price=None,
            provider_tiered_pricing=tiers,
            provider_input_price=None,
            provider_output_price=None,
            provider_cache_billing_enabled=True,
            provider_cached_input_price=0.25,
        )
        assert billing.cached_input_price == 0.25


class TestCacheBillingOutputCachedTokens:
    """Test cached output token billing."""

    def test_cached_output_tokens(self):
        cost = calculate_cost(
            input_tokens=0,
            output_tokens=1_000_000,
            input_price=0.0,
            output_price=15.0,
            cache_billing_enabled=True,
            cached_output_tokens=400_000,
            cached_output_price=5.0,
        )
        # non-cached output: 600000/1M * 15 = 9.0
        # cached output: 400000/1M * 5 = 2.0
        assert cost.output_cost == 11.0
        assert cost.cached_output_cost == 2.0
        assert cost.total_cost == 11.0

    def test_both_cached_input_and_output(self):
        cost = calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            input_price=5.0,
            output_price=15.0,
            cache_billing_enabled=True,
            cached_input_tokens=500_000,
            cached_input_price=1.0,
            cached_output_tokens=200_000,
            cached_output_price=5.0,
        )
        # input: 500k*5/1M + 500k*1/1M = 2.5 + 0.5 = 3.0
        # output: 800k*15/1M + 200k*5/1M = 12.0 + 1.0 = 13.0
        assert cost.input_cost == 3.0
        assert cost.cached_input_cost == 0.5
        assert cost.output_cost == 13.0
        assert cost.cached_output_cost == 1.0
        assert cost.total_cost == 16.0


class TestResolveBillingCacheFieldsFromProvider:
    """Provider cache billing fields override model's."""

    def test_provider_cache_overrides_model(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            model_cache_billing_enabled=True,
            model_cached_input_price=2.0,
            provider_billing_mode="token_flat",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=3.0,
            provider_output_price=10.0,
            provider_cache_billing_enabled=True,
            provider_cached_input_price=0.5,
        )
        assert billing.cache_billing_enabled is True
        assert billing.cached_input_price == 0.5  # Provider wins
        assert billing.input_price == 3.0

    def test_provider_disables_cache_even_if_model_enables(self):
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_billing_mode="token_flat",
            model_cache_billing_enabled=True,
            model_cached_input_price=2.0,
            provider_billing_mode="token_flat",
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=3.0,
            provider_output_price=10.0,
            provider_cache_billing_enabled=False,
        )
        assert billing.cache_billing_enabled is False


class TestResolveBillingCacheFieldsFromModelFallback:
    """Model cache billing used when provider doesn't set it."""

    def test_model_cache_fallback(self):
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
        assert billing.cache_billing_enabled is True
        assert billing.cached_input_price == 1.0
        assert billing.cached_output_price == 3.0
        assert billing.price_source == "ModelFallback"

    def test_no_billing_mode_with_model_cache(self):
        """When neither has billing_mode, model cache still resolved via fallback."""
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_cache_billing_enabled=True,
            model_cached_input_price=1.0,
            provider_billing_mode=None,
            provider_per_request_price=None,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.cache_billing_enabled is True
        assert billing.cached_input_price == 1.0

    def test_per_request_always_disables_cache(self):
        """per_request mode → cache_billing_enabled is always False."""
        billing = resolve_billing(
            input_tokens=1000,
            model_input_price=5.0,
            model_output_price=15.0,
            model_cache_billing_enabled=True,
            model_cached_input_price=1.0,
            provider_billing_mode="per_request",
            provider_per_request_price=0.01,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.cache_billing_enabled is False

    def test_per_image_always_disables_cache(self):
        """per_image mode → cache_billing_enabled is always False."""
        billing = resolve_billing(
            input_tokens=0,
            model_input_price=0.0,
            model_output_price=0.0,
            model_cache_billing_enabled=True,
            model_cached_input_price=1.0,
            provider_billing_mode="per_image",
            provider_per_request_price=None,
            provider_per_image_price=0.05,
            provider_tiered_pricing=None,
            provider_input_price=None,
            provider_output_price=None,
        )
        assert billing.cache_billing_enabled is False


class TestCacheBillingRounding:
    """Test rounding behavior with cached billing."""

    def test_small_cached_amount_rounds_up(self):
        """1 cached token at $1/1M should round up to 0.0001"""
        cost = calculate_cost(
            input_tokens=2,
            output_tokens=0,
            input_price=1.0,
            output_price=0.0,
            cache_billing_enabled=True,
            cached_input_tokens=1,
            cached_input_price=1.0,
        )
        # cached: 1/1M * 1.0 = 0.000001 → 0.0001 (round up)
        # regular: 1/1M * 1.0 = 0.000001 → 0.0001 (round up)
        assert cost.cached_input_cost == 0.0001
        assert cost.input_cost == 0.0002


class TestCalculateCostFromBillingWithCache:
    """Test calculate_cost_from_billing passes cache params correctly."""

    def test_token_flat_with_cache(self):
        billing = ResolvedBilling(
            billing_mode=BILLING_MODE_TOKEN_FLAT,
            price_source="SupplierOverride",
            input_price=5.0,
            output_price=15.0,
            cache_billing_enabled=True,
            cached_input_price=1.0,
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

    def test_token_tiered_with_cache_via_billing(self):
        billing = ResolvedBilling(
            billing_mode=BILLING_MODE_TOKEN_TIERED,
            price_source="SupplierOverride",
            input_price=3.0,
            output_price=4.0,
            cache_billing_enabled=True,
            cached_input_price=1.5,
        )
        cost = calculate_cost_from_billing(
            input_tokens=1_000_000,
            output_tokens=0,
            billing=billing,
            cached_input_tokens=400_000,
        )
        # non-cached: 600k/1M * 3.0 = 1.8
        # cached: 400k/1M * 1.5 = 0.6
        assert cost.input_cost == 2.4
        assert cost.cached_input_cost == 0.6
