"""
Streaming Response Parsing and Token Counting

Used when upstream returns SSE (text/event-stream) to extract incremental text from the stream and count output tokens.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from app.common.token_counter import get_token_counter
from app.common.usage_extractor import UsageDetails, extract_usage_details


class SSEDecoder:
    """
    Simple SSE Decoder: Splits bytes stream into event blocks and extracts data fields.

    - Uses empty line (\n\n) as event boundary
    - Supports CRLF (\r\n)
    - Only parses data: lines, ignores other fields
    """

    def __init__(self) -> None:
        self._buf = b""

    def feed(self, chunk: bytes) -> list[str]:
        """
        Append bytes and return list of parsed data payloads (one string per event).
        """
        if not chunk:
            return []

        data = (self._buf + chunk).replace(b"\r\n", b"\n")
        parts = data.split(b"\n\n")
        self._buf = parts.pop()  # Keep last incomplete event

        payloads: list[str] = []
        for event in parts:
            payload = self._extract_data_payload(event)
            if payload is not None:
                payloads.append(payload)
        return payloads

    @staticmethod
    def _extract_data_payload(event: bytes) -> Optional[str]:
        data_lines: list[bytes] = []
        for line in event.split(b"\n"):
            if not line:
                continue
            if line.startswith(b"data:"):
                value = line[5:]
                if value.startswith(b" "):
                    value = value[1:]
                data_lines.append(value)
        if not data_lines:
            return None
        try:
            return b"\n".join(data_lines).decode("utf-8", errors="ignore")
        except Exception:
            return None


@dataclass
class StreamUsageResult:
    output_text: str
    output_preview: str
    output_preview_truncated: bool
    output_tokens: int
    input_tokens: Optional[int]
    upstream_reported_output_tokens: Optional[int]
    usage_details: Optional[dict[str, Any]]


class StreamUsageAccumulator:
    """
    Extract output text and count tokens from SSE stream.

    Explanation:
    - Prioritize usage.output_tokens / usage.completion_tokens returned by upstream in stream (if present)
    - Otherwise use local tokenizer to count aggregated output text
    """

    def __init__(self, protocol: str, model: str, preview_chars: int = 4096) -> None:
        self.protocol = (protocol or "openai").lower()
        self.model = model or ""
        self.preview_chars = preview_chars

        self._decoder = SSEDecoder()
        self._token_counter = get_token_counter(self.protocol)

        self._text_parts: list[str] = []
        self._upstream_output_tokens: Optional[int] = None
        self._upstream_input_tokens: Optional[int] = None
        self._usage_details: Optional[UsageDetails] = None

    def feed(self, chunk: bytes) -> None:
        for payload in self._decoder.feed(chunk):
            self._handle_payload(payload)

    def finalize(self) -> StreamUsageResult:
        output_text = "".join(self._text_parts)
        output_tokens = (
            self._upstream_output_tokens
            if self._upstream_output_tokens is not None
            else self._token_counter.count_tokens(output_text, self.model)
        )

        if len(output_text) > self.preview_chars:
            preview = output_text[: self.preview_chars]
            truncated = True
        else:
            preview = output_text
            truncated = False

        return StreamUsageResult(
            output_text=output_text,
            output_preview=preview,
            output_preview_truncated=truncated,
            output_tokens=output_tokens,
            input_tokens=self._upstream_input_tokens,
            upstream_reported_output_tokens=self._upstream_output_tokens,
            usage_details=self._usage_details.__dict__ if self._usage_details else None,
        )

    def _handle_payload(self, payload: str) -> None:
        if not payload:
            return

        stripped = payload.strip()
        if stripped == "[DONE]":
            return

        try:
            data = json.loads(payload)
        except Exception:
            return

        if self.protocol == "anthropic":
            self._handle_anthropic_event(data)
        else:
            self._handle_openai_event(data)

    def _handle_openai_event(self, data: dict[str, Any]) -> None:
        self._update_usage_from_payload(data)

        choices = data.get("choices")
        if not isinstance(choices, list):
            return

        for choice in choices:
            if not isinstance(choice, dict):
                continue

            # Chat Completions stream: choices[].delta.content
            delta = choice.get("delta")
            if isinstance(delta, dict):
                content = delta.get("content")
                if isinstance(content, str) and content:
                    self._text_parts.append(content)

                tool_calls = delta.get("tool_calls")
                if tool_calls:
                    try:
                        self._text_parts.append(json.dumps(tool_calls, ensure_ascii=False))
                    except Exception:
                        pass

                # Legacy OpenAI streaming function calling: choices[].delta.function_call
                function_call = delta.get("function_call")
                if function_call:
                    try:
                        self._text_parts.append(json.dumps(function_call, ensure_ascii=False))
                    except Exception:
                        pass
                continue

            # Text Completions stream: choices[].text
            text = choice.get("text")
            if isinstance(text, str) and text:
                self._text_parts.append(text)

    def _handle_anthropic_event(self, data: dict[str, Any]) -> None:
        event_type = data.get("type")
        self._update_usage_from_payload(data)

        # Anthropic Messages stream: content_block_delta.delta.text
        if event_type == "content_block_delta":
            delta = data.get("delta")
            if isinstance(delta, dict):
                text = delta.get("text")
                if isinstance(text, str) and text:
                    self._text_parts.append(text)

    def _update_usage_from_payload(self, data: dict[str, Any]) -> None:
        details = extract_usage_details(data)
        if not details:
            return
        self._usage_details = details
        if details.output_tokens is not None:
            self._upstream_output_tokens = details.output_tokens
        if details.input_tokens is not None:
            self._upstream_input_tokens = details.input_tokens
            return

        # Compatible with old format: carry completion field directly
        completion = data.get("completion")
        if isinstance(completion, str) and completion:
            self._text_parts.append(completion)
