from app.common.costs import (
    BILLING_MODE_PER_REQUEST,
    BILLING_MODE_TOKEN_TIERED,
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
