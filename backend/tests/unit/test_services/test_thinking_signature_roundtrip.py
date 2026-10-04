"""Signed Anthropic thinking survives an OpenAI-protocol client (GUL-201).

OpenAI client -> gateway -> Anthropic-protocol upstream (Anthropic/MiniMax):
the upstream's signed thinking must come back verbatim on the next tool turn.
"""

import json

import pytest

from app.common.protocol_conversion import (
    convert_request_for_supplier,
    convert_response_for_user,
    convert_stream_for_user,
)
from app.common.stream_usage import SSEDecoder
from app.common.time import utc_now
from app.domain.kv_store import KeyValueModel
from app.services.protocol_hooks import ProtocolConversionHooks


class DictKV:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def get(self, key):
        if key not in self.data:
            return None
        now = utc_now()
        return KeyValueModel(
            key=key, value=self.data[key], expires_at=None, created_at=now, updated_at=now
        )

    async def set(self, key, value, ttl_seconds=None):
        self.data[key] = value


async def _agen(chunks):
    for c in chunks:
        yield c


def _sse(events):
    return [f"data: {json.dumps(e)}\n\n".encode() for e in events]


TOOL = {
    "type": "function",
    "function": {"name": "web_fetch", "parameters": {"type": "object", "properties": {}}},
}

ANTHROPIC_TOOL_TURN = [
    {"type": "message_start", "message": {"id": "msg_1", "usage": {"input_tokens": 3}}},
    {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "thinking", "thinking": "", "signature": ""},
    },
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "thinking_delta", "thinking": "Need to "},
    },
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "thinking_delta", "thinking": "fetch."},
    },
    {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "signature_delta", "signature": "SIG-1"},
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
        "delta": {"type": "text_delta", "text": "Looking it up."},
    },
    {"type": "content_block_stop", "index": 1},
    {
        "type": "content_block_start",
        "index": 2,
        "content_block": {"type": "tool_use", "id": "toolu_1", "name": "web_fetch", "input": {}},
    },
    {
        "type": "content_block_delta",
        "index": 2,
        "delta": {"type": "input_json_delta", "partial_json": '{"url":"https://a.b"}'},
    },
    {"type": "content_block_stop", "index": 2},
    {
        "type": "message_delta",
        "delta": {"stop_reason": "tool_use"},
        "usage": {"output_tokens": 9},
    },
    {"type": "message_stop"},
]


@pytest.mark.asyncio
@pytest.mark.parametrize("supplier", ["anthropic", "minimax"])
async def test_stream_thinking_signature_round_trip_through_openai_client(supplier):
    kv = DictKV()
    hooks = ProtocolConversionHooks(kv_repo=kv)

    # 1. Upstream stream -> OpenAI client, passing through the response hook.
    out = b""
    async for chunk in convert_stream_for_user(
        request_protocol="openai",
        supplier_protocol="anthropic",
        upstream=_agen(_sse(ANTHROPIC_TOOL_TURN)),
        model="MiniMax-M3",
    ):
        out += await hooks.after_stream_chunk_conversion(chunk, "openai", "anthropic")

    chunks = [json.loads(p) for p in SSEDecoder().feed(out) if p.strip() != "[DONE]"]
    tool_deltas = [
        tc
        for c in chunks
        for choice in c.get("choices", [])
        for tc in choice["delta"].get("tool_calls", [])
    ]
    expected_blocks = [
        {"type": "thinking", "thinking": "Need to fetch.", "signature": "SIG-1"}
    ]
    assert tool_deltas[0]["extra_content"] == {
        "anthropic": {"thinking_blocks": expected_blocks}
    }
    # Signed blocks are cached by tool_call_id; converted reasoning is not
    # cached per delta (it is never replayed to Anthropic upstreams).
    assert json.loads(kv.data["tool_call_extra:toolu_1"]) == {
        "anthropic": {"thinking_blocks": expected_blocks}
    }
    assert not any(k.startswith("chat_reasoning:") for k in kv.data)

    # 2. The client sends the history back WITHOUT extra_content.
    next_request = {
        "model": "coding/minimax",
        "max_tokens": 16384,
        "reasoning_effort": "high",
        "tools": [TOOL],
        "messages": [
            {"role": "user", "content": "Read a.b"},
            {
                "role": "assistant",
                "content": "Looking it up.",
                "tool_calls": [
                    {
                        "id": "toolu_1",
                        "type": "function",
                        "function": {"name": "web_fetch", "arguments": '{"url":"https://a.b"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "toolu_1", "content": "page"},
        ],
    }
    hooked = await hooks.before_request_conversion(next_request, "openai", "anthropic")
    _, supplier_body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol=supplier,
        path="/v1/chat/completions",
        body=hooked,
        target_model="MiniMax-M3",
    )
    supplier_body = await hooks.after_request_conversion(
        supplier_body, "openai", "anthropic"
    )

    assistant = supplier_body["messages"][1]
    assert assistant["role"] == "assistant"
    assert [b["type"] for b in assistant["content"]] == ["thinking", "text", "tool_use"]
    assert assistant["content"][0] == expected_blocks[0]


def test_non_stream_interleaved_thinking_rides_on_each_tool_call():
    out = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="anthropic",
        body={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "m",
            "content": [
                {"type": "thinking", "thinking": "a", "signature": "S1"},
                {"type": "redacted_thinking", "data": "R1"},
                {"type": "tool_use", "id": "t1", "name": "f", "input": {}},
                {"type": "thinking", "thinking": "b", "signature": "S2"},
                {"type": "tool_use", "id": "t2", "name": "f", "input": {}},
                {"type": "tool_use", "id": "t3", "name": "f", "input": {}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        },
        target_model="m",
    )

    calls = out["choices"][0]["message"]["tool_calls"]
    assert calls[0]["extra_content"]["anthropic"]["thinking_blocks"] == [
        {"type": "thinking", "thinking": "a", "signature": "S1"},
        {"type": "redacted_thinking", "data": "R1"},
    ]
    assert calls[1]["extra_content"]["anthropic"]["thinking_blocks"] == [
        {"type": "thinking", "thinking": "b", "signature": "S2"},
    ]
    assert "extra_content" not in calls[2]

    # Replaying that message rebuilds the original block order.
    _, body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/chat/completions",
        body={
            "model": "m",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": "hi"}, out["choices"][0]["message"]],
        },
        target_model="m",
    )
    content = body["messages"][1]["content"]
    assert [(b["type"], b.get("id")) for b in content] == [
        ("thinking", None),
        ("redacted_thinking", None),
        ("tool_use", "t1"),
        ("thinking", None),
        ("tool_use", "t2"),
        ("tool_use", "t3"),
    ]


def test_unsigned_thinking_is_not_carried():
    out = convert_response_for_user(
        request_protocol="openai",
        supplier_protocol="anthropic",
        body={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "m",
            "content": [
                {"type": "thinking", "thinking": "a", "signature": ""},
                {"type": "tool_use", "id": "t1", "name": "f", "input": {}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        },
        target_model="m",
    )

    message = out["choices"][0]["message"]
    assert message["reasoning_content"] == "a"
    assert "extra_content" not in message["tool_calls"][0]


@pytest.mark.parametrize(
    "extra",
    [
        "bad",
        {"anthropic": "bad"},
        {"anthropic": {"thinking_blocks": "bad"}},
        {
            "anthropic": {
                "thinking_blocks": [
                    "bad",
                    {"type": "thinking", "thinking": "x"},
                    {"type": "thinking", "thinking": "x", "signature": ""},
                    {"type": "redacted_thinking", "data": ""},
                    {"type": "other"},
                ]
            }
        },
    ],
)
def test_malformed_carried_thinking_is_ignored(extra):
    _, body = convert_request_for_supplier(
        request_protocol="openai",
        supplier_protocol="anthropic",
        path="/v1/chat/completions",
        body={
            "model": "m",
            "max_tokens": 100,
            "messages": [
                {"role": "user", "content": "hi"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "t1",
                            "type": "function",
                            "function": {"name": "f", "arguments": "{}"},
                            "extra_content": extra,
                        }
                    ],
                },
            ],
        },
        target_model="m",
    )

    assert [b["type"] for b in body["messages"][1]["content"]] == ["tool_use"]


@pytest.mark.asyncio
async def test_openai_upstream_never_receives_anthropic_signatures():
    hooks = ProtocolConversionHooks()
    body = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "t1",
                        "extra_content": {
                            "anthropic": {"thinking_blocks": [{"type": "thinking"}]},
                            "google": {"thought_signature": "g"},
                        },
                    },
                    {
                        "id": "t2",
                        "extra_content": {"anthropic": {"thinking_blocks": []}},
                    },
                    {"id": "t3"},
                ],
            },
            {"role": "user", "content": "x"},
        ]
    }

    out = await hooks.after_request_conversion(body, "openai", "openai")

    calls = out["messages"][0]["tool_calls"]
    assert calls[0]["extra_content"] == {"google": {"thought_signature": "g"}}
    assert "extra_content" not in calls[1]
    assert "extra_content" not in calls[2]


@pytest.mark.asyncio
async def test_anthropic_upstream_keeps_carried_signatures_in_hook():
    hooks = ProtocolConversionHooks()
    body = {"messages": [{"role": "user", "content": "x"}]}

    assert await hooks.after_request_conversion(body, "openai", "anthropic") == body
