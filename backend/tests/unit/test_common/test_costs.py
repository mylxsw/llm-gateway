from app.common.costs import calculate_cost, resolve_price


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

