"""
OpenAI Chat Completions (Classic) Encoder/Decoder

Converts between OpenAI Chat Completions format and the Intermediate Representation.
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


class OpenAIChatDecoder:
    """Decodes OpenAI Chat Completions format to IR."""

    def decode_request(self, payload: Dict[str, Any]) -> IRRequest:
        """Decode an OpenAI Chat request to IR."""
        ir = IRRequest(
            model=payload.get("model", ""),
            stream=payload.get("stream", False),
        )

        # Decode messages
        messages = payload.get("messages", [])
        ir.messages, ir.system = self._decode_messages(messages)

        # Decode generation config
        ir.generation_config = self._decode_generation_config(payload)

        # Decode tools
        if "tools" in payload:
            ir.tools = self._decode_tools(payload["tools"])

        # Decode tool choice
        if "tool_choice" in payload:
            ir.tool_choice = self._decode_tool_choice(payload["tool_choice"])

        # Decode response format
        if "response_format" in payload:
            ir.response_format = self._decode_response_format(
                payload["response_format"]
            )

        # User
        if "user" in payload:
            ir.user = payload["user"]

        # Store unsupported params
        unsupported_keys = [
            "store",
            "stream_options",
            "service_tier",
            "parallel_tool_calls",
        ]
        for key in unsupported_keys:
            if key in payload:
                ir.unsupported_params[key] = payload[key]

        return ir

    def _decode_messages(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[List[IRMessage], Optional[str]]:
        """Decode messages and extract system prompt."""
        ir_messages = []
        system_parts = []

        for msg in messages:
            role = msg.get("role", "user")

            # Extract system/developer messages
            if role in ("system", "developer"):
                content = msg.get("content", "")
                if isinstance(content, str):
                    system_parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            system_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            system_parts.append(block)
                continue

            # Decode user/assistant/tool messages
            ir_role = self._map_role(role)
            ir_message = IRMessage(role=ir_role)

            # Decode content
            content = msg.get("content")
            if content is not None:
                ir_message.content = self._decode_content(content, msg)

            # Decode tool calls (for assistant messages)
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    tool_use = IRToolUseBlock(
                        id=tc.get("id", ""),
                        name=tc.get("function", {}).get("name", ""),
                        input=self._parse_json_safely(
                            tc.get("function", {}).get("arguments", "{}")
                        ),
                    )
                    ir_message.content.append(tool_use)

            # Handle tool message (tool result)
            if role == "tool":
                tool_result = IRToolResultBlock(
                    tool_use_id=msg.get("tool_call_id", ""),
                    content=msg.get("content", ""),
                )
                ir_message.content = [tool_result]

            # Name
            if "name" in msg:
                ir_message.name = msg["name"]

            ir_messages.append(ir_message)

        system = "\n\n".join(system_parts) if system_parts else None
        return ir_messages, system

    def _decode_content(
        self, content: Union[str, List[Dict[str, Any]]], msg: Dict[str, Any]
    ) -> List[IRContentBlock]:
        """Decode message content to IR blocks."""
        blocks: List[IRContentBlock] = []

        if isinstance(content, str):
            if content:
                blocks.append(IRTextBlock(text=content))
        elif isinstance(content, list):
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

        if block_type == "text":
            return IRTextBlock(text=block.get("text", ""))

        elif block_type == "image_url":
            image_url = block.get("image_url", {})
            if isinstance(image_url, str):
                url = image_url
                detail = None
            else:
                url = image_url.get("url", "")
                detail = image_url.get("detail")

            # Check if it's a data URL (base64)
            if url.startswith("data:"):
                media_type, base64_data = self._parse_data_url(url)
                return IRImageBlock(
                    source_type=ImageSourceType.BASE64,
                    base64_data=base64_data,
                    media_type=media_type,
                    detail=detail,
                )
            else:
                return IRImageBlock(
                    source_type=ImageSourceType.URL,
                    url=url,
                    detail=detail,
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
        if "max_tokens" in payload:
            config.max_tokens = payload["max_tokens"]
        if "max_completion_tokens" in payload:
            config.max_tokens = payload["max_completion_tokens"]
        if "stop" in payload:
            stop = payload["stop"]
            if isinstance(stop, str):
                config.stop_sequences = [stop]
            else:
                config.stop_sequences = stop
        if "seed" in payload:
            config.seed = payload["seed"]
        if "presence_penalty" in payload:
            config.presence_penalty = payload["presence_penalty"]
        if "frequency_penalty" in payload:
            config.frequency_penalty = payload["frequency_penalty"]
        if "logprobs" in payload:
            config.logprobs = payload["logprobs"]
        if "top_logprobs" in payload:
            config.top_logprobs = payload["top_logprobs"]
        if "n" in payload:
            config.n = payload["n"]

        return config

    def _decode_tools(self, tools: List[Dict[str, Any]]) -> List[IRToolDeclaration]:
        """Decode tool declarations."""
        ir_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                ir_tools.append(
                    IRToolDeclaration(
                        name=func.get("name", ""),
                        description=func.get("description"),
                        parameters=func.get("parameters", {}),
                        strict=func.get("strict", False),
                    )
                )
        return ir_tools

    def _decode_tool_choice(
        self, tool_choice: Union[str, Dict[str, Any]]
    ) -> IRToolChoice:
        """Decode tool choice configuration."""
        if isinstance(tool_choice, str):
            if tool_choice == "auto":
                return IRToolChoice(type=ToolChoiceType.AUTO)
            elif tool_choice == "none":
                return IRToolChoice(type=ToolChoiceType.NONE)
            elif tool_choice == "required":
                return IRToolChoice(type=ToolChoiceType.ANY)
        elif isinstance(tool_choice, dict):
            if tool_choice.get("type") == "function":
                name = tool_choice.get("function", {}).get("name", "")
                return IRToolChoice(type=ToolChoiceType.SPECIFIC, name=name)
        return IRToolChoice(type=ToolChoiceType.AUTO)

    def _decode_response_format(
        self, response_format: Dict[str, Any]
    ) -> IRResponseFormat:
        """Decode response format configuration."""
        fmt_type = response_format.get("type", "text")
        ir_format = IRResponseFormat(type=fmt_type)

        if fmt_type == "json_schema":
            schema = response_format.get("json_schema", {})
            ir_format.json_schema = schema.get("schema")
            ir_format.schema_name = schema.get("name")
            ir_format.strict = schema.get("strict", False)

        return ir_format

    def decode_response(self, payload: Dict[str, Any]) -> IRResponse:
        """Decode an OpenAI Chat response to IR."""
        ir = IRResponse(
            id=payload.get("id", ""),
            model=payload.get("model", ""),
            created=payload.get("created"),
        )

        # Decode first choice (primary response)
        choices = payload.get("choices", [])
        if choices:
            choice = choices[0]
            ir.choice_index = choice.get("index", 0)

            # Decode message content
            message = choice.get("message", {})
            content = message.get("content")
            if content:
                ir.content.append(IRTextBlock(text=content))

            # Decode tool calls
            tool_calls = message.get("tool_calls", [])
            for tc in tool_calls:
                ir.content.append(
                    IRToolUseBlock(
                        id=tc.get("id", ""),
                        name=tc.get("function", {}).get("name", ""),
                        input=self._parse_json_safely(
                            tc.get("function", {}).get("arguments", "{}")
                        ),
                    )
                )

            # Decode finish reason
            finish_reason = choice.get("finish_reason")
            ir.stop_reason = self._map_finish_reason(finish_reason)

        # Decode usage
        usage = payload.get("usage")
        if usage:
            ir.usage = IRUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens"),
            )
            # Decode detailed usage
            prompt_details = usage.get("prompt_tokens_details", {})
            if prompt_details:
                ir.usage.cache_read_tokens = prompt_details.get("cached_tokens", 0)
            completion_details = usage.get("completion_tokens_details", {})
            if completion_details:
                ir.usage.reasoning_tokens = completion_details.get(
                    "reasoning_tokens", 0
                )

        return ir

    def decode_stream_event(
        self, event: Union[Dict[str, Any], str]
    ) -> List[IRStreamEvent]:
        """Decode a streaming event to IR events."""
        # Handle SSE text format
        if isinstance(event, str):
            event = self._parse_sse_line(event)
            if event is None:
                return []

        # Handle [DONE] marker
        if event == "[DONE]":
            return [IRStreamEvent(type=StreamEventType.DONE)]

        ir_events = []

        # Extract chunk data
        choices = event.get("choices", [])
        if not choices:
            # Check for usage-only final chunk
            if "usage" in event:
                usage = event["usage"]
                ir_events.append(
                    IRStreamEvent(
                        type=StreamEventType.MESSAGE_DELTA,
                        usage=IRUsage(
                            input_tokens=usage.get("prompt_tokens", 0),
                            output_tokens=usage.get("completion_tokens", 0),
                        ),
                    )
                )
            return ir_events

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        # Role delta (message start)
        if "role" in delta:
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.MESSAGE_START,
                    response=IRResponse(
                        id=event.get("id", ""),
                        model=event.get("model", ""),
                        created=event.get("created"),
                    ),
                )
            )

        # Content delta
        if "content" in delta and delta["content"]:
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.CONTENT_BLOCK_DELTA,
                    index=0,
                    delta_type="text",
                    delta_text=delta["content"],
                )
            )

        # Tool calls delta
        if "tool_calls" in delta:
            for tc in delta["tool_calls"]:
                index = tc.get("index", 0)
                func = tc.get("function", {})

                # Tool call start (has id and name)
                if "id" in tc:
                    ir_events.append(
                        IRStreamEvent(
                            type=StreamEventType.CONTENT_BLOCK_START,
                            index=index,
                            content_block=IRToolUseBlock(
                                id=tc["id"],
                                name=func.get("name", ""),
                            ),
                        )
                    )

                # Arguments delta
                if "arguments" in func:
                    ir_events.append(
                        IRStreamEvent(
                            type=StreamEventType.CONTENT_BLOCK_DELTA,
                            index=index,
                            delta_type="input_json",
                            delta_json=func["arguments"],
                        )
                    )

        # Finish reason
        if finish_reason:
            ir_events.append(
                IRStreamEvent(
                    type=StreamEventType.MESSAGE_DELTA,
                    stop_reason=self._map_finish_reason(finish_reason),
                )
            )

        return ir_events

    def _parse_sse_line(self, line: str) -> Optional[Union[Dict[str, Any], str]]:
        """Parse an SSE data line."""
        line = line.strip()
        if not line or line.startswith(":"):
            return None
        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                return "[DONE]"
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    def _map_role(self, role: str) -> Role:
        """Map OpenAI role to IR role."""
        role_map = {
            "system": Role.SYSTEM,
            "developer": Role.SYSTEM,
            "user": Role.USER,
            "assistant": Role.ASSISTANT,
            "tool": Role.TOOL,
        }
        return role_map.get(role, Role.USER)

    def _map_finish_reason(self, reason: Optional[str]) -> Optional[StopReason]:
        """Map OpenAI finish reason to IR stop reason."""
        if not reason:
            return None
        reason_map = {
            "stop": StopReason.END_TURN,
            "length": StopReason.MAX_TOKENS,
            "tool_calls": StopReason.TOOL_USE,
            "content_filter": StopReason.CONTENT_FILTER,
        }
        return reason_map.get(reason, StopReason.END_TURN)

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


class OpenAIChatEncoder:
    """Encodes IR to OpenAI Chat Completions format."""

    def encode_request(
        self, ir: IRRequest, *, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Encode IR request to OpenAI Chat format."""
        options = options or {}
        payload: Dict[str, Any] = {
            "model": ir.model,
            "messages": self._encode_messages(ir.messages, ir.system),
        }

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
            # Use max_completion_tokens for better compatibility with newer OpenAI models
            # (o1, o3, etc. require max_completion_tokens instead of max_tokens)
            payload["max_completion_tokens"] = config.max_tokens
        if config.stop_sequences:
            payload["stop"] = config.stop_sequences
        if config.seed is not None:
            payload["seed"] = config.seed
        if config.presence_penalty is not None:
            payload["presence_penalty"] = config.presence_penalty
        if config.frequency_penalty is not None:
            payload["frequency_penalty"] = config.frequency_penalty
        if config.logprobs is not None:
            payload["logprobs"] = config.logprobs
        if config.top_logprobs is not None:
            payload["top_logprobs"] = config.top_logprobs
        if config.n is not None and config.n > 1:
            payload["n"] = config.n

        # Tools
        if ir.tools:
            payload["tools"] = self._encode_tools(ir.tools)

        # Tool choice
        if ir.tool_choice:
            payload["tool_choice"] = self._encode_tool_choice(ir.tool_choice)

        # Response format
        if ir.response_format:
            payload["response_format"] = self._encode_response_format(
                ir.response_format
            )

        # User
        if ir.user:
            payload["user"] = ir.user

        # Add back unsupported params if option enabled
        if options.get("preserve_unsupported", False):
            for key, value in ir.unsupported_params.items():
                if key not in payload:
                    payload[key] = value

        return payload

    def _encode_messages(
        self, messages: List[IRMessage], system: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Encode IR messages to OpenAI format."""
        result = []

        # Add system message if present
        if system:
            result.append({"role": "system", "content": system})

        for msg in messages:
            encoded = self._encode_message(msg)
            if encoded:
                result.append(encoded)

        return result

    def _encode_message(self, msg: IRMessage) -> Optional[Dict[str, Any]]:
        """Encode a single IR message."""
        role = self._map_role(msg.role)
        message: Dict[str, Any] = {"role": role}

        # Handle tool results separately
        if msg.role == Role.TOOL:
            tool_results = [b for b in msg.content if isinstance(b, IRToolResultBlock)]
            if tool_results:
                tr = tool_results[0]
                message["tool_call_id"] = tr.tool_use_id
                message["content"] = (
                    tr.content if isinstance(tr.content, str) else str(tr.content)
                )
                return message

        # Encode content blocks
        content_blocks = []
        tool_calls = []

        for block in msg.content:
            if isinstance(block, IRTextBlock):
                content_blocks.append({"type": "text", "text": block.text})
            elif isinstance(block, IRImageBlock):
                content_blocks.append(self._encode_image_block(block))
            elif isinstance(block, IRAudioBlock):
                content_blocks.append(self._encode_audio_block(block))
            elif isinstance(block, IRToolUseBlock):
                tool_calls.append(self._encode_tool_call(block))
            elif isinstance(block, IRToolResultBlock):
                # Skip - handled separately
                pass

        # Set content
        if len(content_blocks) == 1 and content_blocks[0]["type"] == "text":
            message["content"] = content_blocks[0]["text"]
        elif content_blocks:
            message["content"] = content_blocks
        elif not tool_calls:
            message["content"] = None

        # Set tool calls
        if tool_calls:
            message["tool_calls"] = tool_calls
            if "content" not in message:
                message["content"] = None

        # Name
        if msg.name:
            message["name"] = msg.name

        return message

    def _encode_image_block(self, block: IRImageBlock) -> Dict[str, Any]:
        """Encode an image block."""
        if block.source_type == ImageSourceType.BASE64:
            media_type = block.media_type or "image/png"
            url = f"data:{media_type};base64,{block.base64_data}"
        else:
            url = block.url or ""

        image_url: Dict[str, Any] = {"url": url}
        if block.detail:
            image_url["detail"] = block.detail

        return {"type": "image_url", "image_url": image_url}

    def _encode_audio_block(self, block: IRAudioBlock) -> Dict[str, Any]:
        """Encode an audio block."""
        return {
            "type": "input_audio",
            "input_audio": {
                "data": block.data,
                "format": block.format or "wav",
            },
        }

    def _encode_tool_call(self, block: IRToolUseBlock) -> Dict[str, Any]:
        """Encode a tool call."""
        return {
            "id": block.id,
            "type": "function",
            "function": {
                "name": block.name,
                "arguments": json.dumps(block.input) if block.input else "{}",
            },
        }

    def _encode_tools(self, tools: List[IRToolDeclaration]) -> List[Dict[str, Any]]:
        """Encode tool declarations."""
        result = []
        for tool in tools:
            encoded: Dict[str, Any] = {
                "type": "function",
                "function": {
                    "name": tool.name,
                },
            }
            if tool.description:
                encoded["function"]["description"] = tool.description
            if tool.parameters:
                encoded["function"]["parameters"] = tool.parameters
            if tool.strict:
                encoded["function"]["strict"] = True
            result.append(encoded)
        return result

    def _encode_tool_choice(self, choice: IRToolChoice) -> Union[str, Dict[str, Any]]:
        """Encode tool choice."""
        if choice.type == ToolChoiceType.AUTO:
            return "auto"
        elif choice.type == ToolChoiceType.NONE:
            return "none"
        elif choice.type == ToolChoiceType.ANY:
            return "required"
        elif choice.type == ToolChoiceType.SPECIFIC:
            return {"type": "function", "function": {"name": choice.name}}
        return "auto"

    def _encode_response_format(self, fmt: IRResponseFormat) -> Dict[str, Any]:
        """Encode response format."""
        if fmt.type == "json_schema":
            result: Dict[str, Any] = {
                "type": "json_schema",
                "json_schema": {},
            }
            if fmt.schema_name:
                result["json_schema"]["name"] = fmt.schema_name
            if fmt.json_schema:
                result["json_schema"]["schema"] = fmt.json_schema
            if fmt.strict:
                result["json_schema"]["strict"] = True
            return result
        return {"type": fmt.type}

    def encode_response(
        self, ir: IRResponse, *, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Encode IR response to OpenAI Chat format."""
        # Build message
        message: Dict[str, Any] = {"role": "assistant"}

        # Extract text content
        text_parts = []
        tool_calls = []

        for block in ir.content:
            if isinstance(block, IRTextBlock):
                text_parts.append(block.text)
            elif isinstance(block, IRToolUseBlock):
                tool_calls.append(self._encode_tool_call(block))

        message["content"] = "".join(text_parts) if text_parts else None

        if tool_calls:
            message["tool_calls"] = tool_calls

        # Determine finish_reason:
        # If response contains tool_calls, finish_reason should be "tool_calls"
        # regardless of the original stop_reason
        if tool_calls:
            finish_reason = "tool_calls"
        else:
            finish_reason = self._map_stop_reason(ir.stop_reason)

        # Build response
        response: Dict[str, Any] = {
            "id": ir.id if ir.id.startswith("chatcmpl") else f"chatcmpl-{ir.id}",
            "object": "chat.completion",
            "created": ir.created or int(time.time()),
            "model": ir.model,
            "choices": [
                {
                    "index": ir.choice_index,
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ],
        }

        # Usage
        if ir.usage:
            response["usage"] = {
                "prompt_tokens": ir.usage.input_tokens,
                "completion_tokens": ir.usage.output_tokens,
                "total_tokens": ir.usage.total_tokens
                or (ir.usage.input_tokens + ir.usage.output_tokens),
            }

        return response

    def encode_stream_event(
        self, ir_event: IRStreamEvent, *, options: Optional[Dict[str, Any]] = None
    ) -> List[Union[Dict[str, Any], str]]:
        """Encode IR stream event to OpenAI Chat format."""
        options = options or {}
        output_format = options.get("output_format", "dict")  # dict or sse

        events = []

        if ir_event.type == StreamEventType.MESSAGE_START:
            chunk = self._create_chunk_base(ir_event.response)
            chunk["choices"] = [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ]
            events.append(self._format_event(chunk, output_format))

        elif ir_event.type == StreamEventType.CONTENT_BLOCK_DELTA:
            if ir_event.delta_type == "text":
                chunk = self._create_chunk_base()
                chunk["choices"] = [
                    {
                        "index": 0,
                        "delta": {"content": ir_event.delta_text},
                        "finish_reason": None,
                    }
                ]
                events.append(self._format_event(chunk, output_format))

            elif ir_event.delta_type == "input_json":
                chunk = self._create_chunk_base()
                chunk["choices"] = [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": ir_event.index,
                                    "function": {"arguments": ir_event.delta_json},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
                events.append(self._format_event(chunk, output_format))

        elif ir_event.type == StreamEventType.CONTENT_BLOCK_START:
            if isinstance(ir_event.content_block, IRToolUseBlock):
                chunk = self._create_chunk_base()
                chunk["choices"] = [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": ir_event.index,
                                    "id": ir_event.content_block.id,
                                    "type": "function",
                                    "function": {
                                        "name": ir_event.content_block.name,
                                        "arguments": "",
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
                events.append(self._format_event(chunk, output_format))

        elif ir_event.type == StreamEventType.MESSAGE_DELTA:
            if ir_event.stop_reason:
                chunk = self._create_chunk_base()
                chunk["choices"] = [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": self._map_stop_reason(ir_event.stop_reason),
                    }
                ]
                events.append(self._format_event(chunk, output_format))

            if ir_event.usage:
                chunk = self._create_chunk_base()
                chunk["choices"] = []
                chunk["usage"] = {
                    "prompt_tokens": ir_event.usage.input_tokens,
                    "completion_tokens": ir_event.usage.output_tokens,
                    "total_tokens": ir_event.usage.total_tokens or 0,
                }
                events.append(self._format_event(chunk, output_format))

        elif ir_event.type == StreamEventType.DONE:
            if output_format == "sse":
                events.append("data: [DONE]\n\n")
            else:
                events.append("[DONE]")

        return events

    def _create_chunk_base(
        self, response: Optional[IRResponse] = None
    ) -> Dict[str, Any]:
        """Create base chunk structure."""
        return {
            "id": response.id if response else "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "created": response.created if response else int(time.time()),
            "model": response.model if response else "",
        }

    def _format_event(
        self, chunk: Dict[str, Any], output_format: str
    ) -> Union[Dict[str, Any], str]:
        """Format event based on output format."""
        if output_format == "sse":
            return f"data: {json.dumps(chunk)}\n\n"
        return chunk

    def _map_role(self, role: Role) -> str:
        """Map IR role to OpenAI role."""
        role_map = {
            Role.SYSTEM: "system",
            Role.USER: "user",
            Role.ASSISTANT: "assistant",
            Role.TOOL: "tool",
        }
        return role_map.get(role, "user")

    def _map_stop_reason(self, reason: Optional[StopReason]) -> Optional[str]:
        """Map IR stop reason to OpenAI finish reason."""
        if not reason:
            return None
        reason_map = {
            StopReason.END_TURN: "stop",
            StopReason.MAX_TOKENS: "length",
            StopReason.STOP_SEQUENCE: "stop",
            StopReason.TOOL_USE: "tool_calls",
            StopReason.CONTENT_FILTER: "content_filter",
            StopReason.ERROR: "stop",
        }
        return reason_map.get(reason, "stop")
