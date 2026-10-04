"""Thinking/reasoning compatibility across protocol conversion (GUL-201)."""

import json

import pytest

from app.common.protocol_conversion import (
    convert_request_for_supplier,
    convert_response_for_user,
    convert_stream_for_user,
)
from app.common.reasoning import (
    normalize_reasoning_for_anthropic,
    normalize_reasoning_for_openai,
)
from app.common.stream_usage import SSEDecoder


def _chat_body(**extra):
    body = {
        "model": "any",
        "messages": [{"role": "user", "content": "Hi"}],
    }
    body.update(extra)
    return body


def _to_anthropic(body):
    return convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/chat/completions",
        body=body,
        target_model="MiniMax-M3",
    )


# --- request: OpenAI Chat `reasoning_effort` -------------------------------


def test_openai_chat_reasoning_effort_reaches_anthropic_supplier():
    """The reported case: Chat `reasoning_effort` was dropped for Anthropic."""
    path, out = _to_anthropic(
        _chat_body(
            reasoning_effort="high",
            max_tokens=16384,
            stream=True,
            temperature=0.3,
            top_p=0.5,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "web_fetch",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )
    )

    assert path == "/v1/messages"
    assert out["thinking"] == {"type": "enabled", "budget_tokens": 12288}
    assert out["output_config"] == {"effort": "high"}
    assert "reasoning_effort" not in out
    assert "reasoning" not in out
    # Anthropic rejects these while thinking is enabled.
    assert "temperature" not in out
    assert "top_p" not in out


def test_openai_chat_reasoning_effort_none_disables_anthropic_thinking():
    _, out = _to_anthropic(_chat_body(reasoning_effort="none", max_tokens=1000))

    assert out["thinking"] == {"type": "disabled"}
    assert "output_config" not in out


def test_openai_chat_reasoning_effort_skips_thinking_when_tool_use_forced():
    _, out = _to_anthropic(
        _chat_body(
            reasoning_effort="low",
            max_tokens=8000,
            tool_choice="required",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "f",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        )
    )

    assert out["tool_choice"]["type"] == "any"
    assert "thinking" not in out
    assert out["output_config"] == {"effort": "low"}


def test_openai_chat_reasoning_effort_skips_thinking_when_max_tokens_too_small():
    _, out = _to_anthropic(_chat_body(reasoning_effort="medium", max_tokens=1024))

    assert "thinking" not in out
    assert out["output_config"] == {"effort": "medium"}


@pytest.mark.parametrize(
    ("effort", "max_tokens", "budget"),
    [
        ("minimal", 64000, 2048),
        ("low", 64000, 2048),
        ("medium", 64000, 8192),
        ("high", 64000, 16384),
        ("xhigh", 64000, 32768),
        ("high", 1100, 1024),
    ],
)
def test_openai_chat_reasoning_effort_budget_mapping(effort, max_tokens, budget):
    _, out = _to_anthropic(_chat_body(reasoning_effort=effort, max_tokens=max_tokens))

    assert out["thinking"] == {"type": "enabled", "budget_tokens": budget}
    assert out["thinking"]["budget_tokens"] < max_tokens


def test_openai_chat_reasoning_effort_keeps_temperature_one():
    _, out = _to_anthropic(
        _chat_body(reasoning_effort="high", max_tokens=20000, temperature=1, top_p=0.97)
    )

    assert out["temperature"] == 1
    assert out["top_p"] == 0.97


@pytest.mark.parametrize(
    ("supplier", "field", "expected"),
    [
        ("deepseek", "thinking", {"type": "enabled"}),
        ("moonshot", "thinking", {"type": "enabled"}),
        ("aliyun", "enable_thinking", True),
    ],
)
def test_openai_chat_reasoning_effort_reaches_vendor_thinking_switch(
    supplier, field, expected
):
    _, out = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol=supplier,
        path="/v1/chat/completions",
        body=_chat_body(reasoning_effort="high"),
        target_model="m",
    )

    assert out[field] == expected
    assert "reasoning_effort" not in out
    assert "reasoning" not in out


def test_openai_chat_reasoning_effort_none_disables_vendor_thinking():
    _, out = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="deepseek",
        path="/v1/chat/completions",
        body=_chat_body(reasoning_effort="none"),
        target_model="deepseek-chat",
    )

    assert out["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in out


def test_openai_chat_reasoning_effort_maps_to_responses_reasoning():
    path, out = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai_responses",
        path="/v1/chat/completions",
        body=_chat_body(reasoning_effort="low"),
        target_model="gpt-5-mini",
    )

    assert path == "/v1/responses"
    assert out["reasoning"] == {"effort": "low"}
    assert "reasoning_effort" not in out


def test_identity_openai_chat_keeps_reasoning_effort():
    _, out = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai",
        path="/v1/chat/completions",
        body=_chat_body(reasoning_effort="high"),
        target_model="gpt-5-mini",
    )

    assert out["reasoning_effort"] == "high"
    assert "reasoning" not in out


def test_identity_openai_chat_moves_reasoning_object_effort_but_keeps_other_keys():
    _, out = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="openai",
        path="/v1/chat/completions",
        body=_chat_body(reasoning={"effort": "low", "summary": "auto"}),
        target_model="gpt-5-mini",
    )

    assert out["reasoning_effort"] == "low"
    assert out["reasoning"] == {"summary": "auto"}


def test_anthropic_to_responses_uses_reasoning_object():
    path, out = convert_request_for_supplier(
        request_protocol="anthropic",
        supplier_protocol="openai_responses",
        path="/v1/messages",
        body={
            "model": "any",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 100,
            "thinking": {"type": "enabled", "budget_tokens": 50},
            "output_config": {"effort": "low"},
        },
        target_model="gpt-5-mini",
    )

    assert path == "/v1/responses"
    assert out["reasoning"]["effort"] == "low"
    assert "reasoning_effort" not in out


def test_normalize_openai_explicit_api_overrides_inference():
    out = normalize_reasoning_for_openai(
        {"messages": [], "reasoning_effort": "high"}, api="responses"
    )

    assert out == {"messages": [], "reasoning": {"effort": "high"}}


# --- request: Anthropic thinking budget -----------------------------------


def test_anthropic_explicit_budget_is_preserved():
    out = normalize_reasoning_for_anthropic(
        {
            "max_tokens": 4000,
            "temperature": 0.2,
            "thinking": {"type": "enabled", "budget_tokens": 2000},
        }
    )

    assert out["thinking"] == {"type": "enabled", "budget_tokens": 2000}
    # Client-authored Anthropic params are not rewritten.
    assert out["temperature"] == 0.2


def test_anthropic_enabled_without_budget_gets_one():
    out = normalize_reasoning_for_anthropic(
        {"max_tokens": 32000, "thinking": {"type": "enabled"}}
    )

    assert out["thinking"] == {"type": "enabled", "budget_tokens": 8192}


def test_anthropic_enabled_without_max_tokens_uses_effort_budget():
    out = normalize_reasoning_for_anthropic({"reasoning_effort": "low"})

    assert out["thinking"] == {"type": "enabled", "budget_tokens": 2048}


def test_anthropic_disabled_drops_stale_budget():
    out = normalize_reasoning_for_anthropic(
        {"max_tokens": 4000, "thinking": {"type": "enabled", "budget_tokens": 2000}},
        source_body={"reasoning_effort": "none"},
    )

    assert out["thinking"] == {"type": "disabled"}

    out = normalize_reasoning_for_anthropic(
        {"max_tokens": 4000, "thinking": {"type": "enabled", "budget_tokens": 2000}},
        source_body={"thinking": {"type": "disabled"}},
    )
    assert out["thinking"] == {"type": "disabled"}


def test_anthropic_adaptive_needs_no_budget():
    out = normalize_reasoning_for_anthropic(
        {"max_tokens": 4000, "thinking": {"type": "adaptive"}}
    )

    assert out["thinking"] == {"type": "adaptive"}


# --- response: thinking <-> reasoning_content ------------------------------


async def _agen(chunks):
    for c in chunks:
        yield c


def _sse(events):
    return [f"data: {json.dumps(e)}\n\n".encode() for e in events]


async def _collect(stream):
    out = b""
    async for chunk in stream:
        out += chunk
    return [
        json.loads(p) for p in SSEDecoder().feed(out) if p.strip() != "[DONE]"
    ]


@pytest.mark.asyncio
async def test_stream_anthropic_thinking_becomes_reasoning_content():
    upstream = _agen(
        _sse(
            [
                {
                    "type": "message_start",
                    "message": {"id": "msg_1", "usage": {"input_tokens": 3}},
                },
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "thinking", "thinking": "Let"},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": " me think"},
                },
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "signature_delta", "signature": "sig"},
                },
                {"type": "content_block_stop", "index": 0},
                {
                    "type": "content_block_start",
                    "index": 1,
                    "content_block": {"type": "text", "text": ""},
                },
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "text_delta", "text": "Answer"},
                },
                {"type": "content_block_stop", "index": 1},
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn"},
                    "usage": {"output_tokens": 5},
                },
                {"type": "message_stop"},
            ]
        )
    )

    chunks = await _collect(
        convert_stream_for_user(
            request_protocol="openai",
            supplier_protocol="anthropic",
            upstream=upstream,
            model="MiniMax-M3",
        )
    )
    deltas = [c["choices"][0]["delta"] for c in chunks if c.get("choices")]

    reasoning = "".join(d.get("reasoning_content", "") for d in deltas)
    content = "".join(d.get("content") or "" for d in deltas)
    assert reasoning == "Let me think"
    assert content == "Answer"
    assert deltas[0]["role"] == "assistant"
    assert sum(1 for d in deltas if "role" in d) == 1


@pytest.mark.asyncio
async def test_stream_openai_reasoning_content_becomes_anthropic_thinking():
    def chunk(delta, finish=None):
        return {
            "id": "c1",
            "object": "chat.completion.chunk",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }

    upstream = _agen(
        _sse(
            [
                chunk({"role": "assistant", "reasoning_content": "Hmm"}),
                chunk({"reasoning_content": ", ok"}),
                chunk({"content": "Done"}),
                chunk({}, "stop"),
            ]
        )
        + [b"data: [DONE]\n\n"]
    )

    events = await _collect(
        convert_stream_for_user(
            request_protocol="anthropic",
            supplier_protocol="openai",
            upstream=upstream,
            model="claude",
        )
    )

    starts = [e for e in events if e["type"] == "content_block_start"]
    assert [s["content_block"]["type"] for s in starts] == ["thinking", "text"]
    assert starts[0]["content_block"]["signature"] == ""
    thinking = "".join(
        e["delta"]["thinking"]
        for e in events
        if e["type"] == "content_block_delta"
        and e["delta"]["type"] == "thinking_delta"
    )
    text = "".join(
        e["delta"]["text"]
        for e in events
        if e["type"] == "content_block_delta" and e["delta"]["type"] == "text_delta"
    )
    assert thinking == "Hmm, ok"
    assert text == "Done"
    # Thinking block is closed before the text block starts.
    types = [(e["type"], e.get("index")) for e in events]
    assert types.index(("content_block_stop", 0)) < types.index(
        ("content_block_start", 1)
    )


def test_response_anthropic_thinking_becomes_reasoning_content():
    out = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="anthropic",
        body={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "MiniMax-M3",
            "content": [
                {"type": "thinking", "thinking": "reason", "signature": "s"},
                {"type": "redacted_thinking", "data": "x"},
                {"type": "text", "text": "answer"},
            ],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        },
        target_model="MiniMax-M3",
    )

    message = out["choices"][0]["message"]
    assert message["content"] == "answer"
    assert message["reasoning_content"] == "reason"


@pytest.mark.parametrize("field", ["reasoning_content", "reasoning"])
def test_response_openai_reasoning_becomes_anthropic_thinking(field):
    out = convert_response_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        body={
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "model": "deepseek-reasoner",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "answer",
                        field: "reason",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        },
        target_model="deepseek-reasoner",
    )

    assert out["content"][0] == {
        "type": "thinking",
        "thinking": "reason",
        "signature": "",
    }
    assert out["content"][1] == {"type": "text", "text": "answer"}


def test_response_without_reasoning_has_no_reasoning_content():
    out = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="anthropic",
        body={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "m",
            "content": [{"type": "text", "text": "answer"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        },
        target_model="m",
    )

    assert "reasoning_content" not in out["choices"][0]["message"]
