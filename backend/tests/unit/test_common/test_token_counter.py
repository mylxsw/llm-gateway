
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
