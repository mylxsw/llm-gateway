"""
协议转换（OpenAI <-> Anthropic）

在供应商协议与用户请求协议不一致时，将请求/响应在两种协议之间转换。
"""

from __future__ import annotations

import copy
import json
import time
import uuid
from typing import Any, AsyncGenerator, Optional

import httpx
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk

from app.common.errors import ServiceError
from app.common.stream_usage import SSEDecoder

try:
    import litellm

    try:
        from litellm.llms.anthropic.chat.transformation import AnthropicConfig  # type: ignore
    except Exception:  # pragma: no cover
        AnthropicConfig = litellm.AnthropicConfig  # type: ignore[misc,assignment]

    try:
        from litellm.types.utils import ModelResponse  # type: ignore
    except Exception:  # pragma: no cover
        from litellm.utils import ModelResponse  # type: ignore

    # NOTE: This module path is not available in all LiteLLM versions.
    try:  # pragma: no cover
        from litellm.llms.anthropic.experimental_pass_through.transformation import (  # type: ignore
            AnthropicExperimentalPassThroughConfig,
        )

        _HAS_EXPERIMENTAL_PASSTHROUGH = True
    except Exception:  # pragma: no cover
        AnthropicExperimentalPassThroughConfig = None  # type: ignore[assignment]
        _HAS_EXPERIMENTAL_PASSTHROUGH = False
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "litellm is required for protocol conversion. "
        "Install backend dependencies (see backend/requirements.txt)."
    ) from e


OPENAI_PROTOCOL = "openai"
ANTHROPIC_PROTOCOL = "anthropic"


def normalize_protocol(protocol: str) -> str:
    protocol = (protocol or OPENAI_PROTOCOL).lower().strip()
    if protocol not in (OPENAI_PROTOCOL, ANTHROPIC_PROTOCOL):
        raise ServiceError(message=f"Unsupported protocol '{protocol}'", code="unsupported_protocol")
    return protocol


def _encode_sse_data(payload: str) -> bytes:
    return f"data: {payload}\n\n".encode("utf-8")


def _encode_sse_json(obj: dict[str, Any]) -> bytes:
    return _encode_sse_data(json.dumps(obj, ensure_ascii=False))


def _map_anthropic_finish_reason_to_openai(stop_reason: Optional[str]) -> str:
    if not stop_reason:
        return "stop"
    if stop_reason == "end_turn":
        return "stop"
    if stop_reason == "max_tokens":
        return "length"
    if stop_reason == "tool_use":
        return "tool_calls"
    return "stop"


def _map_openai_finish_reason_to_anthropic(finish_reason: Optional[str]) -> str:
    if not finish_reason:
        return "end_turn"
    if finish_reason == "stop":
        return "end_turn"
    if finish_reason == "length":
        return "max_tokens"
    if finish_reason == "tool_calls":
        return "tool_use"
    return "end_turn"


def _translate_anthropic_to_openai_request(
    *, anthropic_body: dict[str, Any], target_model: str
) -> dict[str, Any]:
    """
    Fallback translator when LiteLLM experimental passthrough module is unavailable.
    Covers the common text-only paths needed by this gateway.
    """
    system = anthropic_body.get("system")
    messages = anthropic_body.get("messages", [])
    if not isinstance(messages, list):
        raise ServiceError(message="Anthropic request missing 'messages'", code="invalid_request")

    openai_messages: list[dict[str, Any]] = []
    if system is not None:
        if isinstance(system, str):
            system_text = system
        elif isinstance(system, list):
            # Anthropic allows list of system blocks; keep only text blocks.
            parts: list[str] = []
            for item in system:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            system_text = "\n".join(parts)
        else:
            system_text = str(system)
        openai_messages.append({"role": "system", "content": system_text})

    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
                elif isinstance(block, dict) and block.get("type") == "tool_result":
                    # Minimal conversion: treat tool_result as tool message content.
                    tool_call_id = block.get("tool_use_id")
                    tool_content = block.get("content", "")
                    if isinstance(tool_content, list):
                        tool_text_parts: list[str] = []
                        for item in tool_content:
                            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                                tool_text_parts.append(item["text"])
                        tool_content = "\n".join(tool_text_parts)
                    if tool_call_id is not None:
                        openai_messages.append(
                            {"role": "tool", "tool_call_id": tool_call_id, "content": tool_content}
                        )
            if text_parts:
                openai_messages.append({"role": role, "content": "".join(text_parts)})

    out: dict[str, Any] = {"model": target_model, "messages": openai_messages}
    metadata = anthropic_body.get("metadata")
    if isinstance(metadata, dict) and "user_id" in metadata:
        out["user"] = metadata["user_id"]

    passthrough_keys = [
        "temperature",
        "top_p",
        "max_tokens",
        "stream",
        "stop",
        "tools",
        "tool_choice",
    ]
    for k in passthrough_keys:
        if k in anthropic_body:
            out[k] = anthropic_body[k]
    return out


def _translate_openai_response_to_anthropic(body: dict[str, Any], target_model: str) -> dict[str, Any]:
    """
    Fallback translator when LiteLLM experimental passthrough module is unavailable.
    Produces a basic Anthropic Messages response.
    """
    choices = body.get("choices") or []
    first = choices[0] if isinstance(choices, list) and choices else {}
    message = first.get("message") if isinstance(first, dict) else {}
    content = ""
    tool_calls = None
    if isinstance(message, dict):
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")

    anthropic_content: list[dict[str, Any]] = []
    if tool_calls and isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            name = fn.get("name") or ""
            args = fn.get("arguments") or "{}"
            try:
                inp = json.loads(args) if isinstance(args, str) else args
            except Exception:
                inp = {}
            anthropic_content.append({"type": "tool_use", "id": tc.get("id"), "name": name, "input": inp})
    if isinstance(content, str) and content:
        anthropic_content.append({"type": "text", "text": content})

    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    finish_reason = first.get("finish_reason") if isinstance(first, dict) else None

    return {
        "id": body.get("id") or f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "model": body.get("model") or target_model,
        "stop_sequence": None,
        "stop_reason": _map_openai_finish_reason_to_anthropic(finish_reason if isinstance(finish_reason, str) else None),
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "content": anthropic_content,
    }


def convert_request_for_supplier(
    *,
    request_protocol: str,
    supplier_protocol: str,
    path: str,
    body: dict[str, Any],
    target_model: str,
) -> tuple[str, dict[str, Any]]:
    """
    将用户请求协议转换为供应商协议的请求体/路径。

    仅支持 Chat/Messages 的互转：
    - OpenAI: /v1/chat/completions
    - Anthropic: /v1/messages
    """
    request_protocol = normalize_protocol(request_protocol)
    supplier_protocol = normalize_protocol(supplier_protocol)

    if request_protocol == supplier_protocol:
        new_body = copy.deepcopy(body)
        new_body["model"] = target_model
        return path, new_body

    if request_protocol == OPENAI_PROTOCOL and supplier_protocol == ANTHROPIC_PROTOCOL:
        if path != "/v1/chat/completions":
            raise ServiceError(
                message=f"Unsupported OpenAI endpoint for conversion: {path}",
                code="unsupported_protocol_conversion",
            )
        openai_body = copy.deepcopy(body)
        messages = openai_body.get("messages")
        if not isinstance(messages, list):
            raise ServiceError(message="OpenAI request missing 'messages'", code="invalid_request")

        optional_params = {k: v for k, v in openai_body.items() if k not in ("model", "messages")}
        if "max_tokens" not in optional_params and "max_completion_tokens" in optional_params:
            optional_params["max_tokens"] = optional_params["max_completion_tokens"]
        if "max_tokens" not in optional_params:
            optional_params["max_tokens"] = 1024

        anthropic_body = AnthropicConfig().transform_request(
            model=target_model,
            messages=messages,
            optional_params=optional_params,
            litellm_params={},
            headers={},
        )
        return "/v1/messages", anthropic_body

    if request_protocol == ANTHROPIC_PROTOCOL and supplier_protocol == OPENAI_PROTOCOL:
        if path != "/v1/messages":
            raise ServiceError(
                message=f"Unsupported Anthropic endpoint for conversion: {path}",
                code="unsupported_protocol_conversion",
            )
        anthropic_body = copy.deepcopy(body)
        anthropic_body["model"] = target_model
        if _HAS_EXPERIMENTAL_PASSTHROUGH:
            openai_body = AnthropicExperimentalPassThroughConfig().translate_anthropic_to_openai(  # type: ignore[union-attr]
                anthropic_message_request=anthropic_body  # type: ignore[arg-type]
            )
        else:
            openai_body = _translate_anthropic_to_openai_request(
                anthropic_body=anthropic_body, target_model=target_model
            )
        return "/v1/chat/completions", openai_body

    raise ServiceError(
        message=f"Unsupported protocol conversion: {request_protocol} -> {supplier_protocol}",
        code="unsupported_protocol_conversion",
    )


def convert_response_for_user(
    *,
    request_protocol: str,
    supplier_protocol: str,
    body: Any,
    target_model: str,
) -> Any:
    """
    将供应商响应转换为用户请求协议的响应体。
    """
    request_protocol = normalize_protocol(request_protocol)
    supplier_protocol = normalize_protocol(supplier_protocol)

    if request_protocol == supplier_protocol:
        return body

    if not isinstance(body, dict):
        return body

    if request_protocol == ANTHROPIC_PROTOCOL and supplier_protocol == OPENAI_PROTOCOL:
        if _HAS_EXPERIMENTAL_PASSTHROUGH:
            model_response = ModelResponse(**body)
            translated = AnthropicExperimentalPassThroughConfig().translate_openai_response_to_anthropic(  # type: ignore[union-attr]
                response=model_response
            )
            return translated.model_dump(exclude_none=True)
        return _translate_openai_response_to_anthropic(body, target_model)

    if request_protocol == OPENAI_PROTOCOL and supplier_protocol == ANTHROPIC_PROTOCOL:
        dummy_logger = type("DummyLogger", (), {"post_call": lambda *args, **kwargs: None})()
        response = httpx.Response(200, json=body, headers={})
        model = body.get("model") or target_model
        model_response = AnthropicConfig().transform_response(
            model=model,
            raw_response=response,
            model_response=ModelResponse(),
            logging_obj=dummy_logger,
            request_data={},
            messages=[],
            optional_params={},
            litellm_params={},
            encoding=None,
            api_key="",
            json_mode=None,
        )
        return model_response.model_dump(exclude_none=True)

    raise ServiceError(
        message=f"Unsupported protocol conversion: {supplier_protocol} -> {request_protocol}",
        code="unsupported_protocol_conversion",
    )


async def convert_stream_for_user(
    *,
    request_protocol: str,
    supplier_protocol: str,
    upstream: AsyncGenerator[bytes, None],
    model: str,
) -> AsyncGenerator[bytes, None]:
    """
    将供应商 SSE bytes 流转换为用户请求协议的 SSE bytes 流。

    - OpenAI: data: {chat.completion.chunk}\n\n + data: [DONE]\n\n
    - Anthropic: data: {type: ...}\n\n
    """
    request_protocol = normalize_protocol(request_protocol)
    supplier_protocol = normalize_protocol(supplier_protocol)

    if request_protocol == supplier_protocol:
        async for chunk in upstream:
            yield chunk
        return

    if request_protocol == ANTHROPIC_PROTOCOL and supplier_protocol == OPENAI_PROTOCOL:
        decoder = SSEDecoder()

        sent_message_start = False
        sent_content_block_start = False
        sent_content_block_finish = False
        sent_message_stop = False
        holding: Optional[dict[str, Any]] = None

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
                        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
                    )

                try:
                    data = json.loads(payload)
                except Exception:
                    continue

                try:
                    openai_chunk = ChatCompletionChunk(**data)
                except Exception:
                    continue

                if _HAS_EXPERIMENTAL_PASSTHROUGH:
                    cfg = AnthropicExperimentalPassThroughConfig()  # type: ignore[call-arg]
                    processed = cfg.translate_streaming_openai_response_to_anthropic(response=openai_chunk)  # type: ignore[union-attr]
                else:
                    # Minimal fallback: translate content delta + finish into Anthropic stream events
                    choice = openai_chunk.choices[0] if openai_chunk.choices else None
                    if choice is None:
                        continue
                    if choice.delta and getattr(choice.delta, "content", None):
                        processed = {
                            "type": "content_block_delta",
                            "index": choice.index,
                            "delta": {"type": "text_delta", "text": choice.delta.content},
                        }
                    elif choice.finish_reason is not None:
                        processed = {
                            "type": "message_delta",
                            "delta": {"stop_reason": _map_openai_finish_reason_to_anthropic(choice.finish_reason)},
                            "usage": {"output_tokens": 0},
                        }
                    else:
                        continue

                if processed.get("type") == "message_delta" and sent_content_block_finish is False:
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

        if sent_message_stop is False:
            sent_message_stop = True
            yield _encode_sse_json({"type": "message_stop"})
        return

    if request_protocol == OPENAI_PROTOCOL and supplier_protocol == ANTHROPIC_PROTOCOL:
        decoder = SSEDecoder()
        response_id: Optional[str] = None
        sent_role = False
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
                    if isinstance(content_block, dict) and content_block.get("type") == "text":
                        text = content_block.get("text") or ""
                        if text:
                            delta: dict[str, Any] = {"content": text}
                            if not sent_role:
                                delta["role"] = "assistant"
                                sent_role = True
                            yield _encode_sse_json(
                                {
                                    "id": response_id or f"chatcmpl-{uuid.uuid4().hex}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                                }
                            )
                    continue

                if event_type == "content_block_delta":
                    delta_obj = data.get("delta")
                    if isinstance(delta_obj, dict):
                        delta_type = delta_obj.get("type")
                        if delta_type == "text_delta":
                            text = delta_obj.get("text") or ""
                            if text:
                                delta: dict[str, Any] = {"content": text}
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    {
                                        "id": response_id or f"chatcmpl-{uuid.uuid4().hex}",
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": model,
                                        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                                    }
                                )
                        elif delta_type == "input_json_delta":
                            partial_json = delta_obj.get("partial_json") or ""
                            if partial_json:
                                delta: dict[str, Any] = {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": None,
                                            "type": "function",
                                            "function": {"name": None, "arguments": partial_json},
                                        }
                                    ]
                                }
                                if not sent_role:
                                    delta["role"] = "assistant"
                                    sent_role = True
                                yield _encode_sse_json(
                                    {
                                        "id": response_id or f"chatcmpl-{uuid.uuid4().hex}",
                                        "object": "chat.completion.chunk",
                                        "created": int(time.time()),
                                        "model": model,
                                        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
                                    }
                                )
                    continue

                if event_type == "message_delta":
                    delta_dict = data.get("delta")
                    stop_reason = None
                    if isinstance(delta_dict, dict):
                        stop_reason = delta_dict.get("stop_reason")
                    finish_reason = _map_anthropic_finish_reason_to_openai(stop_reason)
                    yield _encode_sse_json(
                        {
                            "id": response_id or f"chatcmpl-{uuid.uuid4().hex}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
                        }
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
        return

    raise ServiceError(
        message=f"Unsupported protocol conversion: {supplier_protocol} -> {request_protocol}",
        code="unsupported_protocol_conversion",
    )
