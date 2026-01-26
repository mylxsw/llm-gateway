#!/usr/bin/env python3
"""
Streaming Conversion Examples

Demonstrates converting streaming events between protocols.
"""

import json
import sys
sys.path.insert(0, "/home/user/playground")

from api_protocol_converter import convert_stream, Protocol
from api_protocol_converter.stream import (
    StreamAccumulator,
    StreamConverter,
    SSEParser,
    SSEFormatter,
)


def print_event(title: str, event: dict) -> None:
    """Print a stream event."""
    print(f"  {title}: {json.dumps(event)}")


def example_openai_to_anthropic_stream():
    """Convert OpenAI Chat stream to Anthropic format."""
    print("\n" + "#"*70)
    print("# OpenAI Chat Stream -> Anthropic Messages Stream")
    print("#"*70)

    # Simulated OpenAI Chat streaming chunks
    openai_chunks = [
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]
        },
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {"content": "Hello"}, "finish_reason": None}]
        },
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {"content": "! I'm"}, "finish_reason": None}]
        },
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {"content": " doing great."}, "finish_reason": None}]
        },
        {
            "id": "chatcmpl-stream1",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "gpt-4o",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
        },
    ]

    print("\nOriginal OpenAI Chat chunks:")
    for i, chunk in enumerate(openai_chunks):
        delta = chunk["choices"][0]["delta"]
        finish = chunk["choices"][0].get("finish_reason")
        print(f"  Chunk {i}: delta={delta}, finish_reason={finish}")

    # Convert to Anthropic format
    print("\nConverted Anthropic Messages events:")
    anthropic_events = list(convert_stream(
        Protocol.OPENAI_CHAT,
        Protocol.ANTHROPIC_MESSAGES,
        iter(openai_chunks),
    ))

    for i, event in enumerate(anthropic_events):
        if isinstance(event, dict):
            event_type = event.get("type", "unknown")
            print(f"  Event {i}: type={event_type}")
            if event_type == "content_block_delta":
                print(f"           delta={event.get('delta')}")


def example_anthropic_to_openai_stream():
    """Convert Anthropic stream to OpenAI Chat format."""
    print("\n" + "#"*70)
    print("# Anthropic Messages Stream -> OpenAI Chat Stream")
    print("#"*70)

    # Simulated Anthropic streaming events
    anthropic_events = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_stream1",
                "type": "message",
                "role": "assistant",
                "model": "claude-3-5-sonnet-20241022",
                "content": [],
                "stop_reason": None,
                "usage": {"input_tokens": 10, "output_tokens": 0}
            }
        },
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""}
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "The capital"}
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " of France"}
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": " is Paris."}
        },
        {
            "type": "content_block_stop",
            "index": 0
        },
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 8}
        },
        {
            "type": "message_stop"
        }
    ]

    print("\nOriginal Anthropic events:")
    for i, event in enumerate(anthropic_events):
        event_type = event.get("type")
        if event_type == "content_block_delta":
            print(f"  Event {i}: {event_type} - text: '{event['delta'].get('text', '')}'")
        else:
            print(f"  Event {i}: {event_type}")

    # Convert to OpenAI Chat format
    print("\nConverted OpenAI Chat chunks:")
    openai_chunks = list(convert_stream(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_CHAT,
        iter(anthropic_events),
    ))

    for i, chunk in enumerate(openai_chunks):
        if isinstance(chunk, dict) and "choices" in chunk:
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                finish = choices[0].get("finish_reason")
                print(f"  Chunk {i}: delta={delta}, finish_reason={finish}")
        elif chunk == "[DONE]":
            print(f"  Chunk {i}: [DONE]")


def example_stream_accumulator():
    """Use StreamAccumulator to collect streamed content."""
    print("\n" + "#"*70)
    print("# Using StreamAccumulator")
    print("#"*70)

    # Create converter with accumulator
    converter = StreamConverter(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_CHAT,
    )

    # Simulated Anthropic events
    events = [
        {"type": "message_start", "message": {"id": "msg_1", "model": "claude-3-5-sonnet-20241022", "content": []}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello, "}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "world!"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_stop"}
    ]

    print("\nProcessing events...")
    for event in events:
        converted = converter.convert_event(event)
        print(f"  Converted {event['type']} -> {len(converted)} output events")

    # Get accumulated content
    print(f"\nAccumulated text: '{converter.get_accumulated_content()}'")


def example_sse_parsing():
    """Parse and format SSE (Server-Sent Events)."""
    print("\n" + "#"*70)
    print("# SSE Parsing and Formatting")
    print("#"*70)

    # Sample SSE text (as received from HTTP stream)
    sse_text = """event: message_start
data: {"type":"message_start","message":{"id":"msg_1"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: message_stop
data: {"type":"message_stop"}

"""

    print("\nRaw SSE text:")
    print(sse_text)

    # Parse SSE
    parser = SSEParser()
    print("\nParsed events:")
    for event in parser.feed(sse_text):
        print(f"  {event}")

    # Format as SSE
    print("\nFormatting events as SSE:")
    events_to_format = [
        ("message_start", {"message": {"id": "msg_2"}}),
        ("content_block_delta", {"delta": {"type": "text_delta", "text": "Hi!"}}),
        ("message_stop", {}),
    ]

    for event_type, data in events_to_format:
        sse = SSEFormatter.format_event(event_type, data)
        print(f"  {repr(sse)}")


def example_tool_call_stream():
    """Handle tool calls in streaming responses."""
    print("\n" + "#"*70)
    print("# Tool Call Streaming")
    print("#"*70)

    # Anthropic stream with tool use
    anthropic_events = [
        {"type": "message_start", "message": {"id": "msg_tools", "model": "claude-3-5-sonnet-20241022", "content": []}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "toolu_123", "name": "get_weather", "input": {}}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"city"'}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": ': "Paris"'}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '}'}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 20}},
        {"type": "message_stop"}
    ]

    print("\nAnthropic tool use stream:")
    for event in anthropic_events:
        event_type = event["type"]
        if "delta" in event and "partial_json" in event.get("delta", {}):
            print(f"  {event_type}: partial_json='{event['delta']['partial_json']}'")
        else:
            print(f"  {event_type}")

    # Convert to OpenAI
    print("\nConverted to OpenAI Chat stream:")
    openai_events = list(convert_stream(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_CHAT,
        iter(anthropic_events),
    ))

    for event in openai_events:
        if isinstance(event, dict) and "choices" in event:
            delta = event["choices"][0].get("delta", {}) if event["choices"] else {}
            if "tool_calls" in delta:
                print(f"  tool_calls delta: {delta['tool_calls']}")
            elif delta:
                print(f"  delta: {delta}")


if __name__ == "__main__":
    example_openai_to_anthropic_stream()
    example_anthropic_to_openai_stream()
    example_stream_accumulator()
    example_sse_parsing()
    example_tool_call_stream()
