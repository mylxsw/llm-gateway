"""
Cost calculation helpers.

All prices are in USD per 1,000,000 tokens.
All costs are rounded to 4 decimal places (ROUND_HALF_UP).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


PRICE_SOURCE_SUPPLIER_OVERRIDE = "SupplierOverride"
PRICE_SOURCE_MODEL_FALLBACK = "ModelFallback"
PRICE_SOURCE_DEFAULT_ZERO = "DefaultZero"


_ONE_MILLION = Decimal("1000000")
_Q4 = Decimal("0.0001")


def _to_decimal(value: Optional[float]) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _q4(value: Decimal) -> Decimal:
    return value.quantize(_Q4, rounding=ROUND_HALF_UP)


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

