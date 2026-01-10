"""
工具函数单元测试
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
    """API Key 生成测试"""
    
    def test_generate_with_default_prefix(self):
        """测试使用默认前缀生成"""
        key = generate_api_key()
        assert key.startswith("lgw-")
        assert len(key) > 10
    
    def test_generate_with_custom_prefix(self):
        """测试使用自定义前缀生成"""
        key = generate_api_key(prefix="test-")
        assert key.startswith("test-")
    
    def test_generate_unique_keys(self):
        """测试生成的 key 唯一性"""
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100


class TestGenerateTraceId:
    """Trace ID 生成测试"""
    
    def test_generate_trace_id(self):
        """测试生成 trace ID"""
        trace_id = generate_trace_id()
        assert len(trace_id) == 36  # UUID 格式
        assert "-" in trace_id
    
    def test_generate_unique_trace_ids(self):
        """测试生成的 trace ID 唯一性"""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestExtractModelFromBody:
    """提取模型名测试"""
    
    def test_extract_model(self):
        """测试提取模型名"""
        body = {"model": "gpt-4", "messages": []}
        assert extract_model_from_body(body) == "gpt-4"
    
    def test_extract_missing_model(self):
        """测试模型名不存在"""
        body = {"messages": []}
        assert extract_model_from_body(body) is None


class TestReplaceModelInBody:
    """替换模型名测试"""
    
    def test_replace_model(self):
        """测试替换模型名"""
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
        }
        result = replace_model_in_body(body, "gpt-4-turbo")
        
        # 只修改 model，其他保持不变
        assert result["model"] == "gpt-4-turbo"
        assert result["messages"] == body["messages"]
        assert result["temperature"] == 0.7
        
        # 不修改原始数据
        assert body["model"] == "gpt-4"
    
    def test_not_modify_other_fields(self):
        """测试不修改其他字段"""
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
    """字符串掩码测试"""
    
    def test_mask_normal_string(self):
        """测试普通字符串掩码"""
        result = mask_string("abcdefghijklmnop")
        assert result.startswith("abcd")
        assert result.endswith("op")
        assert "***" in result
    
    def test_mask_short_string(self):
        """测试短字符串掩码"""
        result = mask_string("abc")
        assert result == "***"


class TestTryParseJsonObject:
    """JSON 对象/数组解析测试"""

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
