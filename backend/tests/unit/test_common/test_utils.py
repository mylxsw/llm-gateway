"""
Utility Functions Unit Tests
"""

import pytest
from app.common.utils import (
    generate_api_key,
    generate_trace_id,
    extract_model_from_body,
    replace_model_in_body,
    mask_string,
    try_parse_json_object,
)


class TestGenerateApiKey:
    """API Key Generation Tests"""
    
    def test_generate_with_default_prefix(self):
        """Test generation with default prefix"""
        key = generate_api_key()
        assert key.startswith("lgw-")
        assert len(key) > 10
    
    def test_generate_with_custom_prefix(self):
        """Test generation with custom prefix"""
        key = generate_api_key(prefix="test-")
        assert key.startswith("test-")
    
    def test_generate_unique_keys(self):
        """Test uniqueness of generated keys"""
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100


class TestGenerateTraceId:
    """Trace ID Generation Tests"""
    
    def test_generate_trace_id(self):
        """Test trace ID generation"""
        trace_id = generate_trace_id()
        assert len(trace_id) == 36  # UUID format
        assert "-" in trace_id
    
    def test_generate_unique_trace_ids(self):
        """Test uniqueness of generated trace IDs"""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestExtractModelFromBody:
    """Extract Model from Body Tests"""
    
    def test_extract_model(self):
        """Test extract model name"""
        body = {"model": "gpt-4", "messages": []}
        assert extract_model_from_body(body) == "gpt-4"
    
    def test_extract_missing_model(self):
        """Test extracting missing model name"""
        body = {"messages": []}
        assert extract_model_from_body(body) is None


class TestReplaceModelInBody:
    """Replace Model in Body Tests"""
    
    def test_replace_model(self):
        """Test replace model name"""
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
        }
        result = replace_model_in_body(body, "gpt-4-turbo")
        
        # Only modify model, others remain unchanged
        assert result["model"] == "gpt-4-turbo"
        assert result["messages"] == body["messages"]
        assert result["temperature"] == 0.7
        
        # Original data not modified
        assert body["model"] == "gpt-4"
    
    def test_not_modify_other_fields(self):
        """Test not modifying other fields"""
        body = {
            "model": "gpt-4",
            "messages": [],
            "temperature": 0.7,
            "max_tokens": 1000,
            "stream": True,
            "tools": [{"type": "function"}],
        }
        result = replace_model_in_body(body, "target-model")
        
        assert result["model"] == "target-model"
        assert result["temperature"] == 0.7
        assert result["max_tokens"] == 1000
        assert result["stream"] is True
        assert result["tools"] == [{"type": "function"}]


class TestMaskString:
    """String Masking Tests"""
    
    def test_mask_normal_string(self):
        """Test normal string masking"""
        result = mask_string("abcdefghijklmnop")
        assert result.startswith("abcd")
        assert result.endswith("op")
        assert "***" in result
    
    def test_mask_short_string(self):
        """Test short string masking"""
        result = mask_string("abc")
        assert result == "***"


class TestTryParseJsonObject:
    """JSON Object/Array Parsing Tests"""

    def test_parse_json_object(self):
        assert try_parse_json_object('{"type":"stream","ok":true}') == {
            "type": "stream",
            "ok": True,
        }

    def test_parse_json_array(self):
        assert try_parse_json_object('[{"a":1},{"b":2}]') == [{"a": 1}, {"b": 2}]

    def test_keep_non_json_string(self):
        assert try_parse_json_object("not json") == "not json"

    def test_keep_invalid_json(self):
        assert try_parse_json_object("{not json}") == "{not json}"