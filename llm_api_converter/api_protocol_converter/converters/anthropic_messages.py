"""
Anthropic Messages API Encoder/Decoder

Converts between Anthropic Messages API format and the Intermediate Representation.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional, Union

from ..ir import (
    ImageSourceType,
    IRContentBlock,
    IRDocumentBlock,
    IRGenerationConfig,
    IRImageBlock,
    IRMessage,
    IRRequest,
    IRResponse,
    IRStreamEvent,
    IRTextBlock,
    IRThinkingBlock,
    IRThinkingConfig,
    IRToolChoice,
    IRToolDeclaration,
    IRToolResultBlock,
    IRToolUseBlock,
    IRUsage,
    Role,
    StopReason,
    StreamEventType,
    ToolChoiceType,
)
from .exceptions import CapabilityNotSupportedError, ConversionError, ValidationError


class AnthropicMessagesDecoder:
    """Decodes Anthropic Messages API format to IR."""

    def decode_request(self, payload: Dict[str, Any]) -> IRRequest:
        """Decode an Anthropic Messages request to IR."""
        ir = IRRequest(
            model=payload.get("model", ""),
            stream=payload.get("stream", False),
        )

        # Decode messages
        messages = payload.get("messages", [])
        ir.messages = self._decode_messages(messages)

        # Decode system prompt
        system = payload.get("system")
        if system:
            if isinstance(system, str):
                ir.system = system
            elif isinstance(system, list):
                # System can be an array of text blocks
                ir.system = self._extract_text_from_blocks(system)

        # Decode generation config
        ir.generation_config = self._decode_generation_config(payload)

        # Decode tools
        if "tools" in payload:
            ir.tools = self._decode_tools(payload["tools"])

        # Decode tool choice
        if "tool_choice" in payload:
            ir.tool_choice = self._decode_tool_choice(payload["tool_choice"])

        # Decode thinking config
        if "thinking" in payload:
            ir.thinking = self._decode_thinking_config(payload["thinking"])

        # User ID from metadata
        metadata = payload.get("metadata", {})
        if "user_id" in metadata:
            ir.user = metadata["user_id"]

        # Store unsupported params
        unsupported_keys = ["service_tier"]
        for key in unsupported_keys:
            if key in payload:
                ir.unsupported_params[key] = payload[key]

        return ir

    def _decode_messages(self, messages: List[Dict[str, Any]]) -> List[IRMessage]:
        """Decode messages to IR format."""
        ir_messages = []

        for msg in messages:
            role = self._map_role(msg.get("role", "user"))
            content = msg.get("content", "")

            ir_message = IRMessage(role=role)
            ir_message.content = self._decode_content(content)

            # Check if message contains only tool_result blocks
            # If so, convert each to a separate TOOL role message
            if role == Role.USER:
                tool_results = [
                    b for b in ir_message.content if isinstance(b, IRToolResultBlock)
                ]
                other_content = [
                    b
                    for b in ir_message.content
                    if not isinstance(b, IRToolResultBlock)
                ]

                if tool_results:
                    # Add each tool result as separate TOOL message
                    for tr in tool_results:
                        tool_msg = IRMessage(role=Role.TOOL)
                        tool_msg.content = [tr]
                        ir_messages.append(tool_msg)

                    # If there's other content, add it as user message
                    if other_content:
                        ir_message.content = other_content
                        ir_messages.append(ir_message)
                    continue

            ir_messages.append(ir_message)

        return ir_messages

    def _decode_content(
        self, content: Union[str, List[Dict[str, Any]]]
    ) -> List[IRContentBlock]:
        """Decode content to IR blocks."""
        if isinstance(content, str):
            return [IRTextBlock(text=content)] if content else []

        blocks: List[IRContentBlock] = []
        for item in content:
            block = self._decode_content_block(item)
            if block:
                blocks.append(block)

        return blocks

    def _decode_content_block(self, block: Dict[str, Any]) -> Optional[IRContentBlock]:
        """Decode a single content block."""
        block_type = block.get("type", "text")

        if block_type == "text":
            return IRTextBlock(
                text=block.get("text", ""),
                citations=block.get("citations"),
            )

        elif block_type == "image":
            source = block.get("source", {})
            source_type = source.get("type", "base64")

            if source_type == "base64":
                return IRImageBlock(
                    source_type=ImageSourceType.BASE64,
                    base64_data=source.get("data"),
                    media_type=source.get("media_type"),
                )
            else:  # url
                return IRImageBlock(
                    source_type=ImageSourceType.URL,
                    url=source.get("url"),
                )

        elif block_type == "document":
            source = block.get("source", {})
            return IRDocumentBlock(
                source_type=source.get("type", "base64"),
                data=source.get("data"),
                url=source.get("url"),
                media_type=source.get("media_type"),
                title=block.get("title"),
                context=block.get("context"),
            )

        elif block_type == "tool_use":
            return IRToolUseBlock(
                id=block.get("id", ""),
                name=block.get("name", ""),
                input=block.get("input", {}),
            )

        elif block_type == "tool_result":
            content = block.get("content", "")
            return IRToolResultBlock(
                tool_use_id=block.get("tool_use_id", ""),
                content=content
                if isinstance(content, str)
                else self._decode_tool_result_content(content),
                is_error=block.get("is_error", False),
            )

        elif block_type == "thinking":
            return IRThinkingBlock(
                thinking=block.get("thinking", ""),
                signature=block.get("signature"),
            )

        elif block_type == "redacted_thinking":
            return IRThinkingBlock(
                is_redacted=True,
                redacted_data=block.get("data"),
            )

        return None

    def _decode_tool_result_content(
        self, content: List[Dict[str, Any]]
    ) -> List[IRContentBlock]:
        """Decode tool result content blocks."""
        blocks = []
        for item in content:
            if item.get("type") == "text":
                blocks.append(IRTextBlock(text=item.get("text", "")))
            elif item.get("type") == "image":
                source = item.get("source", {})
                blocks.append(
                    IRImageBlock(
                        source_type=ImageSourceType.BASE64
                        if source.get("type") == "base64"
                        else ImageSourceType.URL,
                        base64_data=source.get("data"),
                        url=source.get("url"),
                        media_type=source.get("media_type"),
                    )
                )
        return blocks

    def _decode_generation_config(self, payload: Dict[str, Any]) -> IRGenerationConfig:
        """Decode generation configuration."""
        config = IRGenerationConfig()

        if "temperature" in payload:
            config.temperature = payload["temperature"]
        if "top_p" in payload:
            config.top_p = payload["top_p"]
        if "top_k" in payload:
            config.top_k = payload["top_k"]
        if "max_tokens" in payload:
            config.max_tokens = payload["max_tokens"]
        if "stop_sequences" in payload:
            config.stop_sequences = payload["stop_sequences"]

        return config

    def _decode_tools(self, tools: List[Dict[str, Any]]) -> List[IRToolDeclaration]:
        """Decode tool declarations."""
        ir_tools = []
        for tool in tools:
            ir_tools.append(
                IRToolDeclaration(
                    name=tool.get("name", ""),
                    description=tool.get("description"),
                    parameters=tool.get("input_schema", {}),
                )
            )
        return ir_tools

    def _decode_tool_choice(self, tool_choice: Dict[str, Any]) -> IRToolChoice:
        """Decode tool choice configuration."""
        choice_type = tool_choice.get("type", "auto")

        ir_choice = IRToolChoice()

        if choice_type == "auto":
            ir_choice.type = ToolChoiceType.AUTO
        elif choice_type == "none":
            ir_choice.type = ToolChoiceType.NONE
        elif choice_type == "any":
            ir_choice.type = ToolChoiceType.ANY
        elif choice_type == "tool":
            ir_choice.type = ToolChoiceType.SPECIFIC
            ir_choice.name = tool_choice.get("name", "")

        ir_choice.disable_parallel = tool_choice.get("disable_parallel_tool_use", False)

        return ir_choice

    def _decode_thinking_config(self, thinking: Dict[str, Any]) -> IRThinkingConfig:
        """Decode thinking configuration."""
        config = IRThinkingConfig()

        if thinking.get("type") == "enabled":
            config.enabled = True
            config.budget_tokens = thinking.get("budget_tokens")
        else:
            config.enabled = False

        return config

    def _extract_text_from_blocks(self, blocks: List[Dict[str, Any]]) -> str:
        """Extract text content from blocks."""
        texts = []
        for block in blocks:
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n\n".join(texts)

    def decode_response(self, payload: Dict[str, Any]) -> IRResponse:
        """Decode an Anthropic Messages response to IR."""
        ir = IRResponse(
            id=payload.get("id", ""),
            model=payload.get("model", ""),
        )

        # Decode content blocks
        content = payload.get("content", [])
        for block in content:
            ir_block = self._decode_content_block(block)
            if ir_block:
                ir.content.append(ir_block)

        # Decode stop reason
        stop_reason = payload.get("stop_reason")
        ir.stop_reason = self._map_stop_reason(stop_reason)
        ir.stop_sequence = payload.get("stop_sequence")

        # Decode usage
        usage = payload.get("usage")
        if usage:
            ir.usage = IRUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            )

        return ir

    def decode_stream_event(
        self, event: Union[Dict[str, Any], str]
    ) -> List[IRStreamEvent]:
        """Decode a streaming event to IR events."""
        # Handle SSE text format
        if isinstance(event, str):
            event = self._parse_sse_event(event)
            if event is None:
                return []

        ir_events = []
        event_type = event.get("type", "")

        if event_type == "message_start":
            message = event.get("message", {})
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.MESSAGE_START,
                    response=IRResponse(
                        id=message.get("id", ""),
                        model=message.get("model", ""),
                    ),
                )
            )

        elif event_type == "content_block_start":
            index = event.get("index", 0)
            block = event.get("content_block", {})
            block_type = block.get("type", "text")

            if block_type == "text":
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_START,
                        index=index,
                        content_block=IRTextBlock(),
                    )
                )
            elif block_type == "tool_use":
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_START,
                        index=index,
                        content_block=IRToolUseBlock(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                        ),
                    )
                )
            elif block_type == "thinking":
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_START,
                        index=index,
                        content_block=IRThinkingBlock(),
                    )
                )

        elif event_type == "content_block_delta":
            index = event.get("index", 0)
            delta = event.get("delta", {})
            delta_type = delta.get("type", "")

            if delta_type == "text_delta":
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_DELTA,
                        index=index,
                        delta_type="text",
                        delta_text=delta.get("text", ""),
                    )
                )
            elif delta_type == "input_json_delta":
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_DELTA,
                        index=index,
                        delta_type="input_json",
                        delta_json=delta.get("partial_json", ""),
                    )
                )
            elif delta_type == "thinking_delta":
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_DELTA,
                        index=index,
                        delta_type="thinking",
                        delta_text=delta.get("thinking", ""),
                    )
                )

        elif event_type == "content_block_stop":
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.CONTENT_BLOCK_STOP,
                    index=event.get("index", 0),
                )
            )

        elif event_type == "message_delta":
            delta = event.get("delta", {})
            usage = event.get("usage", {})

            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.MESSAGE_DELTA,
                    stop_reason=self._map_stop_reason(delta.get("stop_reason")),
                    stop_sequence=delta.get("stop_sequence"),
                    usage=IRUsage(
                        output_tokens=usage.get("output_tokens", 0),
                    )
                    if usage
                    else None,
                )
            )

        elif event_type == "message_stop":
            ir_events.append(IRStreamEvent(type=StreamEventType.DONE))

        elif event_type == "ping":
            ir_events.append(IRStreamEvent(type=StreamEventType.PING))

        elif event_type == "error":
            error = event.get("error", {})
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.ERROR,
                    error_type=error.get("type", "error"),
                    error_message=error.get("message", "Unknown error"),
                )
            )

        return ir_events

    def _parse_sse_event(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse SSE event text."""
        lines = text.strip().split("\n")
        event_type = None
        data = None

        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    pass

        if data:
            if event_type:
                data["type"] = event_type
            return data
        return None

    def _map_role(self, role: str) -> Role:
        """Map Anthropic role to IR role."""
        role_map = {
            "user": Role.USER,
            "assistant": Role.ASSISTANT,
        }
        return role_map.get(role, Role.USER)

    def _map_stop_reason(self, reason: Optional[str]) -> Optional[StopReason]:
        """Map Anthropic stop reason to IR stop reason."""
        if not reason:
            return None
        reason_map = {
            "end_turn": StopReason.END_TURN,
            "max_tokens": StopReason.MAX_TOKENS,
            "stop_sequence": StopReason.STOP_SEQUENCE,
            "tool_use": StopReason.TOOL_USE,
            "refusal": StopReason.CONTENT_FILTER,
            "pause_turn": StopReason.END_TURN,
        }
        return reason_map.get(reason, StopReason.END_TURN)


class AnthropicMessagesEncoder:
    """Encodes IR to Anthropic Messages API format."""

    def encode_request(
        self, ir: IRRequest, *, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Encode IR request to Anthropic Messages format."""
        options = options or {}

        # Validate required fields
        if not ir.generation_config.max_tokens:
            raise ValidationError(
                field="max_tokens",
                message="max_tokens is required for Anthropic Messages API",
                expected="integer > 0",
            )

        payload: Dict[str, Any] = {
            "model": ir.model,
            "messages": self._encode_messages(ir.messages),
            "max_tokens": ir.generation_config.max_tokens,
        }

        # System prompt
        if ir.system:
            payload["system"] = ir.system

        # Stream
        if ir.stream:
            payload["stream"] = True

        # Generation config
        config = ir.generation_config
        if config.temperature is not None:
            # Clamp temperature to Anthropic's range (0-1)
            payload["temperature"] = min(config.temperature, 1.0)
        if config.top_p is not None:
            payload["top_p"] = config.top_p
        if config.top_k is not None:
            payload["top_k"] = config.top_k
        if config.stop_sequences:
            payload["stop_sequences"] = config.stop_sequences

        # Tools
        if ir.tools:
            payload["tools"] = self._encode_tools(ir.tools)

        # Tool choice
        if ir.tool_choice:
            payload["tool_choice"] = self._encode_tool_choice(ir.tool_choice)

        # Thinking config
        if ir.thinking and ir.thinking.enabled:
            payload["thinking"] = {
                "type": "enabled",
                "budget_tokens": ir.thinking.budget_tokens or 10000,
            }

        # User ID in metadata
        if ir.user:
            payload["metadata"] = {"user_id": ir.user}

        # Store unsupported params in metadata if option enabled
        if options.get("preserve_unsupported", False) and ir.unsupported_params:
            if "metadata" not in payload:
                payload["metadata"] = {}
            payload["metadata"]["_unsupported"] = ir.unsupported_params

        return payload

    def _encode_messages(self, messages: List[IRMessage]) -> List[Dict[str, Any]]:
        """Encode IR messages to Anthropic format."""
        result = []

        for msg in messages:
            encoded = self._encode_message(msg)
            if encoded:
                result.append(encoded)

        return result

    def _encode_message(self, msg: IRMessage) -> Optional[Dict[str, Any]]:
        """Encode a single IR message."""
        # Skip system messages (handled separately)
        if msg.role == Role.SYSTEM:
            return None

        role = self._map_role(msg.role)
        message: Dict[str, Any] = {"role": role}

        # Encode content blocks
        content = []
        for block in msg.content:
            encoded = self._encode_content_block(block)
            if encoded:
                content.append(encoded)

        # Simplify single text block to string
        if len(content) == 1 and content[0].get("type") == "text":
            message["content"] = content[0]["text"]
        elif content:
            message["content"] = content
        else:
            message["content"] = ""

        return message

    def _encode_content_block(self, block: IRContentBlock) -> Optional[Dict[str, Any]]:
        """Encode a content block to Anthropic format."""
        if isinstance(block, IRTextBlock):
            return {"type": "text", "text": block.text}

        elif isinstance(block, IRImageBlock):
            if block.source_type == ImageSourceType.BASE64:
                return {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": block.media_type or "image/png",
                        "data": block.base64_data,
                    },
                }
            else:
                return {
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": block.url,
                    },
                }

        elif isinstance(block, IRDocumentBlock):
            source: Dict[str, Any] = {"type": block.source_type}
            if block.data:
                source["data"] = block.data
            if block.url:
                source["url"] = block.url
            if block.media_type:
                source["media_type"] = block.media_type

            result: Dict[str, Any] = {"type": "document", "source": source}
            if block.title:
                result["title"] = block.title
            if block.context:
                result["context"] = block.context
            return result

        elif isinstance(block, IRToolUseBlock):
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }

        elif isinstance(block, IRToolResultBlock):
            result: Dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": block.tool_use_id,
            }

            if isinstance(block.content, str):
                result["content"] = block.content
            elif isinstance(block.content, list):
                result["content"] = [
                    self._encode_content_block(b) for b in block.content if b
                ]
            else:
                result["content"] = str(block.content)

            if block.is_error:
                result["is_error"] = True

            return result

        elif isinstance(block, IRThinkingBlock):
            if block.is_redacted:
                return {
                    "type": "redacted_thinking",
                    "data": block.redacted_data,
                }
            return {
                "type": "thinking",
                "thinking": block.thinking,
                "signature": block.signature,
            }

        return None

    def _encode_tools(self, tools: List[IRToolDeclaration]) -> List[Dict[str, Any]]:
        """Encode tool declarations."""
        result = []
        for tool in tools:
            encoded: Dict[str, Any] = {
                "name": tool.name,
                "input_schema": tool.parameters or {"type": "object", "properties": {}},
            }
            if tool.description:
                encoded["description"] = tool.description
            result.append(encoded)
        return result

    def _encode_tool_choice(self, choice: IRToolChoice) -> Dict[str, Any]:
        """Encode tool choice."""
        result: Dict[str, Any] = {}

        if choice.type == ToolChoiceType.AUTO:
            result["type"] = "auto"
        elif choice.type == ToolChoiceType.NONE:
            result["type"] = "none"
        elif choice.type == ToolChoiceType.ANY:
            result["type"] = "any"
        elif choice.type == ToolChoiceType.SPECIFIC:
            result["type"] = "tool"
            result["name"] = choice.name

        if choice.disable_parallel:
            result["disable_parallel_tool_use"] = True

        return result

    def encode_response(
        self, ir: IRResponse, *, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Encode IR response to Anthropic Messages format."""
        # Encode content blocks
        content = []
        has_tool_use = False
        for block in ir.content:
            encoded = self._encode_content_block(block)
            if encoded:
                content.append(encoded)
            # Check if any block is a tool_use block
            if isinstance(block, IRToolUseBlock):
                has_tool_use = True

        # Determine stop_reason:
        # If response contains tool_use blocks, stop_reason should be "tool_use"
        # regardless of the original stop_reason
        if has_tool_use:
            stop_reason = "tool_use"
        else:
            stop_reason = self._map_stop_reason(ir.stop_reason)

        response: Dict[str, Any] = {
            "id": ir.id if ir.id.startswith("msg_") else f"msg_{ir.id}",
            "type": "message",
            "role": "assistant",
            "model": ir.model,
            "content": content,
            "stop_reason": stop_reason,
        }

        if ir.stop_sequence:
            response["stop_sequence"] = ir.stop_sequence

        # Usage
        if ir.usage:
            response["usage"] = {
                "input_tokens": ir.usage.input_tokens,
                "output_tokens": ir.usage.output_tokens,
            }
            if ir.usage.cache_creation_tokens:
                response["usage"]["cache_creation_input_tokens"] = (
                    ir.usage.cache_creation_tokens
                )
            if ir.usage.cache_read_tokens:
                response["usage"]["cache_read_input_tokens"] = (
                    ir.usage.cache_read_tokens
                )

        return response

    def encode_stream_event(
        self, ir_event: IRStreamEvent, *, options: Optional[Dict[str, Any]] = None
    ) -> List[Union[Dict[str, Any], str]]:
        """Encode IR stream event to Anthropic Messages format."""
        options = options or {}
        output_format = options.get("output_format", "dict")

        events = []

        if ir_event.type == StreamEventType.MESSAGE_START:
            response = ir_event.response
            events.append(
                self._format_event(
                    "message_start",
                    {
                        "message": {
                            "id": response.id if response else "",
                            "type": "message",
                            "role": "assistant",
                            "model": response.model if response else "",
                            "content": [],
                            "stop_reason": None,
                            "stop_sequence": None,
                            "usage": {"input_tokens": 0, "output_tokens": 0},
                        }
                    },
                    output_format,
                )
            )

        elif ir_event.type == StreamEventType.CONTENT_BLOCK_START:
            block = ir_event.content_block
            if isinstance(block, IRTextBlock):
                content_block = {"type": "text", "text": ""}
            elif isinstance(block, IRToolUseBlock):
                content_block = {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": {},
                }
            elif isinstance(block, IRThinkingBlock):
                content_block = {"type": "thinking", "thinking": ""}
            else:
                content_block = {"type": "text", "text": ""}

            events.append(
                self._format_event(
                    "content_block_start",
                    {"index": ir_event.index, "content_block": content_block},
                    output_format,
                )
            )

        elif ir_event.type == StreamEventType.CONTENT_BLOCK_DELTA:
            if ir_event.delta_type == "text":
                delta = {"type": "text_delta", "text": ir_event.delta_text}
            elif ir_event.delta_type == "input_json":
                delta = {
                    "type": "input_json_delta",
                    "partial_json": ir_event.delta_json,
                }
            elif ir_event.delta_type == "thinking":
                delta = {"type": "thinking_delta", "thinking": ir_event.delta_text}
            else:
                delta = {"type": "text_delta", "text": ir_event.delta_text or ""}

            events.append(
                self._format_event(
                    "content_block_delta",
                    {"index": ir_event.index, "delta": delta},
                    output_format,
                )
            )

        elif ir_event.type == StreamEventType.CONTENT_BLOCK_STOP:
            events.append(
                self._format_event(
                    "content_block_stop",
                    {"index": ir_event.index},
                    output_format,
                )
            )

        elif ir_event.type == StreamEventType.MESSAGE_DELTA:
            delta: Dict[str, Any] = {}
            if ir_event.stop_reason:
                delta["stop_reason"] = self._map_stop_reason(ir_event.stop_reason)
            if ir_event.stop_sequence:
                delta["stop_sequence"] = ir_event.stop_sequence

            usage = {}
            if ir_event.usage:
                usage["output_tokens"] = ir_event.usage.output_tokens

            events.append(
                self._format_event(
                    "message_delta",
                    {"delta": delta, "usage": usage},
                    output_format,
                )
            )

        elif ir_event.type == StreamEventType.DONE:
            events.append(self._format_event("message_stop", {}, output_format))

        elif ir_event.type == StreamEventType.PING:
            events.append(self._format_event("ping", {}, output_format))

        elif ir_event.type == StreamEventType.ERROR:
            events.append(
                self._format_event(
                    "error",
                    {
                        "error": {
                            "type": ir_event.error_type or "error",
                            "message": ir_event.error_message or "Unknown error",
                        }
                    },
                    output_format,
                )
            )

        return events

    def _format_event(
        self, event_type: str, data: Dict[str, Any], output_format: str
    ) -> Union[Dict[str, Any], str]:
        """Format event based on output format."""
        data["type"] = event_type
        if output_format == "sse":
            return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        return data

    def _map_role(self, role: Role) -> str:
        """Map IR role to Anthropic role."""
        role_map = {
            Role.USER: "user",
            Role.ASSISTANT: "assistant",
            Role.TOOL: "user",  # Tool results go as user messages
        }
        return role_map.get(role, "user")

    def _map_stop_reason(self, reason: Optional[StopReason]) -> Optional[str]:
        """Map IR stop reason to Anthropic stop reason."""
        if not reason:
            return None
        reason_map = {
            StopReason.END_TURN: "end_turn",
            StopReason.MAX_TOKENS: "max_tokens",
            StopReason.STOP_SEQUENCE: "stop_sequence",
            StopReason.TOOL_USE: "tool_use",
            StopReason.CONTENT_FILTER: "refusal",
            StopReason.ERROR: "end_turn",
        }
        return reason_map.get(reason, "end_turn")
