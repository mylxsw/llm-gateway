"""Tests for provider-facing JSON Schema normalization."""

from api_protocol_converter.converters.schema_utils import omit_null_required


def test_omit_null_required_traverses_schema_keywords_only():
    schema = {
        "type": "object",
        "required": None,
        "$defs": {"address": {"type": "object", "required": None}},
        "items": [{"type": "object", "required": None}],
        "allOf": [{"type": "object", "required": None}],
        "default": {"required": None},
    }

    result = omit_null_required(schema)

    assert "required" not in result
    assert "required" not in result["$defs"]["address"]
    assert "required" not in result["items"][0]
    assert "required" not in result["allOf"][0]
    assert result["default"] == {"required": None}
    assert schema["required"] is None


def test_omit_null_required_preserves_non_schema_value():
    value = [{"required": None}]

    result = omit_null_required(value)

    assert result == value
    assert result is not value
