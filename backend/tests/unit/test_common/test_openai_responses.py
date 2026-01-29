import json

import pytest

from app.common.openai_responses import (
    chat_completion_to_responses_response,
    chat_completions_request_to_responses,
    chat_completions_sse_to_responses_sse,
    responses_request_to_chat_completions,
    responses_response_to_chat_completion,
    responses_sse_to_chat_completions_sse,
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


def test_chat_completions_request_to_responses_system_and_user():
    responses = chat_completions_request_to_responses(
        {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "hello"},
            ],
            "max_tokens": 42,
        }
    )
    assert responses["instructions"] == "You are helpful"
    assert responses["input"][0]["role"] == "user"
    assert responses["input"][0]["content"][0]["type"] == "input_text"
    assert responses["max_output_tokens"] == 42


def test_chat_completion_to_responses_response_usage_mapping():
    resp = chat_completion_to_responses_response(
        {
            "id": "chatcmpl_123",
            "object": "chat.completion",
            "created": 123456,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
        }
    )
    assert resp["object"] == "response"
    assert resp["created_at"] == 123456
    assert resp["usage"] == {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}
    assert resp["output"][0]["type"] == "message"
    assert resp["output"][0]["content"][0]["type"] == "output_text"
    assert resp["output"][0]["content"][0]["text"] == "Hello"


def test_responses_response_to_chat_completion_usage_mapping():
    chat = responses_response_to_chat_completion(
        {
            "id": "resp_1",
            "object": "response",
            "created_at": 123456,
            "model": "gpt-4o-mini",
            "output": [
                {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Hello"}],
                }
            ],
            "usage": {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8},
        }
    )
    assert chat["object"] == "chat.completion"
    assert chat["created"] == 123456
    assert chat["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 5,
        "total_tokens": 8,
    }
    assert chat["choices"][0]["message"]["content"] == "Hello"


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
    async for chunk in chat_completions_sse_to_responses_sse(
        upstream=upstream(), model="gpt-4o-mini"
    ):
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


@pytest.mark.asyncio
async def test_responses_sse_to_chat_completions_sse_text_delta():
    async def upstream():
        yield (
            b'data: {"type":"response.created","response":{"id":"resp_1","object":"response","created_at":1,"model":"gpt-4o-mini"}}\n\n'
        )
        yield b'data: {"type":"response.output_text.delta","delta":"Hel"}\n\n'
        yield b'data: {"type":"response.output_text.delta","delta":"lo"}\n\n'
        yield b'data: {"type":"response.completed"}\n\n'

    out_chunks: list[bytes] = []
    async for chunk in responses_sse_to_chat_completions_sse(
        upstream=upstream(), model="gpt-4o-mini"
    ):
        out_chunks.append(chunk)

    decoder = SSEDecoder()
    payloads: list[str] = []
    for chunk in out_chunks:
        payloads.extend(decoder.feed(chunk))

    assert payloads[-1].strip() == "[DONE]"
    content_payloads = [p for p in payloads if p.strip() not in ("", "[DONE]")]
    chunk_obj = json.loads(
        next(p for p in content_payloads if '"chat.completion.chunk"' in p)
    )
    assert chunk_obj["choices"][0]["delta"]["content"] == "Hel"


def test_chat_completions_request_to_responses_strips_stream_options():
    """Test that stream_options is not passed through to Responses API.

    OpenAI Responses API does not support stream_options parameter.
    Some providers will return an error if include_usage is present.
    """
    responses = chat_completions_request_to_responses(
        {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.5,
        }
    )
    assert "stream_options" not in responses
    assert responses["stream"] is True
    assert responses["temperature"] == 0.5


def test_responses_request_to_chat_completions_strips_stream_options():
    """Test that stream_options is not passed through to Chat Completions API.

    Some OpenAI-compatible providers do not support stream_options parameter
    and will return an error if include_usage is present.
    """
    chat = responses_request_to_chat_completions(
        {
            "model": "gpt-4o-mini",
            "input": "hello",
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.5,
        }
    )
    assert "stream_options" not in chat
    assert chat["stream"] is True
    assert chat["temperature"] == 0.5
