"""
Cost calculation helpers.

All prices are in USD per 1M tokens.
All costs are rounded to 4 decimal places (ROUND_HALF_UP).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_UP
from typing import Optional


PRICE_SOURCE_SUPPLIER_OVERRIDE = "SupplierOverride"
PRICE_SOURCE_MODEL_FALLBACK = "ModelFallback"
PRICE_SOURCE_DEFAULT_ZERO = "DefaultZero"

BILLING_MODE_TOKEN_FLAT = "token_flat"
BILLING_MODE_TOKEN_TIERED = "token_tiered"
BILLING_MODE_PER_REQUEST = "per_request"


_ONE_MILLION = Decimal("1000000")
_Q4 = Decimal("0.0001")


def _to_decimal(value: Optional[float]) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _q4(value: Decimal) -> Decimal:
    # Round-up (ceiling) to 4 decimal places for cost accounting.
    return value.quantize(_Q4, rounding=ROUND_UP)


@dataclass(frozen=True)
class ResolvedPrice:
    input_price: float
    output_price: float
    price_source: str


@dataclass(frozen=True)
class CostBreakdown:
    total_cost: float
    input_cost: float
    output_cost: float


@dataclass(frozen=True)
class ResolvedBilling:
    billing_mode: str
    price_source: str
    input_price: float
    output_price: float
    per_request_price: float | None = None


def resolve_price(
    *,
    model_input_price: Optional[float],
    model_output_price: Optional[float],
    provider_input_price: Optional[float],
    provider_output_price: Optional[float],
) -> ResolvedPrice:
    """
    Resolve effective price based on provider override > model fallback > default zero.

    Note: override can be specified per-direction; missing directions fall back to model price.
    """
    has_any_provider_override = (
        provider_input_price is not None or provider_output_price is not None
    )
    has_any_model_fallback = model_input_price is not None or model_output_price is not None

    effective_input = (
        provider_input_price
        if provider_input_price is not None
        else model_input_price
        if model_input_price is not None
        else 0.0
    )
    effective_output = (
        provider_output_price
        if provider_output_price is not None
        else model_output_price
        if model_output_price is not None
        else 0.0
    )

    if has_any_provider_override:
        source = PRICE_SOURCE_SUPPLIER_OVERRIDE
    elif has_any_model_fallback:
        source = PRICE_SOURCE_MODEL_FALLBACK
    else:
        source = PRICE_SOURCE_DEFAULT_ZERO

    return ResolvedPrice(
        input_price=float(effective_input),
        output_price=float(effective_output),
        price_source=source,
    )


def _select_tier(
    tiers: list[object] | None, *, input_tokens: int
) -> tuple[float, float]:
    if not tiers:
        return 0.0, 0.0

    def get_value(t: object, key: str):
        if isinstance(t, dict):
            return t.get(key)
        return getattr(t, key, None)

    def tier_key(t: object) -> int:
        max_tokens = get_value(t, "max_input_tokens")
        if max_tokens is None:
            return 2**31 - 1
        try:
            return int(max_tokens)
        except Exception:
            return 2**31 - 1

    sorted_tiers = sorted(tiers, key=tier_key)
    for t in sorted_tiers:
        max_tokens = get_value(t, "max_input_tokens")
        if max_tokens is None or input_tokens <= int(max_tokens):
            return (
                float(get_value(t, "input_price") or 0.0),
                float(get_value(t, "output_price") or 0.0),
            )

    last = sorted_tiers[-1]
    return (
        float(get_value(last, "input_price") or 0.0),
        float(get_value(last, "output_price") or 0.0),
    )


def resolve_billing(
    *,
    input_tokens: int | None,
    model_input_price: Optional[float],
    model_output_price: Optional[float],
    provider_billing_mode: Optional[str],
    provider_per_request_price: Optional[float],
    provider_tiered_pricing: list[object] | None,
    provider_input_price: Optional[float],
    provider_output_price: Optional[float],
) -> ResolvedBilling:
    """
    Resolve effective billing config.

    Provider billing config wins when billing_mode is set; otherwise fall back to legacy
    token pricing (provider input/output override > model fallback > default zero).
    """
    mode = provider_billing_mode or BILLING_MODE_TOKEN_FLAT

    if mode == BILLING_MODE_PER_REQUEST:
        return ResolvedBilling(
            billing_mode=mode,
            price_source=PRICE_SOURCE_SUPPLIER_OVERRIDE,
            input_price=0.0,
            output_price=0.0,
            per_request_price=float(provider_per_request_price or 0.0),
        )

    if mode == BILLING_MODE_TOKEN_TIERED:
        in_tokens = int(input_tokens or 0)
        tier_in, tier_out = _select_tier(provider_tiered_pricing, input_tokens=in_tokens)
        return ResolvedBilling(
            billing_mode=mode,
            price_source=PRICE_SOURCE_SUPPLIER_OVERRIDE,
            input_price=float(tier_in),
            output_price=float(tier_out),
        )

    # Default: token_flat (legacy directional pricing supported)
    resolved = resolve_price(
        model_input_price=model_input_price,
        model_output_price=model_output_price,
        provider_input_price=provider_input_price,
        provider_output_price=provider_output_price,
    )
    return ResolvedBilling(
        billing_mode=BILLING_MODE_TOKEN_FLAT,
        price_source=resolved.price_source,
        input_price=resolved.input_price,
        output_price=resolved.output_price,
    )


def calculate_cost_from_billing(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    billing: ResolvedBilling,
) -> CostBreakdown:
    if billing.billing_mode == BILLING_MODE_PER_REQUEST:
        total = _q4(_to_decimal(billing.per_request_price))
        return CostBreakdown(total_cost=float(total), input_cost=0.0, output_cost=0.0)

    return calculate_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_price=billing.input_price,
        output_price=billing.output_price,
    )


def calculate_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    input_price: float,
    output_price: float,
) -> CostBreakdown:
    input_tokens = int(input_tokens or 0)
    output_tokens = int(output_tokens or 0)

    input_cost = _q4((Decimal(input_tokens) / _ONE_MILLION) * _to_decimal(input_price))
    output_cost = _q4((Decimal(output_tokens) / _ONE_MILLION) * _to_decimal(output_price))
    total_cost = _q4(input_cost + output_cost)

    return CostBreakdown(
        total_cost=float(total_cost),
        input_cost=float(input_cost),
        output_cost=float(output_cost),
    )
