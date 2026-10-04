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

# Anthropic `thinking.type=enabled` requires an explicit `budget_tokens`
# (>= 1024 and < max_tokens). These defaults are used when the budget has to be
# synthesized from an effort level, e.g. an OpenAI `reasoning_effort` request.
ANTHROPIC_MIN_THINKING_BUDGET = 1024
_ANTHROPIC_EFFORT_BUDGETS = {
    "low": 2048,
    "medium": 8192,
    "high": 16384,
    "max": 32768,
}
_ANTHROPIC_DEFAULT_BUDGET = _ANTHROPIC_EFFORT_BUDGETS["medium"]
# Keep at least a quarter of max_tokens for the visible answer.
_ANTHROPIC_MAX_BUDGET_RATIO = 0.75
_ANTHROPIC_FORCED_TOOL_CHOICES = {"any", "tool"}

OPENAI_CHAT_API = "chat"
OPENAI_RESPONSES_API = "responses"

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
    """Read OpenAI effort from Chat (`reasoning_effort`) or Responses
    (`reasoning.effort`) style fields."""
    effort = _clean_openai_effort(body.get("reasoning_effort"))
    if effort is not None:
        return effort
    reasoning = body.get("reasoning")
    if not isinstance(reasoning, dict):
        return None
    return _clean_openai_effort(reasoning.get("effort"))


def _infer_openai_api(body: dict[str, Any]) -> str:
    if "messages" not in body and "input" in body:
        return OPENAI_RESPONSES_API
    return OPENAI_CHAT_API


def _pop_openai_reasoning_fields(out: dict[str, Any]) -> None:
    out.pop("reasoning", None)
    out.pop("reasoning_effort", None)


def _set_openai_effort(out: dict[str, Any], effort: str, api: str) -> None:
    """Write effort using the field the target OpenAI API understands.

    Chat Completions only accepts top-level `reasoning_effort`; the Responses
    API only accepts `reasoning.effort`. Other `reasoning` keys (e.g.
    `summary`) are preserved.
    """
    reasoning = out.get("reasoning")
    reasoning = dict(reasoning) if isinstance(reasoning, dict) else {}
    if api == OPENAI_RESPONSES_API:
        out.pop("reasoning_effort", None)
        reasoning["effort"] = effort
        out["reasoning"] = reasoning
        return

    out["reasoning_effort"] = effort
    reasoning.pop("effort", None)
    if reasoning:
        out["reasoning"] = reasoning
    else:
        out.pop("reasoning", None)


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
    api: str | None = None,
) -> dict[str, Any]:
    """Return a body that uses OpenAI-compatible reasoning controls only.

    `api` selects the output field: `"chat"` -> `reasoning_effort`,
    `"responses"` -> `reasoning.effort`. When omitted it is inferred from the
    body shape (`input` without `messages` means Responses).
    """
    out = copy.deepcopy(body)
    api = api or _infer_openai_api(out)
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
        _set_openai_effort(out, effort, api)

    return out


def _anthropic_thinking_budget(
    effort: str | None, max_tokens: Any
) -> int | None:
    """Pick a thinking budget that satisfies Anthropic's constraints.

    Returns None when `max_tokens` is too small to fit the minimum budget.
    """
    budget = _ANTHROPIC_EFFORT_BUDGETS.get(effort or "", _ANTHROPIC_DEFAULT_BUDGET)
    if isinstance(max_tokens, int) and not isinstance(max_tokens, bool):
        if max_tokens <= ANTHROPIC_MIN_THINKING_BUDGET:
            return None
        budget = min(budget, int(max_tokens * _ANTHROPIC_MAX_BUDGET_RATIO))
        budget = max(budget, ANTHROPIC_MIN_THINKING_BUDGET)
    return budget


def _forces_tool_use(out: dict[str, Any]) -> bool:
    tool_choice = out.get("tool_choice")
    return (
        isinstance(tool_choice, dict)
        and tool_choice.get("type") in _ANTHROPIC_FORCED_TOOL_CHOICES
    )


def _drop_sampling_incompatible_with_thinking(out: dict[str, Any]) -> None:
    """Anthropic rejects these sampling params while thinking is on."""
    temperature = out.get("temperature")
    if temperature is not None and temperature != 1:
        out.pop("temperature", None)
    out.pop("top_k", None)
    top_p = out.get("top_p")
    if isinstance(top_p, (int, float)) and top_p < 0.95:
        out.pop("top_p", None)


def normalize_reasoning_for_anthropic(
    body: dict[str, Any],
    *,
    source_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a body that uses Anthropic-compatible thinking/output_config only.

    When thinking is translated from an OpenAI effort, the request is also made
    valid for Anthropic: a `budget_tokens` is synthesized, sampling params that
    are incompatible with thinking are dropped, and thinking is not enabled when
    `tool_choice` forces tool use (Anthropic rejects that combination).
    """
    out = copy.deepcopy(body)
    source = source_body if isinstance(source_body, dict) else body

    thinking_type = _anthropic_thinking_type_from_body(source)
    anthropic_effort = _anthropic_effort_from_body(source)
    translated = False

    openai_effort = _openai_effort_from_body(source)
    if thinking_type is None and openai_effort is not None:
        thinking_type = "disabled" if openai_effort == "none" else "enabled"
        translated = True
    if anthropic_effort is None and openai_effort in _OPENAI_TO_ANTHROPIC_EFFORT:
        anthropic_effort = _OPENAI_TO_ANTHROPIC_EFFORT[openai_effort]

    _pop_openai_reasoning_fields(out)

    if translated and thinking_type == "enabled" and _forces_tool_use(out):
        thinking_type = None

    budget: int | None = None
    if thinking_type == "enabled":
        thinking = out.get("thinking")
        existing_budget = (
            thinking.get("budget_tokens") if isinstance(thinking, dict) else None
        )
        if not isinstance(existing_budget, int) or isinstance(existing_budget, bool):
            budget = _anthropic_thinking_budget(anthropic_effort, out.get("max_tokens"))
            if budget is None and translated:
                # max_tokens cannot fit any thinking budget; asking for thinking
                # would only turn the request into a 400.
                thinking_type = None

    if thinking_type is not None:
        thinking = out.get("thinking")
        if not isinstance(thinking, dict):
            thinking = {}
        thinking["type"] = thinking_type
        if thinking_type != "enabled":
            thinking.pop("budget_tokens", None)
        elif budget is not None:
            thinking["budget_tokens"] = budget
        out["thinking"] = thinking
        if translated and thinking_type == "enabled":
            _drop_sampling_incompatible_with_thinking(out)
    elif translated:
        out.pop("thinking", None)
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

    _pop_openai_reasoning_fields(out)
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

    _pop_openai_reasoning_fields(out)
    out.pop("thinking", None)
    out.pop("output_config", None)
    if thinking_enabled is not None:
        out["enable_thinking"] = thinking_enabled

    return out


def _remove_cross_protocol_reasoning_fields(out: dict[str, Any]) -> None:
    """Remove controls that belong to a different upstream protocol."""
    _pop_openai_reasoning_fields(out)
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
    elif protocol == "openai_responses":
        out["reasoning"] = {"effort": "none"}
    elif protocol == "openai":
        _set_openai_effort(out, "none", _infer_openai_api(out))
    else:
        raise ServiceError(
            message=f"Provider protocol '{supplier_protocol}' cannot disable thinking",
            code="thinking_disable_unsupported",
        )
    return out
