import json

import pytest

from app.common.stream_usage import StreamUsageAccumulator
from app.common.token_counter import TokenCounter


class MockTokenCounter(TokenCounter):
    def count_tokens(self, text: str, model: str) -> int:
        return len(text.split())

    def count_messages(self, messages: list, model: str) -> int:
        return 0


def test_stream_usage_accumulator_tool_calls(monkeypatch):
    monkeypatch.setattr(
        "app.common.stream_usage.get_token_counter", lambda p: MockTokenCounter()
    )

    acc = StreamUsageAccumulator(protocol="openai", model="test-model")

    # Construct chunks using json.dumps to ensure validity
    chunk1_data = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_123",
                            "type": "function",
                            "function": {"name": "get_weather", "arguments": ""},
                        }
                    ]
                }
            }
        ]
    }

    chunk2_data = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [{"index": 0, "function": {"arguments": '{"loc'}}]
                }
            }
        ]
    }

    chunk3_data = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {"index": 0, "function": {"arguments": 'ation": "London"}'}}
                    ]
                }
            }
        ]
    }

    chunks = [
        f"data: {json.dumps(chunk1_data)}\n\n".encode("utf-8"),
        f"data: {json.dumps(chunk2_data)}\n\n".encode("utf-8"),
        f"data: {json.dumps(chunk3_data)}\n\n".encode("utf-8"),
    ]

    for chunk in chunks:
        acc.feed(chunk)

    result = acc.finalize()

    # Check if output_text contains the VALID JSON of the full tool call
    assert json.loads(result.output_text) == [
        {
            "index": 0,
            "id": "call_123",
            "type": "function",
            "function": {"name": "get_weather", "arguments": '{"location": "London"}'},
        }
    ]

    # Count tokens based on our MockTokenCounter (split by space)
    # This will be just a rough check that it's > 0
    assert result.output_tokens > 0
