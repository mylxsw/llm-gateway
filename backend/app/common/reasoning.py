"""Reasoning/thinking request parameter compatibility helpers."""

from __future__ import annotations

import copy
from typing import Any

from app.common.errors import ServiceError
from app.common.provider_protocols import normalize_frontend_protocol

OPENAI_REASONING_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}
ANTHROPIC_THINKING_TYPES = {"enabled", "disabled", "adaptive"}
ANTHROPIC_EFFORTS = {"low", "medium", "high", "max"}

_OPENAI_TO_ANTHROPIC_EFFORT = {
    "minimal": "low",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "max",
}

_ANTHROPIC_TO_OPENAI_EFFORT = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "max": "xhigh",
}

_GEMINI_MINIMAL_THINKING_PREFIXES = (
    "gemini-3-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
)


def _clean_openai_effort(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    effort = value.strip().lower()
    return effort if effort in OPENAI_REASONING_EFFORTS else None


def _clean_anthropic_thinking_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    thinking_type = value.strip().lower()
    return thinking_type if thinking_type in ANTHROPIC_THINKING_TYPES else None


def _clean_anthropic_effort(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    effort = value.strip().lower()
    return effort if effort in ANTHROPIC_EFFORTS else None


def _openai_effort_from_body(body: dict[str, Any]) -> str | None:
    reasoning = body.get("reasoning")
    if not isinstance(reasoning, dict):
        return None
    return _clean_openai_effort(reasoning.get("effort"))


def _anthropic_thinking_type_from_body(body: dict[str, Any]) -> str | None:
    thinking = body.get("thinking")
    if not isinstance(thinking, dict):
        return None
    return _clean_anthropic_thinking_type(thinking.get("type"))


def _anthropic_effort_from_body(body: dict[str, Any]) -> str | None:
    output_config = body.get("output_config")
    if isinstance(output_config, dict):
        effort = _clean_anthropic_effort(output_config.get("effort"))
        if effort is not None:
            return effort

    thinking = body.get("thinking")
    if isinstance(thinking, dict):
        return _clean_anthropic_effort(thinking.get("effort"))

    return None


def _dashscope_thinking_enabled_from_body(body: dict[str, Any]) -> bool | None:
    enable_thinking = body.get("enable_thinking")
    return enable_thinking if isinstance(enable_thinking, bool) else None


def normalize_reasoning_for_openai(
    body: dict[str, Any],
    *,
    source_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a body that uses OpenAI-compatible `reasoning.effort` only."""
    out = copy.deepcopy(body)
    source = source_body if isinstance(source_body, dict) else body

    effort = _openai_effort_from_body(source)
    if effort is None:
        thinking_type = _anthropic_thinking_type_from_body(source)
        anthropic_effort = _anthropic_effort_from_body(source)
        if thinking_type == "disabled":
            effort = "none"
        elif anthropic_effort is not None:
            effort = _ANTHROPIC_TO_OPENAI_EFFORT[anthropic_effort]
        elif thinking_type in ("enabled", "adaptive"):
            effort = "medium"

    out.pop("thinking", None)
    out.pop("output_config", None)
    if effort is not None:
        reasoning = out.get("reasoning")
        if not isinstance(reasoning, dict):
            reasoning = {}
        reasoning["effort"] = effort
        out["reasoning"] = reasoning

    return out


def normalize_reasoning_for_anthropic(
    body: dict[str, Any],
    *,
    source_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a body that uses Anthropic-compatible thinking/output_config only."""
    out = copy.deepcopy(body)
    source = source_body if isinstance(source_body, dict) else body

    thinking_type = _anthropic_thinking_type_from_body(source)
    anthropic_effort = _anthropic_effort_from_body(source)

    openai_effort = _openai_effort_from_body(source)
    if thinking_type is None and openai_effort is not None:
        thinking_type = "disabled" if openai_effort == "none" else "enabled"
    if anthropic_effort is None and openai_effort in _OPENAI_TO_ANTHROPIC_EFFORT:
        anthropic_effort = _OPENAI_TO_ANTHROPIC_EFFORT[openai_effort]

    out.pop("reasoning", None)
    if thinking_type is not None:
        thinking = out.get("thinking")
        if not isinstance(thinking, dict):
            thinking = {}
        thinking["type"] = thinking_type
        out["thinking"] = thinking
    if anthropic_effort is not None:
        output_config = out.get("output_config")
        if not isinstance(output_config, dict):
            output_config = {}
        output_config["effort"] = anthropic_effort
        out["output_config"] = output_config

    return out


def normalize_reasoning_for_deepseek(
    body: dict[str, Any],
    *,
    source_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a DeepSeek OpenAI-compatible body using `thinking.type` only."""
    out = copy.deepcopy(body)
    source = source_body if isinstance(source_body, dict) else body

    thinking_type = _anthropic_thinking_type_from_body(source)
    if thinking_type == "adaptive":
        thinking_type = "enabled"

    openai_effort = _openai_effort_from_body(source)
    if thinking_type is None and openai_effort is not None:
        thinking_type = "disabled" if openai_effort == "none" else "enabled"

    if thinking_type is None:
        body_effort = _openai_effort_from_body(body)
        if body_effort is not None:
            thinking_type = "disabled" if body_effort == "none" else "enabled"

    out.pop("reasoning", None)
    out.pop("output_config", None)
    if thinking_type in ("enabled", "disabled"):
        thinking = out.get("thinking")
        if not isinstance(thinking, dict):
            thinking = {}
        thinking["type"] = thinking_type
        out["thinking"] = thinking

    return out


def normalize_reasoning_for_dashscope(
    body: dict[str, Any],
    *,
    source_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a Dashscope OpenAI-compatible body using `enable_thinking` only."""
    out = copy.deepcopy(body)
    source = source_body if isinstance(source_body, dict) else body

    thinking_enabled = _dashscope_thinking_enabled_from_body(source)

    thinking_type = _anthropic_thinking_type_from_body(source)
    if thinking_enabled is None and thinking_type is not None:
        thinking_enabled = thinking_type != "disabled"

    openai_effort = _openai_effort_from_body(source)
    if thinking_enabled is None and openai_effort is not None:
        thinking_enabled = openai_effort != "none"

    if thinking_enabled is None:
        body_effort = _openai_effort_from_body(body)
        if body_effort is not None:
            thinking_enabled = body_effort != "none"

    out.pop("reasoning", None)
    out.pop("thinking", None)
    out.pop("output_config", None)
    if thinking_enabled is not None:
        out["enable_thinking"] = thinking_enabled

    return out


def _remove_cross_protocol_reasoning_fields(out: dict[str, Any]) -> None:
    """Remove controls that belong to a different upstream protocol."""
    out.pop("reasoning", None)
    out.pop("thinking", None)
    out.pop("enable_thinking", None)
    output_config = out.get("output_config")
    if isinstance(output_config, dict):
        output_config = copy.deepcopy(output_config)
        output_config.pop("effort", None)
        if output_config:
            out["output_config"] = output_config
        else:
            out.pop("output_config", None)
    else:
        out.pop("output_config", None)


def _force_disable_gemini_thinking(
    out: dict[str, Any], target_model: str
) -> dict[str, Any]:
    model = (target_model or "").lower().removeprefix("models/")
    generation_config = out.get("generationConfig")
    if not isinstance(generation_config, dict):
        generation_config = {}
    else:
        generation_config = copy.deepcopy(generation_config)

    # Non-thinking models before the 2.5 family do not need an explicit
    # control. Do not silently treat the old 2.0 Thinking experimental models
    # as disabled: they have no documented off control, so they must fail
    # closed like every other unsupported thinking model.
    if model.startswith(("gemini-1.", "gemini-2.0")) and "thinking" not in model:
        generation_config.pop("thinkingConfig", None)
    elif model.startswith("gemini-2.5-flash"):
        generation_config["thinkingConfig"] = {
            "includeThoughts": False,
            "thinkingBudget": 0,
        }
    elif model.startswith(_GEMINI_MINIMAL_THINKING_PREFIXES):
        generation_config["thinkingConfig"] = {
            "includeThoughts": False,
            "thinkingLevel": "minimal",
        }
    else:
        raise ServiceError(
            message=(
                f"Provider model '{target_model}' does not support disabling "
                "Gemini thinking"
            ),
            code="thinking_disable_unsupported",
        )

    if generation_config:
        out["generationConfig"] = generation_config
    else:
        out.pop("generationConfig", None)
    return out


def force_disable_reasoning_for_supplier(
    body: dict[str, Any],
    *,
    supplier_protocol: str,
    target_model: str,
) -> dict[str, Any]:
    """Apply the supplier's strongest supported no-thinking request control.

    This is intentionally a final override. Callers must invoke it after normal
    protocol conversion, provider defaults, and request-conversion hooks.
    """
    out = copy.deepcopy(body)
    protocol = normalize_frontend_protocol(supplier_protocol)

    if protocol == "gemini":
        _remove_cross_protocol_reasoning_fields(out)
        return _force_disable_gemini_thinking(out, target_model)

    _remove_cross_protocol_reasoning_fields(out)
    if protocol in {"deepseek", "zhipu", "moonshot", "ark"}:
        out["thinking"] = {"type": "disabled"}
    elif protocol == "aliyun":
        out["enable_thinking"] = False
    elif protocol == "anthropic":
        out["thinking"] = {"type": "disabled"}
    elif protocol in {"openai", "openai_responses"}:
        out["reasoning"] = {"effort": "none"}
    else:
        raise ServiceError(
            message=f"Provider protocol '{supplier_protocol}' cannot disable thinking",
            code="thinking_disable_unsupported",
        )
    return out
