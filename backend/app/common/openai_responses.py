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
        if all(isinstance(x, dict) and ("role" in x or x.get("type") == "message") for x in input_value):
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
        role = input_value.get("role") if isinstance(input_value.get("role"), str) else "user"
        content = (
            _coerce_content_blocks(input_value.get("content"))
            if "content" in input_value
            else (input_value.get("text") if isinstance(input_value.get("text"), str) else "")
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
            if isinstance(block.get("image_url"), dict) and isinstance(block["image_url"].get("url"), str):
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
        "stream_options",
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

    if "max_output_tokens" in body and "max_tokens" not in chat_body and "max_completion_tokens" not in chat_body:
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
            if isinstance(item, dict) and item.get("type") in ("text", "output_text") and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def chat_completion_to_responses_response(chat_body: dict[str, Any]) -> dict[str, Any]:
    """
    Translate `/v1/chat/completions` response body into `/v1/responses` response body.
    """
    created_at = chat_body.get("created")
    if not isinstance(created_at, int):
        created_at = int(time.time())

    chat_id = chat_body.get("id")
    resp_id = f"resp_{chat_id}" if isinstance(chat_id, str) and chat_id else _new_id("resp")
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


async def chat_completions_sse_to_responses_sse(
    *,
    upstream: AsyncGenerator[bytes, None],
    model: str,
    response_id: Optional[str] = None,
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
                {"id": msg_id, "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": ""}]}
            ],
        },
    }
    yield f"data: {json.dumps(created, ensure_ascii=False)}\n\n".encode("utf-8")

    text_parts: list[str] = []
    saw_done = False

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

            choices = data.get("choices")
            if not isinstance(choices, list):
                continue

            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
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
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n".encode("utf-8")

        if saw_done:
            break

    final_text = "".join(text_parts)
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
            "usage": None,
        },
    }
    yield f"data: {json.dumps(completed, ensure_ascii=False)}\n\n".encode("utf-8")
    yield b"data: [DONE]\n\n"

