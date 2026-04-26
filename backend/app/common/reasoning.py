"""Reasoning/thinking request parameter compatibility helpers."""

from __future__ import annotations

import copy
from typing import Any

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
    if not isinstance(output_config, dict):
        return None
    return _clean_anthropic_effort(output_config.get("effort"))


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
