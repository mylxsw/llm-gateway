"""
OpenAI Responses API compatibility helpers.

This gateway primarily supports OpenAI Chat Completions (`/v1/chat/completions`) as the internal
OpenAI-compatible interface. This module provides lightweight translation between the newer
OpenAI Responses API (`/v1/responses`) and Chat Completions so clients can use the newer endpoint.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncGenerator, Optional

from app.common.stream_usage import SSEDecoder
from app.common.token_counter import get_token_counter


def _coerce_openai_content_to_responses(content: Any) -> list[dict[str, Any]]:
    if content is None:
        return []

    if isinstance(content, str):
        return [{"type": "input_text", "text": content}]

    if isinstance(content, list):
        out: list[dict[str, Any]] = []
        for item in content:
            if isinstance(item, str):
                if item:
                    out.append({"type": "input_text", "text": item})
                continue
            if not isinstance(item, dict):
                continue
            block_type = item.get("type")
            if block_type in ("text", "input_text", "output_text"):
                text = item.get("text") or item.get("content")
                if isinstance(text, str) and text:
                    out.append({"type": "input_text", "text": text})
                continue
            if block_type in ("image_url", "input_image"):
                url: Optional[str] = None
                image_url = item.get("image_url")
                if isinstance(image_url, dict) and isinstance(
                    image_url.get("url"), str
                ):
                    url = image_url["url"]
                elif isinstance(image_url, str):
                    url = image_url
                elif isinstance(item.get("url"), str):
                    url = item.get("url")
                if url:
                    out.append({"type": "input_image", "image_url": {"url": url}})
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                out.append({"type": "input_text", "text": text})
        return out

    if isinstance(content, dict):
        text = content.get("text") or content.get("content")
        if isinstance(text, str):
            return [{"type": "input_text", "text": text}]

    return [{"type": "input_text", "text": str(content)}]


def chat_completions_request_to_responses(body: dict[str, Any]) -> dict[str, Any]:
    """
    Translate `/v1/chat/completions` request body into `/v1/responses` request body.
    """
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Chat Completions request missing 'messages'")

    instructions: list[str] = []
    input_messages: list[dict[str, Any]] = []

    for item in messages:
        if not isinstance(item, dict):
            continue
        role = item.get("role") if isinstance(item.get("role"), str) else "user"
        content = _coerce_openai_content_to_responses(item.get("content"))
        if role == "system":
            if content:
                instructions.append(
                    "".join(
                        block.get("text", "")
                        for block in content
                        if block.get("type") == "input_text"
                    )
                )
            continue
        input_messages.append({"role": role, "content": content})

    responses_body: dict[str, Any] = {"model": body.get("model")}
    if instructions:
        responses_body["instructions"] = "\n".join(
            [text for text in instructions if text]
        )

    if input_messages:
        responses_body["input"] = input_messages
    else:
        responses_body["input"] = ""

    passthrough_keys = (
        "temperature",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "n",
        "stop",
        "stream",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "response_format",
        "logprobs",
        "top_logprobs",
        "user",
        "metadata",
    )
    for key in passthrough_keys:
        if key in body:
            responses_body[key] = body[key]

    max_output_tokens = None
    if "max_completion_tokens" in body:
        max_output_tokens = body.get("max_completion_tokens")
    elif "max_tokens" in body:
        max_output_tokens = body.get("max_tokens")

    if max_output_tokens is not None:
        responses_body["max_output_tokens"] = max_output_tokens

    return responses_body


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _coerce_input_to_messages(input_value: Any) -> list[dict[str, Any]]:
    if input_value is None:
        return []

    if isinstance(input_value, str):
        return [{"role": "user", "content": input_value}]

    # Some clients send OpenAI "messages" style directly in `input`.
    if isinstance(input_value, list):
        # If it looks like a list of message objects with roles, treat it as messages.
        if all(
            isinstance(x, dict) and ("role" in x or x.get("type") == "message")
            for x in input_value
        ):
            out_messages: list[dict[str, Any]] = []
            for item in input_value:
                if not isinstance(item, dict):
                    continue
                role = item.get("role")
                if item.get("type") == "message" and role is None:
                    role = item.get("role")
                if not isinstance(role, str) or not role:
                    role = "user"

                if "content" in item:
                    content = _coerce_content_blocks(item.get("content"))
                elif "text" in item and isinstance(item.get("text"), str):
                    content = item.get("text")
                else:
                    content = ""

                out_messages.append({"role": role, "content": content})
            return out_messages

        # Otherwise, treat as a list of input content blocks and wrap into a user message.
        content = _coerce_content_blocks(input_value)
        return [{"role": "user", "content": content}]

    if isinstance(input_value, dict):
        # Single message-like object.
        role = (
            input_value.get("role")
            if isinstance(input_value.get("role"), str)
            else "user"
        )
        content = (
            _coerce_content_blocks(input_value.get("content"))
            if "content" in input_value
            else (
                input_value.get("text")
                if isinstance(input_value.get("text"), str)
                else ""
            )
        )
        return [{"role": role, "content": content}]

    return [{"role": "user", "content": str(input_value)}]


def _coerce_content_blocks(content: Any) -> Any:
    """
    Convert Responses-style content blocks into Chat Completions content.

    - "input_text" -> {"type":"text","text":...}
    - "input_image" / "image_url" -> {"type":"image_url","image_url":{"url":...}}
    """
    if content is None or isinstance(content, str):
        return content or ""

    if not isinstance(content, list):
        return str(content)

    out: list[dict[str, Any]] = []
    for block in content:
        if isinstance(block, str):
            if block:
                out.append({"type": "text", "text": block})
            continue
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")
        if block_type in ("input_text", "output_text", "text"):
            text = block.get("text")
            if isinstance(text, str) and text:
                out.append({"type": "text", "text": text})
            continue

        if block_type in ("input_image", "image_url"):
            url: Optional[str] = None
            if isinstance(block.get("image_url"), dict) and isinstance(
                block["image_url"].get("url"), str
            ):
                url = block["image_url"]["url"]
            elif isinstance(block.get("url"), str):
                url = block["url"]
            elif isinstance(block.get("image_url"), str):
                url = block["image_url"]
            if url:
                out.append({"type": "image_url", "image_url": {"url": url}})
            continue

        # Best-effort fallback for blocks that contain text.
        text = block.get("text")
        if isinstance(text, str) and text:
            out.append({"type": "text", "text": text})

    if len(out) == 1 and out[0].get("type") == "text":
        return out[0].get("text") or ""
    return out


def responses_request_to_chat_completions(body: dict[str, Any]) -> dict[str, Any]:
    """
    Translate `/v1/responses` request body into `/v1/chat/completions` request body.
    """
    instructions = body.get("instructions")
    input_value = body.get("input")

    # Some clients may still send `messages`; treat as-is.
    messages = body.get("messages")
    if isinstance(messages, list):
        chat_messages = messages
    else:
        chat_messages = _coerce_input_to_messages(input_value)

    if isinstance(instructions, str) and instructions:
        chat_messages = [{"role": "system", "content": instructions}] + chat_messages

    if not chat_messages:
        raise ValueError("Responses request missing 'input' (or 'messages')")

    chat_body: dict[str, Any] = {
        "model": body.get("model"),
        "messages": chat_messages,
    }

    # Map common parameters. Keep this list tight to avoid forwarding Responses-only fields to providers.
    passthrough_keys = (
        "temperature",
        "top_p",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "n",
        "stop",
        "stream",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "response_format",
        "logprobs",
        "top_logprobs",
        "user",
        "metadata",
        "max_tokens",
        "max_completion_tokens",
    )
    for key in passthrough_keys:
        if key in body:
            chat_body[key] = body[key]

    if (
        "max_output_tokens" in body
        and "max_tokens" not in chat_body
        and "max_completion_tokens" not in chat_body
    ):
        chat_body["max_completion_tokens"] = body.get("max_output_tokens")

    return chat_body


def _extract_assistant_text_from_chat_completion(chat_body: dict[str, Any]) -> str:
    choices = chat_body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if (
                isinstance(item, dict)
                and item.get("type") in ("text", "output_text")
                and isinstance(item.get("text"), str)
            ):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _extract_assistant_text_from_responses(resp_body: dict[str, Any]) -> str:
    output = resp_body.get("output")
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") in ("output_text", "text"):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "".join(parts)


def chat_completion_to_responses_response(chat_body: dict[str, Any]) -> dict[str, Any]:
    """
    Translate `/v1/chat/completions` response body into `/v1/responses` response body.
    """
    created_at = chat_body.get("created")
    if not isinstance(created_at, int):
        created_at = int(time.time())

    chat_id = chat_body.get("id")
    resp_id = (
        f"resp_{chat_id}" if isinstance(chat_id, str) and chat_id else _new_id("resp")
    )
    msg_id = _new_id("msg")

    usage = chat_body.get("usage") if isinstance(chat_body.get("usage"), dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))

    text = _extract_assistant_text_from_chat_completion(chat_body)

    return {
        "id": resp_id,
        "object": "response",
        "created_at": created_at,
        "model": chat_body.get("model"),
        "status": "completed",
        "output": [
            {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
    }


def responses_response_to_chat_completion(resp_body: dict[str, Any]) -> dict[str, Any]:
    """
    Translate `/v1/responses` response body into `/v1/chat/completions` response body.
    """
    created_at = resp_body.get("created_at")
    if not isinstance(created_at, int):
        created_at = int(time.time())

    resp_id = resp_body.get("id")
    chat_id = (
        f"chatcmpl_{resp_id}"
        if isinstance(resp_id, str) and resp_id
        else _new_id("chatcmpl")
    )

    usage = resp_body.get("usage") if isinstance(resp_body.get("usage"), dict) else {}
    prompt_tokens = int(usage.get("input_tokens") or 0)
    completion_tokens = int(usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))

    text = _extract_assistant_text_from_responses(resp_body)

    return {
        "id": chat_id,
        "object": "chat.completion",
        "created": created_at,
        "model": resp_body.get("model"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
    }


async def chat_completions_sse_to_responses_sse(
    *,
    upstream: AsyncGenerator[bytes, None],
    model: str,
    response_id: Optional[str] = None,
    input_tokens: Optional[int] = None,
) -> AsyncGenerator[bytes, None]:
    """


    Convert OpenAI Chat Completions SSE stream to Responses SSE stream.





    This is a best-effort compatibility layer focused on text output deltas.


    """

    decoder = SSEDecoder()

    resp_id = response_id or _new_id("resp")

    msg_id = _new_id("msg")

    created = {
        "type": "response.created",
        "response": {
            "id": resp_id,
            "object": "response",
            "created_at": int(time.time()),
            "model": model,
            "status": "in_progress",
            "output": [
                {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": ""}],
                }
            ],
        },
    }

    yield f"event: response.created\ndata: {json.dumps(created, ensure_ascii=False)}\n\n".encode(
        "utf-8"
    )

    text_parts: list[str] = []

    saw_done = False

    final_usage = None

    async for chunk in upstream:
        for payload in decoder.feed(chunk):
            if not payload:
                continue

            if payload.strip() == "[DONE]":
                saw_done = True

                break

            try:
                data = json.loads(payload)

            except Exception:
                continue

            # Try to extract usage from upstream if available (e.g. stream_options: {include_usage: true})

            if "usage" in data and data["usage"]:
                final_usage = data["usage"]

            choices = data.get("choices")

            if not isinstance(choices, list):
                continue

            for choice in choices:
                if not isinstance(choice, dict):
                    continue

                delta = (
                    choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                )

                content = delta.get("content")

                if isinstance(content, str) and content:
                    text_parts.append(content)

                    evt = {
                        "type": "response.output_text.delta",
                        "delta": content,
                        "output_index": 0,
                        "content_index": 0,
                        "item_id": msg_id,
                    }

                    yield f"event: response.output_text.delta\ndata: {json.dumps(evt, ensure_ascii=False)}\n\n".encode(
                        "utf-8"
                    )

        if saw_done:
            break

    final_text = "".join(text_parts)

    # Calculate usage if not provided by upstream

    if not final_usage:
        token_counter = get_token_counter("openai")

        output_tokens = token_counter.count_tokens(final_text, model)

        total_input = input_tokens or 0

        final_usage = {
            "input_tokens": total_input,
            "output_tokens": output_tokens,
            "total_tokens": total_input + output_tokens,
        }

    else:
        # Normalize usage keys

        if "prompt_tokens" in final_usage:
            final_usage = {
                "input_tokens": final_usage.get("prompt_tokens", 0),
                "output_tokens": final_usage.get("completion_tokens", 0),
                "total_tokens": final_usage.get("total_tokens", 0),
            }

    completed = {
        "type": "response.completed",
        "response": {
            "id": resp_id,
            "object": "response",
            "created_at": int(time.time()),
            "model": model,
            "status": "completed",
            "output": [
                {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": final_text}],
                }
            ],
            "usage": final_usage,
        },
    }

    yield f"event: response.completed\ndata: {json.dumps(completed, ensure_ascii=False)}\n\n".encode(
        "utf-8"
    )


async def responses_sse_to_chat_completions_sse(
    *,
    upstream: AsyncGenerator[bytes, None],
    model: str,
    response_id: Optional[str] = None,
) -> AsyncGenerator[bytes, None]:
    """
    Convert OpenAI Responses SSE stream to Chat Completions SSE stream.
    """
    decoder = SSEDecoder()
    resp_id = response_id or _new_id("chatcmpl")
    sent_role = False
    done = False

    # Track tool calls state
    # item_id -> index
    tool_call_indices: dict[str, int] = {}
    next_tool_index = 0

    async for chunk in upstream:
        for payload in decoder.feed(chunk):
            if not payload:
                continue
            if payload.strip() == "[DONE]":
                if not done:
                    yield b"data: [DONE]\n\n"
                    done = True
                continue

            try:
                data = json.loads(payload)
            except Exception:
                continue

            event_type = data.get("type")
            if event_type == "response.created":
                response = data.get("response")
                if isinstance(response, dict) and isinstance(response.get("id"), str):
                    resp_id = response["id"]
                continue

            if event_type == "response.output_item.added":
                item = data.get("item")
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "function_call":
                    item_id = data.get("item_id") or item.get("id")
                    if not item_id:
                        continue

                    tool_index = next_tool_index
                    next_tool_index += 1
                    tool_call_indices[item_id] = tool_index

                    call_id = item.get("call_id")
                    name = item.get("name")

                    delta: dict[str, Any] = {
                        "tool_calls": [
                            {
                                "index": tool_index,
                                "id": call_id,
                                "type": "function",
                                "function": {"name": name, "arguments": ""},
                            }
                        ]
                    }
                    if not sent_role:
                        delta["role"] = "assistant"
                        sent_role = True

                    payload_obj = {
                        "id": resp_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": delta, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(payload_obj, ensure_ascii=False)}\n\n".encode(
                        "utf-8"
                    )
                continue

            if event_type == "response.function_call_arguments.delta":
                item_id = data.get("item_id")
                delta_args = data.get("delta")
                if item_id in tool_call_indices and delta_args:
                    tool_index = tool_call_indices[item_id]
                    delta = {
                        "tool_calls": [
                            {"index": tool_index, "function": {"arguments": delta_args}}
                        ]
                    }
                    if not sent_role:
                        delta["role"] = "assistant"
                        sent_role = True

                    payload_obj = {
                        "id": resp_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": delta, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(payload_obj, ensure_ascii=False)}\n\n".encode(
                        "utf-8"
                    )
                continue

            if event_type == "response.output_text.delta":
                delta_text = data.get("delta")
                if isinstance(delta_text, str) and delta_text:
                    delta = {"content": delta_text}
                    if not sent_role:
                        delta["role"] = "assistant"
                        sent_role = True
                    payload_obj = {
                        "id": resp_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": delta, "finish_reason": None}
                        ],
                    }
                    yield f"data: {json.dumps(payload_obj, ensure_ascii=False)}\n\n".encode(
                        "utf-8"
                    )
                continue

            if event_type == "response.output_item.done":
                # Check if it was a function call item to send finish_reason="tool_calls"?
                # But typically OpenAI Chat stream sends finish_reason in a separate chunk or with last delta.
                # OpenAI Responses `response.completed` is safer for final finish_reason.
                # However, if we have tool calls, the chat stream usually expects `finish_reason: tool_calls`
                item = data.get("item")
                if isinstance(item, dict) and item.get("type") == "function_call":
                    # We could signal tool_calls finish reason here if we knew this was the last one,
                    # but response.completed is better for overall finish.
                    pass
                continue

            if event_type == "response.completed":
                # Determine finish reason based on usage or context?
                # Default to "stop" if not tool calls?
                # If we processed tool calls, it should probably be "tool_calls".
                finish_reason = "tool_calls" if next_tool_index > 0 else "stop"

                payload_obj = {
                    "id": resp_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {"index": 0, "delta": {}, "finish_reason": finish_reason}
                    ],
                }
                yield f"data: {json.dumps(payload_obj, ensure_ascii=False)}\n\n".encode(
                    "utf-8"
                )
                if not done:
                    yield b"data: [DONE]\n\n"
                    done = True
                continue

    if not done:
        yield b"data: [DONE]\n\n"
