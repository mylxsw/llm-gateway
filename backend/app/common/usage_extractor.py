"""
Usage Extraction Helpers

Extract and normalize token usage fields from upstream JSON responses.
This is primarily used for non-stream requests where the gateway may choose to
pass through raw bytes without parsing the JSON body.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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


def _extract_usage_dict(obj: Any) -> tuple[dict[str, Any], str] | None:
    if not isinstance(obj, dict):
        return None

    usage = obj.get("usage")
    if isinstance(usage, dict):
        return usage, "usage"

    # Google Gemini style
    usage_meta = obj.get("usageMetadata") or obj.get("usage_metadata")
    if isinstance(usage_meta, dict):
        return usage_meta, "usage_metadata"

    # Some protocols nest usage under other keys.
    for key in ("message", "delta", "response"):
        nested = obj.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("usage"), dict):
            return nested["usage"], "usage"

    return None


@dataclass(frozen=True)
class UsageDetails:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    input_audio_tokens: Optional[int] = None
    output_audio_tokens: Optional[int] = None
    input_image_tokens: Optional[int] = None
    output_image_tokens: Optional[int] = None
    input_video_tokens: Optional[int] = None
    output_video_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    tool_tokens: Optional[int] = None
    source: str = "upstream"
    raw_usage: Optional[dict[str, Any]] = None
    extra_usage: Optional[dict[str, Any]] = None


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _normalize_usage(usage: dict[str, Any], usage_kind: str) -> UsageDetails:
    input_tokens = None
    output_tokens = None
    total_tokens = None
    cached_tokens = None
    cache_creation_input_tokens = None
    cache_read_input_tokens = None
    input_audio_tokens = None
    output_audio_tokens = None
    input_image_tokens = None
    output_image_tokens = None
    input_video_tokens = None
    output_video_tokens = None
    reasoning_tokens = None
    tool_tokens = None

    # Gemini usage metadata
    if usage_kind == "usage_metadata":
        input_tokens = _safe_int(usage.get("promptTokenCount"))
        output_tokens = _safe_int(usage.get("candidatesTokenCount"))
        total_tokens = _safe_int(usage.get("totalTokenCount"))
        cached_tokens = _safe_int(usage.get("cachedContentTokenCount"))
    else:
        input_tokens = _safe_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
        output_tokens = _safe_int(usage.get("completion_tokens") or usage.get("output_tokens"))
        total_tokens = _safe_int(usage.get("total_tokens"))

        cached_tokens = _safe_int(usage.get("cached_tokens"))
        cache_creation_input_tokens = _safe_int(usage.get("cache_creation_input_tokens"))
        cache_read_input_tokens = _safe_int(usage.get("cache_read_input_tokens"))

        input_details = (
            usage.get("input_tokens_details")
            or usage.get("prompt_tokens_details")
            or usage.get("input_token_details")
        )
        output_details = (
            usage.get("output_tokens_details")
            or usage.get("completion_tokens_details")
            or usage.get("output_token_details")
        )
        if isinstance(input_details, dict):
            cached_tokens = cached_tokens or _safe_int(input_details.get("cached_tokens"))
            input_audio_tokens = _safe_int(input_details.get("audio_tokens"))
            input_image_tokens = _safe_int(input_details.get("image_tokens"))
            input_video_tokens = _safe_int(input_details.get("video_tokens"))
            reasoning_tokens = _safe_int(input_details.get("reasoning_tokens"))
            tool_tokens = _safe_int(input_details.get("tool_tokens"))
        if isinstance(output_details, dict):
            output_audio_tokens = _safe_int(output_details.get("audio_tokens"))
            output_image_tokens = _safe_int(output_details.get("image_tokens"))
            output_video_tokens = _safe_int(output_details.get("video_tokens"))
            reasoning_tokens = reasoning_tokens or _safe_int(output_details.get("reasoning_tokens"))
            tool_tokens = tool_tokens or _safe_int(output_details.get("tool_tokens"))

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    mapped_keys = {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "cached_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "input_tokens_details",
        "prompt_tokens_details",
        "input_token_details",
        "output_tokens_details",
        "completion_tokens_details",
        "output_token_details",
        "promptTokenCount",
        "candidatesTokenCount",
        "totalTokenCount",
        "cachedContentTokenCount",
    }
    extra_usage = {k: v for k, v in usage.items() if k not in mapped_keys} or None

    return UsageDetails(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cached_tokens=cached_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        input_audio_tokens=input_audio_tokens,
        output_audio_tokens=output_audio_tokens,
        input_image_tokens=input_image_tokens,
        output_image_tokens=output_image_tokens,
        input_video_tokens=input_video_tokens,
        output_video_tokens=output_video_tokens,
        reasoning_tokens=reasoning_tokens,
        tool_tokens=tool_tokens,
        raw_usage=usage,
        extra_usage=extra_usage,
    )


def extract_usage_details(body: Any) -> Optional[UsageDetails]:
    obj = _coerce_json_obj(body)
    usage_extracted = _extract_usage_dict(obj)
    if not usage_extracted:
        return None
    usage, usage_kind = usage_extracted
    return _normalize_usage(usage, usage_kind)


def extract_output_tokens(body: Any) -> Optional[int]:
    """
    Extract output token count from a response body.

    Supports (best-effort):
    - OpenAI Chat Completions: usage.completion_tokens
    - OpenAI Responses API: usage.output_tokens
    - Anthropic Messages: usage.output_tokens
    - Fallback: usage.total_tokens - usage.prompt_tokens (if available)
    """
    details = extract_usage_details(body)
    if not details:
        return None

    if details.output_tokens is not None:
        return details.output_tokens

    if (
        details.total_tokens is not None
        and details.input_tokens is not None
        and details.total_tokens >= details.input_tokens
    ):
        return details.total_tokens - details.input_tokens

    return None
