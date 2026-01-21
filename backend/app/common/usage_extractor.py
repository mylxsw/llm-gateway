"""
Usage Extraction Helpers

Extract token usage fields from upstream JSON responses.
This is primarily used for non-stream requests where the gateway may choose to
pass through raw bytes without parsing the JSON body.
"""

from __future__ import annotations

import json
from typing import Any, Optional


def _coerce_json_obj(body: Any) -> Any | None:
    if body is None:
        return None
    if isinstance(body, (dict, list)):
        return body

    text: str | None = None
    if isinstance(body, (bytes, bytearray)):
        text = body.decode("utf-8", errors="ignore")
    elif isinstance(body, str):
        text = body
    else:
        return None

    if not text:
        return None
    stripped = text.lstrip()
    if not stripped or stripped[0] not in "{[":
        return None

    try:
        return json.loads(stripped)
    except Exception:
        return None


def _extract_usage_dict(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None

    usage = obj.get("usage")
    if isinstance(usage, dict):
        return usage

    # Some protocols nest usage under other keys.
    for key in ("message", "delta", "response"):
        nested = obj.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("usage"), dict):
            return nested["usage"]

    return None


def extract_output_tokens(body: Any) -> Optional[int]:
    """
    Extract output token count from a response body.

    Supports (best-effort):
    - OpenAI Chat Completions: usage.completion_tokens
    - OpenAI Responses API: usage.output_tokens
    - Anthropic Messages: usage.output_tokens
    - Fallback: usage.total_tokens - usage.prompt_tokens (if available)
    """
    obj = _coerce_json_obj(body)
    usage = _extract_usage_dict(obj)
    if not usage:
        return None

    completion_tokens = usage.get("completion_tokens")
    if isinstance(completion_tokens, int):
        return completion_tokens

    output_tokens = usage.get("output_tokens")
    if isinstance(output_tokens, int):
        return output_tokens

    total_tokens = usage.get("total_tokens")
    prompt_tokens = usage.get("prompt_tokens")
    if isinstance(total_tokens, int) and isinstance(prompt_tokens, int) and total_tokens >= prompt_tokens:
        return total_tokens - prompt_tokens

    return None

