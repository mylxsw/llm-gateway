
import json
import pytest
from app.services.proxy_service import _smart_truncate, ProxyService

def test_smart_truncate_dict():
    data = {"a": "b", "c": "d"}
    truncated = _smart_truncate(data)
    assert truncated == data

def test_smart_truncate_list_integers():
    data = list(range(30))
    truncated = _smart_truncate(data, max_list=10)
    # Since it's numbers, it uses special truncation (5 items)
    assert len(truncated) == 6 
    assert truncated[5] == "...(25 items)..."

def test_smart_truncate_list_strings():
    data = ["s"] * 30
    truncated = _smart_truncate(data, max_list=10)
    assert len(truncated) == 11
    assert truncated[10] == "...(20 more items)..."

def test_smart_truncate_embedding_list():
    # Embedding list (list of floats)
    data = [0.1] * 100
    truncated = _smart_truncate(data, max_list=10)
    # Special handling for numbers: keeps 5 items + msg
    assert len(truncated) == 6
    assert truncated[5] == "...(95 items)..."

def test_smart_truncate_nested():
    data = {
        "data": [
            {
                "embedding": [0.1] * 100,
                "index": 0
            }
        ]
    }
    truncated = _smart_truncate(data, max_list=10)
    assert truncated["data"][0]["embedding"][5] == "...(95 items)..."

def test_serialize_response_body_json_bytes():
    body = b'{"key": "value"}'
    serialized = ProxyService._serialize_response_body(body)
    assert serialized == '{"key": "value"}'

def test_serialize_response_body_huge_json_bytes():
    # Create a huge JSON
    huge_list = [0.1] * 1000
    body_dict = {"embedding": huge_list}
    body_bytes = json.dumps(body_dict).encode("utf-8")
    
    serialized = ProxyService._serialize_response_body(body_bytes)
    # It should be a valid JSON string
    loaded = json.loads(serialized)
    assert "embedding" in loaded
    assert len(loaded["embedding"]) == 6 # 5 + 1
    assert loaded["embedding"][-1] == "...(995 items)..."

def test_serialize_response_body_invalid_json_bytes():
    body = b'not json'
    serialized = ProxyService._serialize_response_body(body)
    assert serialized == "not json"

def test_serialize_response_body_truncated_bytes():
    # If bytes are truncated and invalid JSON
    body = b'{"key": "val'
    serialized = ProxyService._serialize_response_body(body)
    assert serialized == '{"key": "val'
