import pytest

from app.common.stream_usage import StreamUsageAccumulator
from app.common.token_counter import TokenCounter


class MockTokenCounter(TokenCounter):
    def count_tokens(self, text: str, model: str) -> int:
        return len(text.split())

    def count_messages(self, messages: list, model: str) -> int:
        return 0


def test_stream_usage_accumulator_fallback_zero_output_tokens(monkeypatch):
    monkeypatch.setattr(
        "app.common.stream_usage.get_token_counter", lambda p: MockTokenCounter()
    )

    acc = StreamUsageAccumulator(protocol="openai", model="test-model")

    # Simulate a stream that returns text but reports 0 output tokens
    acc.feed(
        b'data: {"choices": [{"delta": {"content": "one two three"}}], "usage": {"output_tokens": 0}}\n\n'
    )

    result = acc.finalize()

    # Should use calculated tokens (3 words) instead of reported 0
    assert result.output_tokens == 3
    assert result.output_text == "one two three"


def test_stream_usage_accumulator_fallback_none_output_tokens(monkeypatch):
    monkeypatch.setattr(
        "app.common.stream_usage.get_token_counter", lambda p: MockTokenCounter()
    )

    acc = StreamUsageAccumulator(protocol="openai", model="test-model")

    # Simulate a stream that returns text but no usage info
    acc.feed(b'data: {"choices": [{"delta": {"content": "one two three"}}]}\n\n')

    result = acc.finalize()

    # Should use calculated tokens (3 words)
    assert result.output_tokens == 3
    assert result.output_text == "one two three"


def test_stream_usage_accumulator_uses_reported_if_valid(monkeypatch):
    monkeypatch.setattr(
        "app.common.stream_usage.get_token_counter", lambda p: MockTokenCounter()
    )

    acc = StreamUsageAccumulator(protocol="openai", model="test-model")

    # Simulate a stream that reports valid output tokens
    acc.feed(
        b'data: {"choices": [{"delta": {"content": "one two three"}}], "usage": {"output_tokens": 10}}\n\n'
    )

    result = acc.finalize()

    # Should use reported tokens (10) instead of calculated (3)
    assert result.output_tokens == 10
    assert result.output_text == "one two three"
