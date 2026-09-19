"""Regression coverage for #136: tool identity and content block lifetimes."""

import json
import random

import pytest

from api_protocol_converter import Protocol, convert_stream
from api_protocol_converter.converters import OpenAIChatDecoder
from api_protocol_converter.converters.exceptions import StreamConversionError
from api_protocol_converter.stream import StreamConverter, convert_stream_sync


def chunk(delta, finish=None):
    return {"choices": [{"delta": delta, "finish_reason": finish}]}


def tool(arguments, index=0, **metadata):
    call = {"function": {"arguments": arguments}}
    if index is not None:
        call["index"] = index
    if "id" in metadata:
        call["id"] = metadata["id"]
    if "name" in metadata:
        call["function"]["name"] = metadata["name"]
    return call


def convert(deltas, ending="finish"):
    events = [chunk(delta) for delta in deltas]
    if ending == "finish":
        events.append(chunk({}, "tool_calls"))
    events.append("data: [DONE]")
    return list(
        convert_stream(
            Protocol.OPENAI_CHAT,
            Protocol.ANTHROPIC_MESSAGES,
            iter(events),
        )
    )


def content(events):
    """Validate the consumer contract, including no delta after a block closes."""
    blocks, active = [], None
    for event in events:
        kind = event["type"]
        if kind == "content_block_start":
            assert active is None
            assert event["index"] == len(blocks)
            active = dict(event["content_block"], fragments="")
            if active["type"] == "tool_use":
                assert active["id"] and active["name"]
            blocks.append(active)
        elif kind == "content_block_delta":
            assert active is not None
            assert event["index"] == len(blocks) - 1
            delta = event["delta"]
            expected = (
                "input_json_delta" if active["type"] == "tool_use" else "text_delta"
            )
            assert delta["type"] == expected
            active["fragments"] += delta.get("partial_json", delta.get("text", ""))
        elif kind == "content_block_stop":
            assert active is not None
            assert event["index"] == len(blocks) - 1
            if active["type"] == "tool_use":
                active["input"] = json.loads(active["fragments"])
            active = None
    assert active is None
    return blocks


@pytest.mark.parametrize("index", [0, 7, None])
@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"id": "", "name": ""},
        {"id": None, "name": None},
        {"id": "call_1", "name": "Bash"},
    ],
)
@pytest.mark.parametrize("empty_text", [False, True])
def test_tool_continuations_keep_one_block(index, metadata, empty_text):
    deltas = []
    for position, fragment in enumerate(["{", '"command":"echo ok"', "}"]):
        fields = {"id": "call_1", "name": "Bash"} if position == 0 else metadata
        delta = {"tool_calls": [tool(fragment, index, **fields)]}
        if empty_text:
            delta["content"] = ""
        deltas.append(delta)
    blocks = content(convert(deltas))
    assert len(blocks) == 1
    assert blocks[0]["input"] == {"command": "echo ok"}


def test_interleaved_tools_and_text_use_distinct_sequential_blocks():
    events = convert(
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
        ]
    )
    blocks = content(events)
    assert [block["type"] for block in blocks] == [
        "text",
        "tool_use",
        "tool_use",
        "text",
    ]
    assert blocks[0]["fragments"] == "before"
    assert blocks[1]["input"] == {"a": 1}
    assert blocks[2]["input"] == {"b": 2}
    assert blocks[3]["fragments"] == "after"


@pytest.mark.parametrize("index", [0, None])
def test_delayed_metadata_buffers_arguments(index):
    events = convert(
        [
            {"tool_calls": [tool('{"a":', index)]},
            {"tool_calls": [tool("1}", index, id="a")]},
            {"tool_calls": [tool("", index, id="a", name="A")]},
        ]
    )
    assert content(events)[0]["input"] == {"a": 1}


def test_interleaved_tools_without_indices_resolve_by_id():
    blocks = content(
        convert(
            [
                {
                    "tool_calls": [
                        tool('{"a":', None, id="a", name="A"),
                        tool('{"b":', None, id="b", name="B"),
                    ]
                },
                {"tool_calls": [tool("2}", None, id="b"), tool("1}", None, id="a")]},
            ]
        )
    )
    assert [block["input"] for block in blocks] == [{"a": 1}, {"b": 2}]


def test_done_flushes_blocks_without_finish_reason():
    blocks = content(
        convert(
            [
                {
                    "tool_calls": [
                        tool("{}", id="a", name="A"),
                        tool("{}", 1, id="b", name="B"),
                    ]
                },
            ],
            ending="done",
        )
    )
    assert len(blocks) == 2


def test_first_tool_stays_incremental_and_streams_are_isolated():
    first, second = OpenAIChatDecoder(), OpenAIChatDecoder()
    events = first.decode_stream_event(
        chunk({"tool_calls": [tool("{", id="a", name="A")]})
    )
    assert [event.type.value for event in events] == [
        "content_block_start",
        "content_block_delta",
    ]
    assert events[1].delta_json == "{"
    other = second.decode_stream_event(
        chunk({"tool_calls": [tool("{}", id="b", name="B")]})
    )
    assert other[0].index == 0
    tail = first.decode_stream_event(chunk({"tool_calls": [tool("}")]}))
    assert len(tail) == 1 and tail[0].index == 0


@pytest.mark.parametrize(
    "calls",
    [
        [tool("{}")],
        [tool("{}", id="a")],
        [tool("{}", name="A")],
        [tool("{}", -1, id="a", name="A")],
        [tool("{}", True, id="a", name="A")],
        [tool("{}", id=123, name="A")],
        [tool("{}", id="a", name=123)],
        [tool({"a": 1}, id="a", name="A")],
        [tool("{", id="a", name="A"), tool("}", id="b")],
        [tool("{", id="a", name="A"), tool("}", name="B")],
        [tool("{}", id="a", name="A"), tool("{}", 1, id="a", name="A")],
        [
            tool("{}", id="a", name="A"),
            tool("{}", 1, id="b", name="B"),
            tool("", id="b"),
        ],
        [
            tool("{}", id="a", name="A"),
            tool("{}", 1, id="b", name="B"),
            tool("{}", None),
        ],
    ],
)
def test_invalid_or_ambiguous_tool_identity_is_not_emitted(calls):
    with pytest.raises(StreamConversionError):
        convert([{"tool_calls": calls}])


def test_content_after_finish_is_rejected_but_usage_is_allowed():
    decoder = OpenAIChatDecoder()
    decoder.decode_stream_event(chunk({"content": "hello"}, "stop"))
    assert decoder.decode_stream_event(chunk({})) == []
    usage = decoder.decode_stream_event(
        {"choices": [], "usage": {"completion_tokens": 3}}
    )
    assert usage[0].usage.output_tokens == 3
    with pytest.raises(StreamConversionError):
        decoder.decode_stream_event(chunk({"content": "late"}))


def test_missing_name_waits_before_emitting_a_tool_start():
    decoder = OpenAIChatDecoder()
    assert decoder.decode_stream_event(chunk({"tool_calls": [tool("{", id="a")]})) == []
    events = decoder.decode_stream_event(chunk({"tool_calls": [tool("}", name="A")]}))
    assert events[0].content_block.name == "A"
    assert "".join(event.delta_json or "" for event in events) == "{}"


def test_length_stop_preserves_partial_json_without_inventing_arguments():
    decoder = OpenAIChatDecoder()
    events = decoder.decode_stream_event(
        chunk({"tool_calls": [tool("{", id="a", name="A")]}, "length")
    )
    assert [
        event.delta_json for event in events if event.delta_type == "input_json"
    ] == ["{"]
    assert events[-2].type.value == "content_block_stop"
    assert events[-1].stop_reason.value == "max_tokens"


def test_varied_interleavings_preserve_every_tools_arguments():
    rng = random.Random(136)
    for _ in range(30):
        deltas = [
            {
                "tool_calls": [
                    tool("", i, id=f"call_{i}", name=f"Tool{i}") for i in range(3)
                ]
            }
        ]
        fragments = [list(["{", f'"value":{i}', "}"]) for i in range(3)]
        while any(fragments):
            i = rng.choice([i for i, values in enumerate(fragments) if values])
            deltas.append(
                {
                    "content": "",
                    "tool_calls": [tool(fragments[i].pop(0), i, id="", name="")],
                }
            )
        blocks = content(convert(deltas))
        assert [block["input"] for block in blocks] == [{"value": i} for i in range(3)]


@pytest.mark.parametrize("entry_point", ["generic", "sync", "stateful"])
def test_iterator_eof_flushes_buffered_tools(entry_point):
    chunks = [
        chunk(
            {
                "tool_calls": [
                    tool("{}", id="a", name="A"),
                    tool("{}", 1, id="b", name="B"),
                ]
            }
        )
    ]
    if entry_point == "stateful":
        converter = StreamConverter(Protocol.OPENAI_CHAT, Protocol.ANTHROPIC_MESSAGES)
        events = list(converter.convert_stream(iter(chunks)))
        assert [
            call["arguments"] for call in converter.get_accumulated_tool_calls()
        ] == ["{}", "{}"]
    else:
        convert_fn = convert_stream if entry_point == "generic" else convert_stream_sync
        events = list(
            convert_fn(Protocol.OPENAI_CHAT, Protocol.ANTHROPIC_MESSAGES, iter(chunks))
        )
    assert [block["id"] for block in content(events)] == ["a", "b"]


def test_stateful_converter_reset_clears_decoder_and_accumulator():
    converter = StreamConverter(Protocol.OPENAI_CHAT, Protocol.ANTHROPIC_MESSAGES)
    for tool_id in ["a", "b"]:
        events = list(
            converter.convert_stream(
                iter(
                    [
                        chunk({"tool_calls": [tool("{}", id=tool_id, name="Tool")]}),
                    ]
                )
            )
        )
        assert content(events)[0]["id"] == tool_id
        assert len(converter.get_accumulated_tool_calls()) == 1
        converter.reset()
        assert converter.get_accumulated_tool_calls() == []


@pytest.mark.parametrize("target", [Protocol.OPENAI_CHAT, Protocol.OPENAI_RESPONSES])
def test_other_sdk_targets_keep_interleaved_tool_arguments(target):
    events = list(
        convert_stream(
            Protocol.OPENAI_CHAT,
            target,
            iter(
                [
                    chunk(
                        {
                            "tool_calls": [
                                tool('{"a":', id="a", name="A"),
                                tool('{"b":', 1, id="b", name="B"),
                            ]
                        }
                    ),
                    chunk({"tool_calls": [tool("2}", 1), tool("1}")]}),
                    chunk({}, "tool_calls"),
                ]
            ),
        )
    )
    arguments = {}
    for event in events:
        if target == Protocol.OPENAI_CHAT:
            for call in (
                event.get("choices", [{}])[0].get("delta", {}).get("tool_calls", [])
            ):
                arguments[call["index"]] = arguments.get(call["index"], "") + call[
                    "function"
                ].get("arguments", "")
        elif event["type"] == "response.function_call_arguments.delta":
            index = event["output_index"]
            arguments[index] = arguments.get(index, "") + event["delta"]
    assert {index: json.loads(value) for index, value in arguments.items()} == {
        0: {"a": 1},
        1: {"b": 2},
    }
