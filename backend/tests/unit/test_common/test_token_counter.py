
import pytest
from app.common.token_counter import AnthropicTokenCounter, OpenAITokenCounter

def test_count_input_string():
    counter = OpenAITokenCounter()
    text = "hello world"
    # Fallback estimation: len(text) // 4 = 11 // 4 = 2
    # If tiktoken available, it might be different (e.g. 2 tokens)
    # Mocking tiktoken behavior or relying on fallback if not installed
    count = counter.count_input(text)
    assert count > 0

def test_count_input_list_strings():
    counter = OpenAITokenCounter()
    input_data = ["hello", "world"]
    count = counter.count_input(input_data)
    # hello -> 1, world -> 1 (approx)
    assert count > 0

def test_count_input_list_tokens():
    counter = OpenAITokenCounter()
    input_data = [1, 2, 3, 4, 5]
    count = counter.count_input(input_data)
    assert count == 5

def test_count_input_list_list_tokens():
    counter = OpenAITokenCounter()
    input_data = [[1, 2], [3, 4, 5]]
    count = counter.count_input(input_data)
    assert count == 5

def test_count_input_empty():
    counter = OpenAITokenCounter()
    assert counter.count_input("") == 0
    assert counter.count_input([]) == 0


def test_count_tokens_treats_reserved_special_token_text_as_plain_text():
    text = "literal marker <|endoftext|> should not fail"

    assert OpenAITokenCounter().count_tokens(text, "gpt-4") > 0
    assert AnthropicTokenCounter().count_tokens(text, "claude-sonnet-4-0") > 0


def test_anthropic_count_request_allows_reserved_special_token_text():
    counter = AnthropicTokenCounter()
    body = {
        "model": "claude-sonnet-4-0",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_123",
                        "content": [
                            {"type": "text", "text": "literal <|endoftext|> value"}
                        ],
                    }
                ],
            }
        ],
    }

    assert counter.count_request(body) > 0


def test_count_messages_with_image_detail_low_adds_tokens():
    counter = OpenAITokenCounter()
    image_payload = {
        "type": "image_url",
        "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==",
            "detail": "low",
        },
    }
    base = counter.count_messages([{"role": "user", "content": [{"type": "text", "text": "hi"}]}])
    with_image = counter.count_messages([{"role": "user", "content": [{"type": "text", "text": "hi"}, image_payload]}])
    assert with_image - base >= 85


def test_count_messages_with_audio_adds_tokens():
    counter = OpenAITokenCounter()
    audio_payload = {"type": "input_audio", "input_audio": {"data": "AAAA"}}
    base = counter.count_messages([{"role": "user", "content": [{"type": "text", "text": "hi"}]}])
    with_audio = counter.count_messages([{"role": "user", "content": [{"type": "text", "text": "hi"}, audio_payload]}])
    assert with_audio > base


def test_count_request_tools_increases_tokens():
    counter = OpenAITokenCounter()
    body = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
    body_with_tools = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"type": "function", "function": {"name": "f", "parameters": {}}}],
    }
    base = counter.count_request(body)
    with_tools = counter.count_request(body_with_tools)
    assert with_tools > base


def test_anthropic_count_request_with_system_and_tools_increases_tokens():
    counter = AnthropicTokenCounter()
    body = {
        "model": "claude-sonnet-4-0",
        "messages": [{"role": "user", "content": "hi"}],
    }
    body_with_system_and_tools = {
        "model": "claude-sonnet-4-0",
        "system": "You are helpful.",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [
            {
                "name": "get_weather",
                "description": "Get weather by city",
                "input_schema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            }
        ],
    }
    base = counter.count_request(body)
    with_system_and_tools = counter.count_request(body_with_system_and_tools)
    assert with_system_and_tools > base


def test_anthropic_count_messages_with_document_and_tool_result():
    counter = AnthropicTokenCounter()
    base = counter.count_messages(
        [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
    )
    enriched = counter.count_messages(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {
                        "type": "document",
                        "title": "Spec",
                        "context": "API reference",
                        "source": {
                            "type": "text",
                            "media_type": "text/plain",
                            "data": "This is a longer document body used for counting.",
                        },
                    },
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_123",
                        "name": "get_weather",
                        "input": {"city": "Shanghai"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_123",
                        "content": [{"type": "text", "text": "22C and sunny"}],
                    }
                ],
            },
        ]
    )
    assert enriched > base
