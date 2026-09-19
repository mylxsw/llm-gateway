"""Exercise the real gateway entry point for OpenAI -> Anthropic tool streams."""

import asyncio
import json

import pytest

from app.common.protocol_conversion import convert_stream_for_user
from app.common.errors import ServiceError
from app.common.protocol import converters
from starlette.responses import StreamingResponse


async def convert(deltas, *, ending="finish", usage=False, split_bytes=False):
    chunks = [
        {"choices": [{"delta": delta, "finish_reason": None}]} for delta in deltas
    ]
    if ending == "finish":
        chunks.append({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]})
    if usage:
        chunks.append(
            {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        )
    wire = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
    if ending != "eof":
        wire += "data: [DONE]\n\n"

    async def upstream():
        data = wire.encode()
        if split_bytes:
            for byte in data:
                await asyncio.sleep(0)
                yield bytes([byte])
        else:
            await asyncio.sleep(0)
            yield data

    result = b"".join(
        [
            item
            async for item in convert_stream_for_user(
                request_protocol="anthropic",
                supplier_protocol="openai",
                upstream=upstream(),
                model="test",
            )
        ]
    )
    return [
        json.loads(line[6:])
        for line in result.decode().splitlines()
        if line.startswith("data: ")
    ]


def tool(arguments, index=0, **fields):
    call = {"function": {"arguments": arguments}}
    if index is not None:
        call["index"] = index
    if "id" in fields:
        call["id"] = fields["id"]
    if "name" in fields:
        call["function"]["name"] = fields["name"]
    return call


def assemble(events):
    blocks, active = [], None
    for event in events:
        kind = event["type"]
        if kind == "content_block_start":
            assert active is None and event["index"] == len(blocks)
            active = dict(event["content_block"], fragments="")
            if active["type"] == "tool_use":
                assert active["id"] and active["name"]
            blocks.append(active)
        elif kind == "content_block_delta":
            assert active is not None and event["index"] == len(blocks) - 1
            delta = event["delta"]
            assert delta["type"] == (
                "input_json_delta" if active["type"] == "tool_use" else "text_delta"
            )
            active["fragments"] += delta.get("partial_json", delta.get("text", ""))
        elif kind == "content_block_stop":
            assert active is not None and event["index"] == len(blocks) - 1
            if active["type"] == "tool_use":
                active["input"] = json.loads(active["fragments"])
            active = None
        elif kind in ("message_delta", "message_stop"):
            assert active is None
    assert active is None
    assert sum(event["type"] == "message_stop" for event in events) == 1
    return blocks


@pytest.mark.parametrize("index", [0, 9, None])
@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"id": "", "name": ""},
        {"id": None, "name": None},
        {"id": "call_1", "name": "Bash"},
    ],
)
@pytest.mark.parametrize("empty_content", [False, True])
async def test_empty_and_repeated_metadata_preserve_tool_input(
    index, metadata, empty_content
):
    deltas = []
    for position, fragment in enumerate(["{", '"command":"echo ok"', "}"]):
        fields = {"id": "call_1", "name": "Bash"} if position == 0 else metadata
        delta = {"tool_calls": [tool(fragment, index, **fields)]}
        if empty_content:
            delta["content"] = ""
        deltas.append(delta)
    events = await convert(deltas, usage=True, split_bytes=True)
    blocks = assemble(events)
    assert len(blocks) == 1 and blocks[0]["input"] == {"command": "echo ok"}
    assert events[-2]["delta"]["stop_reason"] == "tool_use"
    assert events[-2]["usage"] == {"input_tokens": 10, "output_tokens": 5}


@pytest.mark.parametrize("ending", ["finish", "done", "eof"])
async def test_interleaved_tools_with_text_flush_before_message_end(ending):
    events = await convert(
        [
            {"content": "before"},
            {
                "tool_calls": [
                    tool('{"a":', id="a", name="A"),
                    tool('{"b":', 1, id="b", name="B"),
                ]
            },
            {"content": "", "tool_calls": [tool("2}", 1, id="", name="")]},
            {"tool_calls": [tool("1}", id="", name="")]},
            {"content": "after"},
        ],
        ending=ending,
    )
    blocks = assemble(events)
    assert [block["type"] for block in blocks] == [
        "text",
        "tool_use",
        "tool_use",
        "text",
    ]
    assert [blocks[1]["input"], blocks[2]["input"]] == [{"a": 1}, {"b": 2}]
    assert blocks[0]["fragments"] == "before" and blocks[3]["fragments"] == "after"


async def test_metadata_can_arrive_after_arguments():
    blocks = assemble(
        await convert(
            [
                {"tool_calls": [tool('{"a":')]},
                {"tool_calls": [tool("1}", id="a")]},
                {"tool_calls": [tool("", name="A")]},
            ]
        )
    )
    assert blocks[0]["input"] == {"a": 1}


async def test_missing_metadata_fails_instead_of_emitting_empty_tool():
    with pytest.raises(ServiceError, match="without an ID or name"):
        await convert([{"tool_calls": [tool("{}")]}])


async def test_unaddressed_parallel_continuation_is_rejected():
    with pytest.raises(ServiceError, match="Ambiguous"):
        await convert(
            [
                {
                    "tool_calls": [
                        tool("{", id="a", name="A"),
                        tool("{", 1, id="b", name="B"),
                    ]
                },
                {"tool_calls": [tool("}", None)]},
            ]
        )


async def test_first_tool_emits_before_reading_the_next_upstream_chunk():
    read_second_chunk = False

    async def upstream():
        nonlocal read_second_chunk
        yield (
            "data: "
            + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [tool("{", id="a", name="A")],
                            }
                        }
                    ]
                }
            )
            + "\n\n"
        ).encode()
        read_second_chunk = True
        yield (
            "data: "
            + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [tool("}")],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
            )
            + "\n\n"
        ).encode()

    stream = convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        upstream=upstream(),
        model="test",
    )
    try:
        for expected in ["message_start", "content_block_start", "content_block_delta"]:
            output = await anext(stream)
            assert f"event: {expected}".encode() in output
            assert not read_second_chunk
        remaining = [output async for output in stream]
        assert b'"message_stop"' in remaining[-1]
    finally:
        await stream.aclose()


async def test_simultaneous_requests_do_not_share_tool_state():
    outputs = await asyncio.gather(
        *[
            convert(
                [
                    {
                        "tool_calls": [
                            tool(json.dumps({"value": i}), id=f"call_{i}", name="Tool")
                        ]
                    }
                ]
            )
            for i in range(3)
        ]
    )
    for i, events in enumerate(outputs):
        blocks = assemble(events)
        assert len(blocks) == 1
        assert blocks[0]["id"] == f"call_{i}" and blocks[0]["input"] == {"value": i}


def sse(delta, finish=None):
    return (
        "data: "
        + json.dumps({"choices": [{"delta": delta, "finish_reason": finish}]})
        + "\n\n"
    ).encode()


async def test_buffered_tool_sends_heartbeats_without_changing_content(monkeypatch):
    monkeypatch.setattr(converters, "ANTHROPIC_HEARTBEAT_INTERVAL_SECONDS", 0.005)
    release, buffered, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def upstream():
        try:
            yield sse({"tool_calls": [tool("{}", id="a", name="A")]})
            yield sse({"tool_calls": [tool("{", 1, id="b", name="B")]})
            yield sse({"tool_calls": [tool('"value":1', 1)]})
            buffered.set()
            await release.wait()
            yield sse({"tool_calls": [tool("}", 1)]}, "tool_calls")
            yield b'data: {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}\n\n'
        finally:
            closed.set()

    stream = convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        upstream=upstream(),
        model="test",
    )
    events = []
    try:
        for _ in range(10):
            event_bytes = await asyncio.wait_for(anext(stream), 1)
            event = json.loads(
                next(
                    line[6:]
                    for line in event_bytes.decode().splitlines()
                    if line.startswith("data: ")
                )
            )
            events.append(event)
            if event["type"] == "ping":
                break
        assert events[-1] == {"type": "ping"} and buffered.is_set()
        assert sum(event["type"] == "content_block_start" for event in events) == 1
        assert b"event: ping" in await asyncio.wait_for(anext(stream), 1)
        assert not closed.is_set()
        release.set()
        async for data in stream:
            events.append(
                json.loads(
                    next(
                        line[6:]
                        for line in data.decode().splitlines()
                        if line.startswith("data: ")
                    )
                )
            )
        assert [block["input"] for block in assemble(events)] == [{}, {"value": 1}]
        assert events[-2]["usage"] == {"input_tokens": 10, "output_tokens": 5}
        assert events[-2]["delta"]["stop_reason"] == "tool_use"
        assert closed.is_set()
    finally:
        await stream.aclose()


@pytest.mark.parametrize("supplier", ["openai", "openai_responses", "gemini"])
@pytest.mark.parametrize("cancel_read", [False, True])
async def test_public_stream_disconnect_closes_upstream(
    monkeypatch, supplier, cancel_read
):
    monkeypatch.setattr(
        converters, "ANTHROPIC_HEARTBEAT_INTERVAL_SECONDS", 60 if cancel_read else 0.005
    )
    reading, closed = asyncio.Event(), asyncio.Event()

    async def upstream():
        try:
            reading.set()
            await asyncio.Event().wait()
            yield b"unreachable"
        finally:
            closed.set()

    stream = convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol=supplier,
        upstream=upstream(),
        model="test",
    )
    if cancel_read:
        consumer = asyncio.create_task(anext(stream))
        await asyncio.wait_for(reading.wait(), 1)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
    else:
        assert b"event: ping" in await asyncio.wait_for(anext(stream), 1)
        await stream.aclose()
    assert closed.is_set()


async def test_buffer_overflow_closes_upstream_and_returns_conversion_error(
    monkeypatch,
):
    original = converters.OpenAIChatStreamBlocks
    monkeypatch.setattr(
        converters, "OpenAIChatStreamBlocks", lambda: original(max_buffer_bytes=8)
    )
    closed = asyncio.Event()

    async def upstream():
        try:
            yield sse({"tool_calls": [tool("{}", id="a", name="A")]})
            yield sse({"tool_calls": [tool("x" * 9, 1, id="b", name="B")]})
            pytest.fail("Overflow must stop reading upstream")
        finally:
            closed.set()

    with pytest.raises(ServiceError, match="byte limit"):
        async for _ in convert_stream_for_user(
            request_protocol="anthropic",
            supplier_protocol="openai",
            upstream=upstream(),
            model="test",
        ):
            pass
    assert closed.is_set()


async def test_http_disconnect_during_ping_waits_for_async_upstream_cleanup(
    monkeypatch,
):
    monkeypatch.setattr(converters, "ANTHROPIC_HEARTBEAT_INTERVAL_SECONDS", 0.005)
    disconnected, closed = asyncio.Event(), asyncio.Event()

    async def upstream():
        try:
            await asyncio.Event().wait()
            yield b"unreachable"
        finally:
            # Network clients can suspend while releasing their connection.
            await asyncio.sleep(0.01)
            closed.set()

    async def receive():
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if b"event: ping" in message.get("body", b""):
            disconnected.set()

    stream = convert_stream_for_user(
        request_protocol="anthropic",
        supplier_protocol="openai",
        upstream=upstream(),
        model="test",
    )
    response = StreamingResponse(stream, media_type="text/event-stream")
    await asyncio.wait_for(
        response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send), 1
    )
    assert closed.is_set()
