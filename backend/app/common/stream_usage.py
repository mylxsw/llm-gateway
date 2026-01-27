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
        self._tool_calls_buffer: dict[int, dict[str, Any]] = {}
        self._upstream_output_tokens: Optional[int] = None
        self._upstream_input_tokens: Optional[int] = None
        self._usage_details: Optional[UsageDetails] = None

    def feed(self, chunk: bytes) -> None:
        for payload in self._decoder.feed(chunk):
            self._handle_payload(payload)

    def finalize(self) -> StreamUsageResult:
        if self._tool_calls_buffer:
            try:
                # Append buffered tool calls as JSON string to text parts for token counting
                # Sort by index to maintain order
                sorted_calls = sorted(
                    self._tool_calls_buffer.items(), key=lambda x: x[0]
                )
                tool_calls_list = [call for _, call in sorted_calls]
                self._text_parts.append(json.dumps(tool_calls_list, ensure_ascii=False))
            except Exception:
                pass

        output_text = "".join(self._text_parts)
        output_tokens = (
            self._upstream_output_tokens
            if self._upstream_output_tokens
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
                    for tool_call in tool_calls:
                        index = tool_call.get("index")
                        if index is None:
                            continue

                        if index not in self._tool_calls_buffer:
                            self._tool_calls_buffer[index] = {
                                "index": index,
                                "id": tool_call.get("id"),
                                "type": tool_call.get("type", "function"),
                                "function": {"name": "", "arguments": ""},
                            }

                        buffer = self._tool_calls_buffer[index]
                        if tool_call.get("id"):
                            buffer["id"] = tool_call["id"]
                        if tool_call.get("type"):
                            buffer["type"] = tool_call["type"]

                        fn = tool_call.get("function", {})
                        if fn.get("name"):
                            buffer["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            print(
                                f"DEBUG: Appending args for index {index}: '{fn['arguments']}'"
                            )
                            buffer["function"]["arguments"] += fn["arguments"]

                # Legacy OpenAI streaming function calling: choices[].delta.function_call
                function_call = delta.get("function_call")
                if function_call:
                    # Treat legacy function call as tool call at index 0
                    index = 0
                    if index not in self._tool_calls_buffer:
                        self._tool_calls_buffer[index] = {
                            "index": index,
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }

                    buffer = self._tool_calls_buffer[index]
                    if function_call.get("name"):
                        buffer["function"]["name"] += function_call["name"]
                    if function_call.get("arguments"):
                        buffer["function"]["arguments"] += function_call["arguments"]
                continue

            # Text Completions stream: choices[].text
            text = choice.get("text")
            if isinstance(text, str) and text:
                self._text_parts.append(text)

    def _handle_anthropic_event(self, data: dict[str, Any]) -> None:
        event_type = data.get("type")
        self._update_usage_from_payload(data)

        if event_type == "content_block_start":
            index = data.get("index")
            content_block = data.get("content_block")
            if isinstance(index, int) and isinstance(content_block, dict):
                if content_block.get("type") == "tool_use":
                    if index not in self._tool_calls_buffer:
                        self._tool_calls_buffer[index] = {
                            "index": index,
                            "id": content_block.get("id"),
                            "type": "function",
                            "function": {
                                "name": content_block.get("name", ""),
                                "arguments": "",
                            },
                        }

        # Anthropic Messages stream: content_block_delta.delta.text
        if event_type == "content_block_delta":
            index = data.get("index")
            delta = data.get("delta")
            if isinstance(delta, dict):
                text = delta.get("text")
                if isinstance(text, str) and text:
                    self._text_parts.append(text)

                # Handle tool arguments streaming
                if delta.get("type") == "input_json_delta" and isinstance(index, int):
                    partial_json = delta.get("partial_json")
                    if partial_json and index in self._tool_calls_buffer:
                        self._tool_calls_buffer[index]["function"]["arguments"] += (
                            partial_json
                        )

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
