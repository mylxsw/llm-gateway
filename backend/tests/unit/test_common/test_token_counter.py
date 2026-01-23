
import pytest
from app.common.token_counter import OpenAITokenCounter

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
