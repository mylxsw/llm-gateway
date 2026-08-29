"""Helpers for normalizing JSON Schemas between provider protocols."""

import copy
from typing import Any, Dict

_SCHEMA_MAP_KEYWORDS = (
    "$defs",
    "dependencies",
    "definitions",
    "dependentSchemas",
    "patternProperties",
    "properties",
)
_SCHEMA_SINGLE_KEYWORDS = (
    "additionalItems",
    "additionalProperties",
    "contains",
    "contentSchema",
    "else",
    "if",
    "items",
    "not",
    "propertyNames",
    "then",
    "unevaluatedItems",
    "unevaluatedProperties",
)
_SCHEMA_LIST_KEYWORDS = ("allOf", "anyOf", "oneOf", "prefixItems")


def omit_null_required(schema: Any) -> Any:
    """Return a copy of a JSON Schema with null ``required`` values omitted.

    Some schema generators serialize an absent optional ``required`` keyword as
    ``null``. Anthropic accepts such tool schemas, but OpenAI-compatible APIs
    validate the keyword as an array and reject the entire request. Traverse
    only schema-bearing keywords so arbitrary values in ``default`` or
    ``examples`` remain untouched.
    """
    cleaned = copy.deepcopy(schema)
    if not isinstance(cleaned, dict):
        return cleaned

    _omit_null_required_in_place(cleaned)
    return cleaned


def _omit_null_required_in_place(schema: Dict[str, Any]) -> None:
    if "required" in schema and schema["required"] is None:
        schema.pop("required")

    for keyword in _SCHEMA_MAP_KEYWORDS:
        children = schema.get(keyword)
        if isinstance(children, dict):
            for child in children.values():
                if isinstance(child, dict):
                    _omit_null_required_in_place(child)

    for keyword in _SCHEMA_SINGLE_KEYWORDS:
        child = schema.get(keyword)
        if isinstance(child, dict):
            _omit_null_required_in_place(child)
        elif keyword == "items" and isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    _omit_null_required_in_place(item)

    for keyword in _SCHEMA_LIST_KEYWORDS:
        children = schema.get(keyword)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    _omit_null_required_in_place(child)
