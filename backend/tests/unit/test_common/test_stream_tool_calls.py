"""Exercise the real gateway entry point for OpenAI -> Anthropic tool streams."""

import asyncio
import json

import pytest

from app.common.protocol_conversion import convert_stream_for_user
from app.common.errors import ServiceError


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
