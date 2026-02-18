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
BILLING_MODE_PER_IMAGE = "per_image"
BILLING_MODE_INHERIT_MODEL_DEFAULT = "inherit_model_default"


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
    cached_input_cost: float = 0.0
    cached_output_cost: float = 0.0


@dataclass(frozen=True)
class ResolvedBilling:
    billing_mode: str
    price_source: str
    input_price: float
    output_price: float
    per_request_price: float | None = None
    per_image_price: float | None = None
    cache_billing_enabled: bool = False
    cached_input_price: float | None = None
    cached_output_price: float | None = None


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


def _get_tier_value(t: object, key: str):
    if isinstance(t, dict):
        return t.get(key)
    return getattr(t, key, None)


def _select_tier(
    tiers: list[object] | None, *, input_tokens: int
) -> tuple[float, float, float | None, float | None]:
    """Select tier and return (input_price, output_price, cached_input_price, cached_output_price)."""
    if not tiers:
        return 0.0, 0.0, None, None

    def tier_key(t: object) -> int:
        max_tokens = _get_tier_value(t, "max_input_tokens")
        if max_tokens is None:
            return 2**31 - 1
        try:
            return int(max_tokens)
        except Exception:
            return 2**31 - 1

    sorted_tiers = sorted(tiers, key=tier_key)
    for t in sorted_tiers:
        max_tokens = _get_tier_value(t, "max_input_tokens")
        if max_tokens is None or input_tokens <= int(max_tokens):
            cached_in = _get_tier_value(t, "cached_input_price")
            cached_out = _get_tier_value(t, "cached_output_price")
            return (
                float(_get_tier_value(t, "input_price") or 0.0),
                float(_get_tier_value(t, "output_price") or 0.0),
                float(cached_in) if cached_in is not None else None,
                float(cached_out) if cached_out is not None else None,
            )

    last = sorted_tiers[-1]
    cached_in = _get_tier_value(last, "cached_input_price")
    cached_out = _get_tier_value(last, "cached_output_price")
    return (
        float(_get_tier_value(last, "input_price") or 0.0),
        float(_get_tier_value(last, "output_price") or 0.0),
        float(cached_in) if cached_in is not None else None,
        float(cached_out) if cached_out is not None else None,
    )


def _resolve_cache_fields(
    *,
    provider_cache_billing_enabled: Optional[bool],
    provider_cached_input_price: Optional[float],
    provider_cached_output_price: Optional[float],
    model_cache_billing_enabled: Optional[bool],
    model_cached_input_price: Optional[float],
    model_cached_output_price: Optional[float],
    is_provider_source: bool,
) -> tuple[bool, float | None, float | None]:
    """Resolve cache billing fields from provider > model fallback."""
    if is_provider_source:
        enabled = bool(provider_cache_billing_enabled)
        cached_in = provider_cached_input_price
        cached_out = provider_cached_output_price
    else:
        enabled = bool(model_cache_billing_enabled)
        cached_in = model_cached_input_price
        cached_out = model_cached_output_price
    return enabled, cached_in, cached_out


def resolve_billing(
    *,
    input_tokens: int | None,
    model_input_price: Optional[float],
    model_output_price: Optional[float],
    model_billing_mode: Optional[str] = None,
    model_per_request_price: Optional[float] = None,
    model_per_image_price: Optional[float] = None,
    model_tiered_pricing: list[object] | None = None,
    model_cache_billing_enabled: Optional[bool] = None,
    model_cached_input_price: Optional[float] = None,
    model_cached_output_price: Optional[float] = None,
    provider_billing_mode: Optional[str],
    provider_per_request_price: Optional[float],
    provider_per_image_price: Optional[float] = None,
    provider_tiered_pricing: list[object] | None,
    provider_input_price: Optional[float],
    provider_output_price: Optional[float],
    provider_cache_billing_enabled: Optional[bool] = None,
    provider_cached_input_price: Optional[float] = None,
    provider_cached_output_price: Optional[float] = None,
) -> ResolvedBilling:
    """
    Resolve effective billing config.

    Priority: provider billing_mode > model billing_mode > token_flat fallback.
    Within token_flat, price resolution: provider override > model fallback > zero.
    """
    # When inherit_model_default, ignore all provider pricing
    if provider_billing_mode == BILLING_MODE_INHERIT_MODEL_DEFAULT:
        provider_input_price = None
        provider_output_price = None
        provider_per_request_price = None
        provider_per_image_price = None
        provider_tiered_pricing = None
        provider_cache_billing_enabled = None
        provider_cached_input_price = None
        provider_cached_output_price = None

    # Determine effective billing source
    if provider_billing_mode and provider_billing_mode != BILLING_MODE_INHERIT_MODEL_DEFAULT:
        mode = provider_billing_mode
        eff_per_request_price = provider_per_request_price
        eff_per_image_price = provider_per_image_price
        eff_tiered_pricing = provider_tiered_pricing
        price_source = PRICE_SOURCE_SUPPLIER_OVERRIDE
        is_provider_source = True
    elif model_billing_mode:
        mode = model_billing_mode
        eff_per_request_price = model_per_request_price
        eff_per_image_price = model_per_image_price
        eff_tiered_pricing = model_tiered_pricing
        price_source = PRICE_SOURCE_MODEL_FALLBACK
        is_provider_source = False
    else:
        mode = BILLING_MODE_TOKEN_FLAT
        eff_per_request_price = None
        eff_per_image_price = None
        eff_tiered_pricing = None
        price_source = None  # Will be determined by resolve_price
        is_provider_source = False

    if mode == BILLING_MODE_PER_REQUEST:
        return ResolvedBilling(
            billing_mode=mode,
            price_source=price_source,
            input_price=0.0,
            output_price=0.0,
            per_request_price=float(eff_per_request_price or 0.0),
        )

    if mode == BILLING_MODE_PER_IMAGE:
        return ResolvedBilling(
            billing_mode=mode,
            price_source=price_source,
            input_price=0.0,
            output_price=0.0,
            per_image_price=float(eff_per_image_price or 0.0),
        )

    # Resolve cache billing for token-based modes
    cache_enabled, cached_in_price, cached_out_price = _resolve_cache_fields(
        provider_cache_billing_enabled=provider_cache_billing_enabled,
        provider_cached_input_price=provider_cached_input_price,
        provider_cached_output_price=provider_cached_output_price,
        model_cache_billing_enabled=model_cache_billing_enabled,
        model_cached_input_price=model_cached_input_price,
        model_cached_output_price=model_cached_output_price,
        is_provider_source=is_provider_source if price_source is not None else False,
    )

    if mode == BILLING_MODE_TOKEN_TIERED:
        in_tokens = int(input_tokens or 0)
        tier_in, tier_out, tier_cached_in, tier_cached_out = _select_tier(
            eff_tiered_pricing, input_tokens=in_tokens
        )
        # For tiered, per-tier cached prices override global cached prices
        eff_cached_in = tier_cached_in if tier_cached_in is not None else cached_in_price
        eff_cached_out = tier_cached_out if tier_cached_out is not None else cached_out_price
        return ResolvedBilling(
            billing_mode=mode,
            price_source=price_source,
            input_price=float(tier_in),
            output_price=float(tier_out),
            cache_billing_enabled=cache_enabled,
            cached_input_price=eff_cached_in,
            cached_output_price=eff_cached_out,
        )

    # Default: token_flat (legacy directional pricing supported)
    resolved = resolve_price(
        model_input_price=model_input_price,
        model_output_price=model_output_price,
        provider_input_price=provider_input_price,
        provider_output_price=provider_output_price,
    )

    # For token_flat without explicit billing mode, resolve cache from either source
    if price_source is None:
        # No explicit billing mode; resolve cache from provider > model
        if provider_cache_billing_enabled:
            cache_enabled = True
            cached_in_price = provider_cached_input_price
            cached_out_price = provider_cached_output_price
        elif model_cache_billing_enabled:
            cache_enabled = True
            cached_in_price = model_cached_input_price
            cached_out_price = model_cached_output_price

    return ResolvedBilling(
        billing_mode=BILLING_MODE_TOKEN_FLAT,
        price_source=resolved.price_source,
        input_price=resolved.input_price,
        output_price=resolved.output_price,
        cache_billing_enabled=cache_enabled,
        cached_input_price=cached_in_price,
        cached_output_price=cached_out_price,
    )


def calculate_cost_from_billing(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    billing: ResolvedBilling,
    image_count: int | None = None,
    cached_input_tokens: int | None = None,
    cached_output_tokens: int | None = None,
) -> CostBreakdown:
    if billing.billing_mode == BILLING_MODE_PER_REQUEST:
        total = _q4(_to_decimal(billing.per_request_price))
        return CostBreakdown(total_cost=float(total), input_cost=0.0, output_cost=0.0)

    if billing.billing_mode == BILLING_MODE_PER_IMAGE:
        n = max(int(image_count or 1), 1)
        total = _q4(_to_decimal(billing.per_image_price) * Decimal(n))
        return CostBreakdown(total_cost=float(total), input_cost=0.0, output_cost=0.0)

    return calculate_cost(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_price=billing.input_price,
        output_price=billing.output_price,
        cache_billing_enabled=billing.cache_billing_enabled,
        cached_input_tokens=cached_input_tokens,
        cached_output_tokens=cached_output_tokens,
        cached_input_price=billing.cached_input_price,
        cached_output_price=billing.cached_output_price,
    )


def calculate_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    input_price: float,
    output_price: float,
    cache_billing_enabled: bool = False,
    cached_input_tokens: int | None = None,
    cached_output_tokens: int | None = None,
    cached_input_price: float | None = None,
    cached_output_price: float | None = None,
) -> CostBreakdown:
    in_tokens = int(input_tokens or 0)
    out_tokens = int(output_tokens or 0)

    cached_in_cost = Decimal("0")
    cached_out_cost = Decimal("0")

    if cache_billing_enabled and (cached_input_tokens or cached_output_tokens):
        # Split input tokens
        c_in = min(int(cached_input_tokens or 0), in_tokens)
        non_cached_in = max(in_tokens - c_in, 0)
        # Effective cached input price: fall back to input_price if not set
        eff_cached_in_price = cached_input_price if cached_input_price is not None else input_price
        cached_in_cost = _q4(
            (Decimal(c_in) / _ONE_MILLION) * _to_decimal(eff_cached_in_price)
        )
        regular_in_cost = _q4(
            (Decimal(non_cached_in) / _ONE_MILLION) * _to_decimal(input_price)
        )
        input_cost = _q4(regular_in_cost + cached_in_cost)

        # Split output tokens
        c_out = min(int(cached_output_tokens or 0), out_tokens)
        non_cached_out = max(out_tokens - c_out, 0)
        eff_cached_out_price = cached_output_price if cached_output_price is not None else output_price
        cached_out_cost = _q4(
            (Decimal(c_out) / _ONE_MILLION) * _to_decimal(eff_cached_out_price)
        )
        regular_out_cost = _q4(
            (Decimal(non_cached_out) / _ONE_MILLION) * _to_decimal(output_price)
        )
        output_cost = _q4(regular_out_cost + cached_out_cost)
    else:
        input_cost = _q4((Decimal(in_tokens) / _ONE_MILLION) * _to_decimal(input_price))
        output_cost = _q4((Decimal(out_tokens) / _ONE_MILLION) * _to_decimal(output_price))

    total_cost = _q4(input_cost + output_cost)

    return CostBreakdown(
        total_cost=float(total_cost),
        input_cost=float(input_cost),
        output_cost=float(output_cost),
        cached_input_cost=float(cached_in_cost),
        cached_output_cost=float(cached_out_cost),
    )
