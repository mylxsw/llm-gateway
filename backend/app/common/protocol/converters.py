"""
Protocol Converters Implementation

Uses llm_api_converter SDK for protocol conversion through
Intermediate Representation (IR).
"""

from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from .base import (
    Protocol,
    IRequestConverter,
    IResponseConverter,
    IStreamConverter,
    ConversionResult,
    ProtocolConversionError,
    ValidationError,
)

# Import llm_api_converter SDK
try:
    import sys
    import os
    # Add llm_api_converter to path if needed
    llm_converter_path = os.path.join(
        os.path.dirname(__file__), '..', '..', '..', '..', 'llm_api_converter'
    )
    if llm_converter_path not in sys.path:
        sys.path.insert(0, os.path.abspath(llm_converter_path))

    from api_protocol_converter import (
        convert_request,
        convert_response,
        Protocol as SDKProtocol,
    )
    from api_protocol_converter.converters import (
        OpenAIChatEncoder,
        OpenAIChatDecoder,
        OpenAIResponsesEncoder,
        OpenAIResponsesDecoder,
        AnthropicMessagesEncoder,
        AnthropicMessagesDecoder,
    )
    from api_protocol_converter.ir import (
        IRRequest,
        IRResponse,
        IRStreamEvent,
        StreamEventType,
        StopReason,
    )
    from api_protocol_converter.stream import SSEParser, SSEFormatter

    _HAS_SDK = True
except ImportError as e:
    _HAS_SDK = False
    _SDK_IMPORT_ERROR = str(e)

logger = logging.getLogger(__name__)


def _protocol_to_sdk(protocol: Protocol) -> "SDKProtocol":
    """Convert internal Protocol to SDK Protocol."""
    mapping = {
        Protocol.OPENAI: SDKProtocol.OPENAI_CHAT,
        Protocol.OPENAI_RESPONSES: SDKProtocol.OPENAI_RESPONSES,
        Protocol.ANTHROPIC: SDKProtocol.ANTHROPIC_MESSAGES,
    }
    return mapping[protocol]


def _normalize_openai_tooling_fields(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize legacy OpenAI function-calling fields to modern tool-calling fields.

    - functions -> tools
    - function_call -> tool_choice
    """
    out = copy.deepcopy(body)

    # Legacy: functions + function_call -> tools + tool_choice
    if "tools" not in out and isinstance(out.get("functions"), list):
        tools: List[Dict[str, Any]] = []
        for fn in out["functions"]:
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not isinstance(name, str) or not name:
                continue
            tool: Dict[str, Any] = {"type": "function", "function": {}}
            tool_fn = tool["function"]
            tool_fn["name"] = name
            if isinstance(fn.get("description"), str):
                tool_fn["description"] = fn.get("description")
            if isinstance(fn.get("parameters"), dict):
                tool_fn["parameters"] = fn.get("parameters")
            tools.append(tool)
        if tools:
            out["tools"] = tools

    if "tool_choice" not in out and "function_call" in out:
        fc = out.get("function_call")
        if isinstance(fc, str):
            out["tool_choice"] = fc
        elif isinstance(fc, dict):
            name = fc.get("name")
            if isinstance(name, str) and name:
                out["tool_choice"] = {"type": "function", "function": {"name": name}}

    return out


class SDKRequestConverter(IRequestConverter):
    """
    Request converter using llm_api_converter SDK.

    Uses the SDK's IR-based conversion pipeline.
    """

    def __init__(self, source: Protocol, target: Protocol):
        self._source = source
        self._target = target
        self._path_mapping = {
            Protocol.OPENAI: "/v1/chat/completions",
            Protocol.OPENAI_RESPONSES: "/v1/responses",
            Protocol.ANTHROPIC: "/v1/messages",
        }

    @property
    def source_protocol(self) -> Protocol:
        return self._source

    @property
    def target_protocol(self) -> Protocol:
        return self._target

    def get_target_path(self, source_path: str) -> str:
        return self._path_mapping.get(self._target, source_path)

    def convert(
        self,
        path: str,
        body: Dict[str, Any],
        target_model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert request using SDK."""
        if not _HAS_SDK:
            raise ProtocolConversionError(
                message=f"llm_api_converter SDK not available: {_SDK_IMPORT_ERROR}",
                code="sdk_unavailable",
            )

        options = options or {}

        try:
            # Normalize OpenAI request
            if self._source == Protocol.OPENAI:
                body = _normalize_openai_tooling_fields(body)

            # Determine if streaming
            stream = body.get("stream", False)

            # Handle max_tokens for Anthropic target
            if self._target == Protocol.ANTHROPIC:
                body = self._ensure_max_tokens(body)

            # Use SDK conversion
            sdk_source = _protocol_to_sdk(self._source)
            sdk_target = _protocol_to_sdk(self._target)

            converted = convert_request(
                sdk_source,
                sdk_target,
                body,
                stream=stream,
                options=options,
            )

            # Set target model
            converted["model"] = target_model

            # Get target path
            target_path = self.get_target_path(path)

            return ConversionResult(path=target_path, body=converted)

        except Exception as e:
            logger.error(
                "Request conversion failed: %s -> %s, error: %s",
                self._source.value,
                self._target.value,
                str(e),
            )
            raise ProtocolConversionError(
                message=f"Request conversion failed: {str(e)}",
                code="conversion_error",
                source_protocol=self._source.value,
                target_protocol=self._target.value,
            ) from e

    def _ensure_max_tokens(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure max_tokens is set for Anthropic requests."""
        if body.get("max_tokens") is None:
            body = copy.deepcopy(body)
            if body.get("max_completion_tokens") is not None:
                body["max_tokens"] = body["max_completion_tokens"]
            else:
                body["max_tokens"] = 4096
        return body


class SDKResponseConverter(IResponseConverter):
    """
    Response converter using llm_api_converter SDK.

    Uses the SDK's IR-based conversion pipeline.
    """

    def __init__(self, source: Protocol, target: Protocol):
        self._source = source
        self._target = target

    @property
    def source_protocol(self) -> Protocol:
        return self._source

    @property
    def target_protocol(self) -> Protocol:
        return self._target

    def convert(
        self,
        body: Dict[str, Any],
        target_model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Convert response using SDK."""
        if not _HAS_SDK:
            raise ProtocolConversionError(
                message=f"llm_api_converter SDK not available: {_SDK_IMPORT_ERROR}",
                code="sdk_unavailable",
            )

        options = options or {}

        try:
            sdk_source = _protocol_to_sdk(self._source)
            sdk_target = _protocol_to_sdk(self._target)

            converted = convert_response(
                sdk_source,
                sdk_target,
                body,
                options=options,
            )

            return converted

        except Exception as e:
            logger.error(
                "Response conversion failed: %s -> %s, error: %s",
                self._source.value,
                self._target.value,
                str(e),
            )
            raise ProtocolConversionError(
                message=f"Response conversion failed: {str(e)}",
                code="conversion_error",
                source_protocol=self._source.value,
                target_protocol=self._target.value,
            ) from e


class SDKStreamConverter(IStreamConverter):
    """
    Stream converter using llm_api_converter SDK.

    Handles SSE stream conversion with stateful tracking.
    """

    def __init__(self, source: Protocol, target: Protocol):
        self._source = source
        self._target = target

    @property
    def source_protocol(self) -> Protocol:
        return self._source

    @property
    def target_protocol(self) -> Protocol:
        return self._target

    async def convert(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Convert stream using SDK."""
        if not _HAS_SDK:
            raise ProtocolConversionError(
                message=f"llm_api_converter SDK not available: {_SDK_IMPORT_ERROR}",
                code="sdk_unavailable",
            )

        # Use specialized converters for each direction
        if self._source == Protocol.ANTHROPIC and self._target == Protocol.OPENAI:
            async for chunk in self._convert_anthropic_to_openai(upstream, model):
                yield chunk
        elif self._source == Protocol.OPENAI and self._target == Protocol.ANTHROPIC:
            async for chunk in self._convert_openai_to_anthropic(upstream, model):
                yield chunk
        elif self._source == Protocol.OPENAI_RESPONSES and self._target == Protocol.OPENAI:
            async for chunk in self._convert_openai_responses_to_openai(upstream, model):
                yield chunk
        elif self._source == Protocol.OPENAI and self._target == Protocol.OPENAI_RESPONSES:
            async for chunk in self._convert_openai_to_openai_responses(upstream, model):
                yield chunk
        else:
            # Generic fallback using SDK
            async for chunk in self._generic_stream_conversion(upstream, model):
                yield chunk

    async def _convert_anthropic_to_openai(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Convert Anthropic stream to OpenAI format."""
        decoder = _SSEDecoder()
        response_id: Optional[str] = None
        sent_role = False
        current_tool_id: Optional[str] = None
        current_tool_name: Optional[str] = None
        current_tool_index = 0
        done = False

        async for chunk in upstream:
            for payload in decoder.feed(chunk):
                if not payload:
                    continue
                if payload.strip() == "[DONE]":
                    continue

                try:
                    data = json.loads(payload)
                except Exception:
                    continue

                event_type = data.get("type")

                if event_type == "message_start":
                    message = data.get("message", {})
                    if isinstance(message, dict):
                        response_id = message.get("id") or response_id
                    continue

                if event_type == "content_block_start":
                    content_block = data.get("content_block", {})
                    if isinstance(content_block, dict):
                        block_type = content_block.get("type")
                        if block_type == "text":
                            text = content_block.get("text") or ""
                            if text:
                                delta: Dict[str, Any] = {"content": text}
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    self._create_openai_chunk(
                                        response_id, model, delta, None
                                    )
                                )
                        elif block_type == "tool_use":
                            current_tool_id = content_block.get("id")
                            current_tool_name = content_block.get("name")
                            if isinstance(data.get("index"), int):
                                current_tool_index = data["index"]
                            tool_args = content_block.get("input")
                            if isinstance(tool_args, dict):
                                arguments = json.dumps(tool_args, ensure_ascii=False)
                            elif isinstance(tool_args, str):
                                arguments = tool_args
                            else:
                                arguments = "{}"
                            delta = {
                                "tool_calls": [
                                    {
                                        "index": current_tool_index,
                                        "id": current_tool_id,
                                        "type": "function",
                                        "function": {
                                            "name": current_tool_name,
                                            "arguments": arguments,
                                        },
                                    }
                                ]
                            }
                            if not sent_role:
                                delta["role"] = "assistant"
                                sent_role = True
                            yield _encode_sse_json(
                                self._create_openai_chunk(
                                    response_id, model, delta, None
                                )
                            )
                    continue

                if event_type == "content_block_delta":
                    delta_obj = data.get("delta")
                    if isinstance(delta_obj, dict):
                        delta_type = delta_obj.get("type")
                        if delta_type == "text_delta":
                            text = delta_obj.get("text") or ""
                            if text:
                                delta = {"content": text}
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    self._create_openai_chunk(
                                        response_id, model, delta, None
                                    )
                                )
                        elif delta_type == "input_json_delta":
                            partial_json = delta_obj.get("partial_json") or ""
                            if partial_json:
                                delta = {
                                    "tool_calls": [
                                        {
                                            "index": current_tool_index,
                                            "id": current_tool_id,
                                            "type": "function",
                                            "function": {
                                                "name": current_tool_name,
                                                "arguments": partial_json,
                                            },
                                        }
                                    ]
                                }
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    self._create_openai_chunk(
                                        response_id, model, delta, None
                                    )
                                )
                    continue

                if event_type == "message_delta":
                    delta_dict = data.get("delta")
                    stop_reason = None
                    if isinstance(delta_dict, dict):
                        stop_reason = delta_dict.get("stop_reason")
                    finish_reason = _map_anthropic_to_openai_finish_reason(stop_reason)
                    yield _encode_sse_json(
                        self._create_openai_chunk(
                            response_id, model, {}, finish_reason
                        )
                    )
                    yield _encode_sse_data("[DONE]")
                    done = True
                    continue

                if event_type == "message_stop":
                    if not done:
                        yield _encode_sse_data("[DONE]")
                        done = True
                    continue

        if not done:
            yield _encode_sse_data("[DONE]")

    async def _convert_openai_to_anthropic(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Convert OpenAI stream to Anthropic format."""
        decoder = _SSEDecoder()
        sent_message_start = False
        sent_content_block_start = False
        sent_content_block_finish = False
        sent_message_stop = False
        holding: Optional[Dict[str, Any]] = None

        async for chunk in upstream:
            for payload in decoder.feed(chunk):
                if not payload:
                    continue
                if payload.strip() == "[DONE]":
                    continue

                if not sent_message_start:
                    sent_message_start = True
                    yield _encode_sse_json(
                        {
                            "type": "message_start",
                            "message": {
                                "id": f"msg_{uuid.uuid4().hex}",
                                "type": "message",
                                "role": "assistant",
                                "content": [],
                                "model": model,
                                "stop_reason": None,
                                "stop_sequence": None,
                                "usage": {"input_tokens": 0, "output_tokens": 0},
                            },
                        }
                    )
                if not sent_content_block_start:
                    sent_content_block_start = True
                    yield _encode_sse_json(
                        {
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {"type": "text", "text": ""},
                        }
                    )

                try:
                    data = json.loads(payload)
                except Exception:
                    continue

                choices = data.get("choices", [])
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})
                finish_reason = choice.get("finish_reason")

                if delta and delta.get("content"):
                    processed = {
                        "type": "content_block_delta",
                        "index": choice.get("index", 0),
                        "delta": {"type": "text_delta", "text": delta["content"]},
                    }
                elif finish_reason is not None:
                    processed = {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": _map_openai_to_anthropic_finish_reason(
                                finish_reason
                            )
                        },
                        "usage": {"output_tokens": 0},
                    }
                else:
                    continue

                if (
                    processed.get("type") == "message_delta"
                    and not sent_content_block_finish
                ):
                    holding = processed
                    sent_content_block_finish = True
                    yield _encode_sse_json({"type": "content_block_stop", "index": 0})
                    continue

                if holding is not None:
                    yield _encode_sse_json(holding)
                    holding = processed
                    continue

                yield _encode_sse_json(processed)

        if holding is not None:
            yield _encode_sse_json(holding)
            holding = None

        if not sent_message_stop:
            sent_message_stop = True
            yield _encode_sse_json({"type": "message_stop"})

    async def _convert_openai_responses_to_openai(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Convert OpenAI Responses stream to OpenAI Chat format."""
        # Import from openai_responses module
        from app.common.openai_responses import responses_sse_to_chat_completions_sse

        async for chunk in responses_sse_to_chat_completions_sse(
            upstream=upstream, model=model
        ):
            yield chunk

    async def _convert_openai_to_openai_responses(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Convert OpenAI Chat stream to OpenAI Responses format."""
        from app.common.openai_responses import chat_completions_sse_to_responses_sse

        async for chunk in chat_completions_sse_to_responses_sse(
            upstream=upstream, model=model
        ):
            yield chunk

    async def _generic_stream_conversion(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
    ) -> AsyncGenerator[bytes, None]:
        """Generic stream conversion using SDK (fallback)."""
        # For unsupported combinations, pass through
        async for chunk in upstream:
            yield chunk

    def _create_openai_chunk(
        self,
        response_id: Optional[str],
        model: str,
        delta: Dict[str, Any],
        finish_reason: Optional[str],
    ) -> Dict[str, Any]:
        """Create an OpenAI chat completion chunk."""
        return {
            "id": response_id or f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
        }


class _SSEDecoder:
    """SSE decoder for streaming responses."""

    def __init__(self):
        self._buffer = ""

    def feed(self, chunk: bytes) -> List[str]:
        """Feed bytes and return complete SSE data payloads."""
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            return []

        self._buffer += text
        payloads = []

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()

            if line.startswith("data:"):
                data = line[5:].strip()
                if data:
                    payloads.append(data)

        return payloads


def _encode_sse_data(payload: str) -> bytes:
    """Encode string as SSE data line."""
    return f"data: {payload}\n\n".encode("utf-8")


def _encode_sse_json(obj: Dict[str, Any]) -> bytes:
    """Encode dict as SSE JSON data line."""
    return _encode_sse_data(json.dumps(obj, ensure_ascii=False))


def _map_anthropic_to_openai_finish_reason(stop_reason: Optional[str]) -> str:
    """Map Anthropic stop reason to OpenAI finish reason."""
    if not stop_reason:
        return "stop"
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "tool_use": "tool_calls",
        "stop_sequence": "stop",
    }
    return mapping.get(stop_reason, "stop")


def _map_openai_to_anthropic_finish_reason(finish_reason: Optional[str]) -> str:
    """Map OpenAI finish reason to Anthropic stop reason."""
    if not finish_reason:
        return "end_turn"
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
    }
    return mapping.get(finish_reason, "end_turn")
