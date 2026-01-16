import json

import pytest

from app.common.openai_responses import (
    chat_completion_to_responses_response,
    chat_completions_sse_to_responses_sse,
    responses_request_to_chat_completions,
)
from app.common.stream_usage import SSEDecoder


def test_responses_request_to_chat_completions_string_input_and_instructions():
    chat = responses_request_to_chat_completions(
        {
            "model": "gpt-4o-mini",
            "instructions": "You are a helpful assistant.",
            "input": "hello",
            "max_output_tokens": 123,
            "temperature": 0.2,
        }
    )
    assert chat["model"] == "gpt-4o-mini"
    assert chat["max_completion_tokens"] == 123
    assert chat["temperature"] == 0.2
    assert chat["messages"][0]["role"] == "system"
    assert chat["messages"][1] == {"role": "user", "content": "hello"}


def test_responses_request_to_chat_completions_content_blocks():
    chat = responses_request_to_chat_completions(
        {
            "model": "gpt-4o-mini",
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                }
            ],
        }
    )
    assert chat["messages"][0]["role"] == "user"
    assert chat["messages"][0]["content"] == "hi"


def test_chat_completion_to_responses_response_usage_mapping():
    resp = chat_completion_to_responses_response(
        {
            "id": "chatcmpl_123",
            "object": "chat.completion",
            "created": 123456,
            "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
        }
    )
    assert resp["object"] == "response"
    assert resp["created_at"] == 123456
    assert resp["usage"] == {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}
    assert resp["output"][0]["type"] == "message"
    assert resp["output"][0]["content"][0]["type"] == "output_text"
    assert resp["output"][0]["content"][0]["text"] == "Hello"


@pytest.mark.asyncio
async def test_chat_completions_sse_to_responses_sse_text_delta():
    async def upstream():
        yield (
            b'data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"Hel"},"finish_reason":null}],"model":"gpt-4o-mini"}\n\n'
        )
        yield (
            b'data: {"id":"chatcmpl_1","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"lo"},"finish_reason":null}],"model":"gpt-4o-mini"}\n\n'
        )
        yield b"data: [DONE]\n\n"

    out_chunks: list[bytes] = []
    async for chunk in chat_completions_sse_to_responses_sse(upstream=upstream(), model="gpt-4o-mini"):
        out_chunks.append(chunk)

    decoder = SSEDecoder()
    payloads: list[str] = []
    for chunk in out_chunks:
        payloads.extend(decoder.feed(chunk))

    assert payloads[0]
    first = json.loads(payloads[0])
    assert first["type"] == "response.created"

    delta1 = json.loads(payloads[1])
    delta2 = json.loads(payloads[2])
    assert delta1["type"] == "response.output_text.delta"
    assert delta2["type"] == "response.output_text.delta"
    assert delta1["delta"] + delta2["delta"] == "Hello"

    completed = json.loads(payloads[3])
    assert completed["type"] == "response.completed"
    assert completed["response"]["output"][0]["content"][0]["text"] == "Hello"

    assert payloads[4].strip() == "[DONE]"

