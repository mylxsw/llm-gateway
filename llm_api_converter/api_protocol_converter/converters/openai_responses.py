"""
OpenAI Responses API Encoder/Decoder

Converts between OpenAI Responses API format and the Intermediate Representation.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional, Union

from ..ir import (
    ImageSourceType,
    IRAudioBlock,
    IRContentBlock,
    IRGenerationConfig,
    IRImageBlock,
    IRMessage,
    IRRequest,
    IRResponse,
    IRResponseFormat,
    IRStreamEvent,
    IRTextBlock,
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
from .exceptions import ConversionError, ValidationError


class OpenAIResponsesDecoder:
    """Decodes OpenAI Responses API format to IR."""

    def decode_request(self, payload: Dict[str, Any]) -> IRRequest:
        """Decode an OpenAI Responses request to IR."""
        ir = IRRequest(
            model=payload.get("model", ""),
            stream=payload.get("stream", False),
        )

        # Decode input (can be string or array of items)
        input_data = payload.get("input", "")
        ir.messages = self._decode_input(input_data)

        # Decode instructions as system prompt
        if "instructions" in payload:
            ir.system = payload["instructions"]

        # Decode generation config
        ir.generation_config = self._decode_generation_config(payload)

        # Decode tools
        if "tools" in payload:
            ir.tools = self._decode_tools(payload["tools"])

        # Decode tool choice
        if "tool_choice" in payload:
            ir.tool_choice = self._decode_tool_choice(payload["tool_choice"])

        # Decode response format (text.format)
        if "text" in payload and "format" in payload["text"]:
            ir.response_format = self._decode_response_format(payload["text"]["format"])

        # User
        if "user" in payload:
            ir.user = payload["user"]

        # Store unsupported params
        unsupported_keys = ["store", "previous_response_id", "include", "truncation"]
        for key in unsupported_keys:
            if key in payload:
                ir.unsupported_params[key] = payload[key]

        return ir

    def _decode_input(
        self, input_data: Union[str, List[Dict[str, Any]]]
    ) -> List[IRMessage]:
        """Decode input to IR messages."""
        if isinstance(input_data, str):
            # Simple string input becomes a user message
            return [
                IRMessage(
                    role=Role.USER,
                    content=[IRTextBlock(text=input_data)],
                )
            ]

        messages = []
        for item in input_data:
            message = self._decode_item(item)
            if message:
                messages.append(message)
        return messages

    def _decode_item(self, item: Dict[str, Any]) -> Optional[IRMessage]:
        """Decode a single input item to IR message."""
        item_type = item.get("type", "message")

        if item_type == "message":
            role = self._map_role(item.get("role", "user"))
            content = self._decode_content(item.get("content", []))
            return IRMessage(role=role, content=content)

        elif item_type == "function_call":
            # Function call from previous response
            return IRMessage(
                role=Role.ASSISTANT,
                content=[
                    IRToolUseBlock(
                        id=item.get("call_id", item.get("id", "")),
                        name=item.get("name", ""),
                        input=self._parse_json_safely(item.get("arguments", "{}")),
                    )
                ],
            )

        elif item_type == "function_call_output":
            # Function result
            return IRMessage(
                role=Role.TOOL,
                content=[
                    IRToolResultBlock(
                        tool_use_id=item.get("call_id", ""),
                        content=item.get("output", ""),
                    )
                ],
            )

        return None

    def _decode_content(
        self, content: Union[str, List[Dict[str, Any]]]
    ) -> List[IRContentBlock]:
        """Decode content to IR blocks."""
        if isinstance(content, str):
            return [IRTextBlock(text=content)]

        blocks = []
        for item in content:
            if isinstance(item, str):
                blocks.append(IRTextBlock(text=item))
            elif isinstance(item, dict):
                block = self._decode_content_block(item)
                if block:
                    blocks.append(block)
        return blocks

    def _decode_content_block(self, block: Dict[str, Any]) -> Optional[IRContentBlock]:
        """Decode a single content block."""
        block_type = block.get("type", "text")

        # Handle text content blocks (text, output_text, input_text)
        if block_type in ("text", "output_text", "input_text"):
            return IRTextBlock(text=block.get("text", ""))

        # Handle image content blocks (image_url, input_image)
        elif block_type == "image_url":
            url = block.get("image_url", "")
            if isinstance(url, dict):
                url = url.get("url", "")

            if url.startswith("data:"):
                media_type, base64_data = self._parse_data_url(url)
                return IRImageBlock(
                    source_type=ImageSourceType.BASE64,
                    base64_data=base64_data,
                    media_type=media_type,
                )
            else:
                return IRImageBlock(
                    source_type=ImageSourceType.URL,
                    url=url,
                )

        elif block_type == "input_image":
            # input_image can have image_url (string URL) or detail
            url = block.get("image_url", "")
            if isinstance(url, dict):
                url = url.get("url", "")

            if url.startswith("data:"):
                media_type, base64_data = self._parse_data_url(url)
                return IRImageBlock(
                    source_type=ImageSourceType.BASE64,
                    base64_data=base64_data,
                    media_type=media_type,
                )
            else:
                return IRImageBlock(
                    source_type=ImageSourceType.URL,
                    url=url,
                )

        elif block_type == "input_audio":
            audio_data = block.get("input_audio", {})
            return IRAudioBlock(
                source_type="base64",
                data=audio_data.get("data"),
                format=audio_data.get("format"),
            )

        return None

    def _decode_generation_config(self, payload: Dict[str, Any]) -> IRGenerationConfig:
        """Decode generation configuration."""
        config = IRGenerationConfig()

        if "temperature" in payload:
            config.temperature = payload["temperature"]
        if "top_p" in payload:
            config.top_p = payload["top_p"]
        if "max_output_tokens" in payload:
            config.max_tokens = payload["max_output_tokens"]
        if "stop" in payload:
            config.stop_sequences = payload["stop"]
        if "seed" in payload:
            config.seed = payload["seed"]

        return config

    def _decode_tools(self, tools: List[Dict[str, Any]]) -> List[IRToolDeclaration]:
        """Decode tool declarations."""
        ir_tools = []
        for tool in tools:
            tool_type = tool.get("type", "function")
            if tool_type == "function":
                ir_tools.append(
                    IRToolDeclaration(
                        name=tool.get("name", ""),
                        description=tool.get("description"),
                        parameters=tool.get("parameters", {}),
                        strict=tool.get("strict", False),
                    )
                )
            # Skip built-in tools (web_search, file_search, etc.) for now
        return ir_tools

    def _decode_tool_choice(self, tool_choice: Dict[str, Any]) -> IRToolChoice:
        """Decode tool choice configuration."""
        choice_type = tool_choice.get("type", "auto")

        if choice_type == "auto":
            return IRToolChoice(type=ToolChoiceType.AUTO)
        elif choice_type == "none":
            return IRToolChoice(type=ToolChoiceType.NONE)
        elif choice_type == "function":
            return IRToolChoice(
                type=ToolChoiceType.SPECIFIC,
                name=tool_choice.get("name", ""),
            )

        return IRToolChoice(type=ToolChoiceType.AUTO)

    def _decode_response_format(self, fmt: Dict[str, Any]) -> IRResponseFormat:
        """Decode response format configuration."""
        fmt_type = fmt.get("type", "text")
        ir_format = IRResponseFormat(type=fmt_type)

        if fmt_type == "json_schema":
            ir_format.json_schema = fmt.get("schema")
            ir_format.schema_name = fmt.get("name")
            ir_format.strict = fmt.get("strict", False)

        return ir_format

    def decode_response(self, payload: Dict[str, Any]) -> IRResponse:
        """Decode an OpenAI Responses response to IR."""
        ir = IRResponse(
            id=payload.get("id", ""),
            model=payload.get("model", ""),
            created=payload.get("created_at"),
        )

        # Decode output items
        output = payload.get("output", [])
        for item in output:
            blocks = self._decode_output_item(item)
            ir.content.extend(blocks)

        # Map status to stop reason
        status = payload.get("status", "completed")
        ir.stop_reason = self._map_status(status)

        # Decode usage
        usage = payload.get("usage")
        if usage:
            ir.usage = IRUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens"),
            )
            # Decode detailed usage
            input_details = usage.get("input_tokens_details", {})
            if input_details:
                ir.usage.cache_read_tokens = input_details.get("cached_tokens", 0)
            output_details = usage.get("output_tokens_details", {})
            if output_details:
                ir.usage.reasoning_tokens = output_details.get("reasoning_tokens", 0)

        return ir

    def _decode_output_item(self, item: Dict[str, Any]) -> List[IRContentBlock]:
        """Decode an output item to IR content blocks."""
        item_type = item.get("type", "message")
        blocks: List[IRContentBlock] = []

        if item_type == "message":
            content = item.get("content", [])
            for c in content:
                if isinstance(c, dict):
                    c_type = c.get("type", "text")
                    if c_type in ("text", "output_text"):
                        blocks.append(IRTextBlock(text=c.get("text", "")))

        elif item_type == "function_call":
            blocks.append(
                IRToolUseBlock(
                    id=item.get("call_id", item.get("id", "")),
                    name=item.get("name", ""),
                    input=self._parse_json_safely(item.get("arguments", "{}")),
                )
            )

        elif item_type == "reasoning":
            # Reasoning items - we could create a thinking block
            summary = item.get("summary", [])
            for s in summary:
                if s.get("type") == "summary_text":
                    blocks.append(IRTextBlock(text=s.get("text", "")))

        return blocks

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

        if event_type == "response.created":
            response_data = event.get("response", {})
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.MESSAGE_START,
                    response=IRResponse(
                        id=response_data.get("id", ""),
                        model=response_data.get("model", ""),
                        created=response_data.get("created_at"),
                    ),
                )
            )

        elif event_type == "response.output_item.added":
            item = event.get("item", {})
            item_type = item.get("type", "")

            if item_type == "message":
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_START,
                        index=event.get("output_index", 0),
                        content_block=IRTextBlock(),
                    )
                )
            elif item_type == "function_call":
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.CONTENT_BLOCK_START,
                        index=event.get("output_index", 0),
                        content_block=IRToolUseBlock(
                            id=item.get("call_id", item.get("id", "")),
                            name=item.get("name", ""),
                        ),
                    )
                )

        elif event_type in ("response.text.delta", "response.output_text.delta"):
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.CONTENT_BLOCK_DELTA,
                    index=event.get("output_index", 0),
                    delta_type="text",
                    delta_text=event.get("delta", ""),
                )
            )

        elif event_type == "response.function_call_arguments.delta":
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.CONTENT_BLOCK_DELTA,
                    index=event.get("output_index", 0),
                    delta_type="input_json",
                    delta_json=event.get("delta", ""),
                )
            )

        elif event_type == "response.output_item.done":
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.CONTENT_BLOCK_STOP,
                    index=event.get("output_index", 0),
                )
            )

        elif event_type == "response.done":
            response_data = event.get("response", {})
            usage = response_data.get("usage", {})

            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.MESSAGE_DELTA,
                    stop_reason=self._map_status(
                        response_data.get("status", "completed")
                    ),
                    usage=IRUsage(
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                    )
                    if usage
                    else None,
                )
            )
            ir_events.append(IRStreamEvent(type=StreamEventType.DONE))

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

        if data and event_type:
            data["type"] = event_type
            return data
        return data

    def _map_role(self, role: str) -> Role:
        """Map OpenAI Responses role to IR role."""
        role_map = {
            "user": Role.USER,
            "assistant": Role.ASSISTANT,
            "system": Role.SYSTEM,
        }
        return role_map.get(role, Role.USER)

    def _map_status(self, status: str) -> StopReason:
        """Map OpenAI Responses status to IR stop reason."""
        status_map = {
            "completed": StopReason.END_TURN,
            "incomplete": StopReason.MAX_TOKENS,
            "failed": StopReason.ERROR,
            "cancelled": StopReason.ERROR,
        }
        return status_map.get(status, StopReason.END_TURN)

    def _parse_data_url(self, data_url: str) -> tuple[str, str]:
        """Parse a data URL into media type and base64 data."""
        match = re.match(r"data:([^;]+);base64,(.+)", data_url)
        if match:
            return match.group(1), match.group(2)
        return "application/octet-stream", data_url

    def _parse_json_safely(self, json_str: str) -> Dict[str, Any]:
        """Safely parse JSON string."""
        try:
            return json.loads(json_str) if json_str else {}
        except json.JSONDecodeError:
            return {}


class OpenAIResponsesEncoder:
    """Encodes IR to OpenAI Responses API format."""

    def encode_request(
        self, ir: IRRequest, *, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Encode IR request to OpenAI Responses format."""
        options = options or {}
        payload: Dict[str, Any] = {
            "model": ir.model,
        }

        # Encode input
        if len(ir.messages) == 1 and ir.messages[0].role == Role.USER:
            # Simple case: single user message can be a string
            text = ir.messages[0].get_text_content()
            if text and len(ir.messages[0].content) == 1:
                payload["input"] = text
            else:
                payload["input"] = self._encode_messages(ir.messages)
        else:
            payload["input"] = self._encode_messages(ir.messages)

        # Instructions (system prompt)
        if ir.system:
            payload["instructions"] = ir.system

        # Stream
        if ir.stream:
            payload["stream"] = True

        # Generation config
        config = ir.generation_config
        if config.temperature is not None:
            payload["temperature"] = config.temperature
        if config.top_p is not None:
            payload["top_p"] = config.top_p
        if config.max_tokens is not None:
            payload["max_output_tokens"] = config.max_tokens
        if config.stop_sequences:
            payload["stop"] = config.stop_sequences
        if config.seed is not None:
            payload["seed"] = config.seed

        # Tools
        if ir.tools:
            payload["tools"] = self._encode_tools(ir.tools)

        # Tool choice
        if ir.tool_choice:
            payload["tool_choice"] = self._encode_tool_choice(ir.tool_choice)

        # Response format
        if ir.response_format and ir.response_format.type != "text":
            payload["text"] = {
                "format": self._encode_response_format(ir.response_format)
            }

        # User
        if ir.user:
            payload["user"] = ir.user

        # Add back unsupported params if option enabled
        if options.get("preserve_unsupported", False):
            for key, value in ir.unsupported_params.items():
                if key not in payload:
                    payload[key] = value

        return payload

    def _encode_messages(self, messages: List[IRMessage]) -> List[Dict[str, Any]]:
        """Encode IR messages to OpenAI Responses input format."""
        items = []

        for msg in messages:
            item = self._encode_message(msg)
            if item:
                items.extend(item if isinstance(item, list) else [item])

        return items

    def _encode_message(
        self, msg: IRMessage
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """Encode a single IR message to Responses format item(s)."""
        # Handle tool results
        if msg.role == Role.TOOL:
            items = []
            for block in msg.content:
                if isinstance(block, IRToolResultBlock):
                    items.append(
                        {
                            "type": "function_call_output",
                            "call_id": block.tool_use_id,
                            "output": block.content
                            if isinstance(block.content, str)
                            else str(block.content),
                        }
                    )
            return items if items else None

        # Handle regular messages
        role = self._map_role(msg.role)
        content = []
        function_calls = []

        # Determine text type based on role
        # User messages use input_text/input_image, assistant messages use output_text
        is_user_message = msg.role == Role.USER
        text_type = "input_text" if is_user_message else "output_text"

        for block in msg.content:
            if isinstance(block, IRTextBlock):
                content.append({"type": text_type, "text": block.text})
            elif isinstance(block, IRImageBlock):
                content.append(self._encode_image_block(block, is_user_message))
            elif isinstance(block, IRAudioBlock):
                content.append(self._encode_audio_block(block))
            elif isinstance(block, IRToolUseBlock):
                function_calls.append(
                    {
                        "type": "function_call",
                        "call_id": block.id,
                        "name": block.name,
                        "arguments": json.dumps(block.input) if block.input else "{}",
                    }
                )

        items = []

        # Add message if has content
        if content:
            items.append(
                {
                    "type": "message",
                    "role": role,
                    "content": content,
                }
            )

        # Add function calls as separate items
        items.extend(function_calls)

        return items if items else None

    def _encode_image_block(
        self, block: IRImageBlock, is_user_message: bool = True
    ) -> Dict[str, Any]:
        """Encode an image block."""
        if block.source_type == ImageSourceType.BASE64:
            media_type = block.media_type or "image/png"
            url = f"data:{media_type};base64,{block.base64_data}"
        else:
            url = block.url or ""

        # Use input_image for user messages, image_url for others
        if is_user_message:
            return {"type": "input_image", "image_url": url}
        else:
            return {"type": "image_url", "image_url": url}

    def _encode_audio_block(self, block: IRAudioBlock) -> Dict[str, Any]:
        """Encode an audio block."""
        return {
            "type": "input_audio",
            "input_audio": {
                "data": block.data,
                "format": block.format or "wav",
            },
        }

    def _encode_tools(self, tools: List[IRToolDeclaration]) -> List[Dict[str, Any]]:
        """Encode tool declarations."""
        result = []
        for tool in tools:
            encoded: Dict[str, Any] = {
                "type": "function",
                "name": tool.name,
            }
            if tool.description:
                encoded["description"] = tool.description
            if tool.parameters:
                encoded["parameters"] = tool.parameters
            if tool.strict:
                encoded["strict"] = True
            result.append(encoded)
        return result

    def _encode_tool_choice(self, choice: IRToolChoice) -> Dict[str, Any]:
        """Encode tool choice."""
        if choice.type == ToolChoiceType.AUTO:
            return {"type": "auto"}
        elif choice.type == ToolChoiceType.NONE:
            return {"type": "none"}
        elif choice.type == ToolChoiceType.ANY:
            return {"type": "auto"}  # No direct equivalent
        elif choice.type == ToolChoiceType.SPECIFIC:
            return {"type": "function", "name": choice.name}
        return {"type": "auto"}

    def _encode_response_format(self, fmt: IRResponseFormat) -> Dict[str, Any]:
        """Encode response format."""
        if fmt.type == "json_schema":
            result: Dict[str, Any] = {"type": "json_schema"}
            if fmt.json_schema:
                result["schema"] = fmt.json_schema
            if fmt.schema_name:
                result["name"] = fmt.schema_name
            if fmt.strict:
                result["strict"] = True
            return result
        return {"type": fmt.type}

    def encode_response(
        self, ir: IRResponse, *, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Encode IR response to OpenAI Responses format."""
        # Build output items
        output = []

        # Group text content into a message
        text_parts = []
        for block in ir.content:
            if isinstance(block, IRTextBlock):
                text_parts.append({"type": "output_text", "text": block.text})
            elif isinstance(block, IRToolUseBlock):
                # Add any accumulated text as a message first
                if text_parts:
                    output.append(
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": text_parts,
                        }
                    )
                    text_parts = []

                # Add function call
                output.append(
                    {
                        "type": "function_call",
                        "id": block.id,
                        "call_id": block.id,
                        "name": block.name,
                        "arguments": json.dumps(block.input) if block.input else "{}",
                        "status": "completed",
                    }
                )

        # Add remaining text
        if text_parts:
            output.append(
                {
                    "type": "message",
                    "role": "assistant",
                    "content": text_parts,
                }
            )

        # Build response
        response: Dict[str, Any] = {
            "id": ir.id if ir.id.startswith("resp") else f"resp_{ir.id}",
            "object": "response",
            "created_at": ir.created or int(time.time()),
            "model": ir.model,
            "output": output,
            "status": self._map_stop_reason(ir.stop_reason),
        }

        # Usage
        if ir.usage:
            response["usage"] = {
                "input_tokens": ir.usage.input_tokens,
                "output_tokens": ir.usage.output_tokens,
                "total_tokens": ir.usage.total_tokens
                or (ir.usage.input_tokens + ir.usage.output_tokens),
            }

        return response

    def encode_stream_event(
        self, ir_event: IRStreamEvent, *, options: Optional[Dict[str, Any]] = None
    ) -> List[Union[Dict[str, Any], str]]:
        """Encode IR stream event to OpenAI Responses format."""
        options = options or {}
        output_format = options.get("output_format", "dict")

        events = []

        if ir_event.type == StreamEventType.MESSAGE_START:
            response = ir_event.response
            events.append(
                self._format_event(
                    "response.created",
                    {
                        "response": {
                            "id": response.id if response else "",
                            "object": "response",
                            "created_at": response.created
                            if response
                            else int(time.time()),
                            "model": response.model if response else "",
                            "status": "in_progress",
                            "output": [],
                        }
                    },
                    output_format,
                )
            )

        elif ir_event.type == StreamEventType.CONTENT_BLOCK_START:
            block = ir_event.content_block
            if isinstance(block, IRToolUseBlock):
                events.append(
                    self._format_event(
                        "response.output_item.added",
                        {
                            "output_index": ir_event.index,
                            "item": {
                                "type": "function_call",
                                "id": block.id,
                                "call_id": block.id,
                                "name": block.name,
                                "arguments": "",
                                "status": "in_progress",
                            },
                        },
                        output_format,
                    )
                )
            else:
                events.append(
                    self._format_event(
                        "response.output_item.added",
                        {
                            "output_index": ir_event.index,
                            "item": {
                                "type": "message",
                                "role": "assistant",
                                "content": [],
                            },
                        },
                        output_format,
                    )
                )

        elif ir_event.type == StreamEventType.CONTENT_BLOCK_DELTA:
            if ir_event.delta_type == "text":
                events.append(
                    self._format_event(
                        "response.output_text.delta",
                        {
                            "output_index": ir_event.index,
                            "delta": ir_event.delta_text,
                        },
                        output_format,
                    )
                )
            elif ir_event.delta_type == "input_json":
                events.append(
                    self._format_event(
                        "response.function_call_arguments.delta",
                        {
                            "output_index": ir_event.index,
                            "delta": ir_event.delta_json,
                        },
                        output_format,
                    )
                )

        elif ir_event.type == StreamEventType.CONTENT_BLOCK_STOP:
            events.append(
                self._format_event(
                    "response.output_item.done",
                    {"output_index": ir_event.index},
                    output_format,
                )
            )

        elif ir_event.type == StreamEventType.MESSAGE_DELTA:
            # Usage and status will be in response.done
            pass

        elif ir_event.type == StreamEventType.DONE:
            events.append(
                self._format_event(
                    "response.done",
                    {
                        "response": {
                            "status": "completed",
                            "usage": {
                                "input_tokens": ir_event.usage.input_tokens
                                if ir_event.usage
                                else 0,
                                "output_tokens": ir_event.usage.output_tokens
                                if ir_event.usage
                                else 0,
                            }
                            if ir_event.usage
                            else {},
                        }
                    },
                    output_format,
                )
            )

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
        """Map IR role to OpenAI Responses role."""
        role_map = {
            Role.SYSTEM: "system",
            Role.USER: "user",
            Role.ASSISTANT: "assistant",
            Role.TOOL: "user",  # Tool results go as user in input
        }
        return role_map.get(role, "user")

    def _map_stop_reason(self, reason: Optional[StopReason]) -> str:
        """Map IR stop reason to OpenAI Responses status."""
        if not reason:
            return "completed"
        reason_map = {
            StopReason.END_TURN: "completed",
            StopReason.MAX_TOKENS: "incomplete",
            StopReason.STOP_SEQUENCE: "completed",
            StopReason.TOOL_USE: "completed",
            StopReason.CONTENT_FILTER: "incomplete",
            StopReason.ERROR: "failed",
        }
        return reason_map.get(reason, "completed")
