"""
Streaming Usage Parsing Unit Tests
"""

from app.common.stream_usage import StreamUsageAccumulator
from app.common.token_counter import get_token_counter


def test_openai_stream_accumulates_content_and_counts_tokens():
    acc = StreamUsageAccumulator(protocol="openai", model="gpt-4")
    chunks = [
        b"data: {\"choices\":[{\"delta\":{\"content\":\"Hel\"}}]}\n\n",
        b"data: {\"choices\":[{\"delta\":{\"content\":\"lo\"}}]}\n\n",
        b"data: [DONE]\n\n",
    ]
    for c in chunks:
        acc.feed(c)

    result = acc.finalize()
    assert result.output_text == "Hello"

    expected = get_token_counter("openai").count_tokens("Hello", "gpt-4")
    assert result.output_tokens == expected


def test_openai_stream_prefers_upstream_reported_usage():
    acc = StreamUsageAccumulator(protocol="openai", model="gpt-4")
    chunks = [
        b"data: {\"choices\":[{\"delta\":{\"content\":\"Hello\"}}]}\n\n",
        b"data: {\"choices\":[{\"delta\":{}}],\"usage\":{\"completion_tokens\":7}}\n\n",
        b"data: [DONE]\n\n",
    ]
    for c in chunks:
        acc.feed(c)

    result = acc.finalize()
    assert result.output_text == "Hello"
    assert result.output_tokens == 7
    assert result.upstream_reported_output_tokens == 7


def test_anthropic_stream_accumulates_text_and_uses_output_tokens():
    acc = StreamUsageAccumulator(protocol="anthropic", model="claude-3")
    chunks = [
        b"data: {\"type\":\"content_block_delta\",\"delta\":{\"text\":\"Hi\"}}\r\n\r\n",
        b"data: {\"type\":\"message_delta\",\"usage\":{\"output_tokens\":9}}\r\n\r\n",
    ]
    for c in chunks:
        acc.feed(c)

    result = acc.finalize()
    assert result.output_text == "Hi"
    assert result.output_tokens == 9


def test_openai_stream_includes_tool_calls_in_output_text():
    acc = StreamUsageAccumulator(protocol="openai", model="gpt-4")
    chunks = [
        b"data: {\"choices\":[{\"delta\":{\"tool_calls\":[{\"index\":0,\"id\":\"call_1\",\"type\":\"function\",\"function\":{\"name\":\"f\",\"arguments\":\"{}\"}}]}}]}\n\n",
        b"data: [DONE]\n\n",
    ]
    for c in chunks:
        acc.feed(c)

    result = acc.finalize()
    assert "call_1" in result.output_text
    assert "\"function\"" in result.output_text


def test_openai_stream_includes_legacy_function_call_in_output_text():
    acc = StreamUsageAccumulator(protocol="openai", model="gpt-4")
    chunks = [
        b"data: {\"choices\":[{\"delta\":{\"function_call\":{\"name\":\"get_weather\",\"arguments\":\"{\\\"city\\\":\\\"BJ\\\"}\"}}}]}\n\n",
        b"data: [DONE]\n\n",
    ]
    for c in chunks:
        acc.feed(c)

    result = acc.finalize()
    assert "get_weather" in result.output_text
    assert "arguments" in result.output_text
