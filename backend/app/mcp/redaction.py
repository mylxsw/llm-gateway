"""
MCP Data Redaction & Serialization

Scheme A: MCP tools return raw database rows to the agent, applying only a
sensitive-column blacklist for redaction. This module is the single maintenance
hotspot for that redaction — adding a new non-sensitive column requires no
change here; it flows through automatically.

Serialization also makes values JSON-safe (datetime -> ISO string,
Decimal -> float) so tool results can be transported over MCP.
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any

from app.common.sanitizer import (
    sanitize_api_key_display,
    sanitize_authorization,
    sanitize_headers,
    sanitize_proxy_url,
)

# Columns / keys whose values must never be returned in clear text, even to an
# MCP admin. Compared case-insensitively. Note: the provider ORM maps the
# attribute ``_api_key`` to the DB column named ``api_key`` — both are listed.
SENSITIVE_COLUMNS = {
    "api_key",
    "_api_key",
    "key_value",
    "encryption_key",
    "proxy_url",
}

# Header keys whose values are masked wherever a headers mapping is serialized.
SENSITIVE_HEADER_KEYS = {"authorization", "x-api-key", "api-key", "cookie"}

# Dict keys that hold a headers mapping and should be sanitized as headers.
_HEADER_CONTAINER_KEYS = {"request_headers", "response_headers", "headers"}


def _mask_scalar(key: str, value: Any) -> Any:
    """Mask a single sensitive scalar value using the right sanitizer."""
    if value is None:
        return None
    lower = key.lower()
    if lower == "proxy_url" and isinstance(value, str):
        return sanitize_proxy_url(value)
    if lower in ("key_value",) and isinstance(value, str):
        return sanitize_api_key_display(value)
    # api_key / _api_key / encryption_key and any other secret string.
    if isinstance(value, str):
        return sanitize_authorization(value)
    # Non-string secret (unexpected) -> hard mask.
    return "***"


def _jsonify(value: Any) -> Any:
    """Convert value into a JSON-serializable form."""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return "<bytes>"
    return value


def _sanitize_header_mapping(headers: Any) -> Any:
    """Sanitize a headers-like mapping (case-insensitive sensitive keys)."""
    if not isinstance(headers, dict):
        return headers
    sanitized: dict[str, Any] = {}
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() in SENSITIVE_HEADER_KEYS and isinstance(v, str):
            sanitized[k] = sanitize_authorization(v)
        else:
            sanitized[k] = v
    return sanitized


def redact_value(key: str, value: Any) -> Any:
    """Redact + JSON-ify a single (key, value) pair.

    - Sensitive columns are masked.
    - Header containers get header-level sanitization.
    - Nested dict/list values are redacted recursively.
    """
    if key.lower() in SENSITIVE_COLUMNS:
        return _mask_scalar(key, value)
    if key.lower() in _HEADER_CONTAINER_KEYS:
        return _sanitize_header_mapping(value)
    if isinstance(value, dict):
        return {k: redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(key, item) for item in value]
    return _jsonify(value)


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Redact and JSON-ify a plain dict (e.g. a Pydantic model_dump)."""
    return {k: redact_value(k, v) for k, v in data.items()}


def serialize_row(orm_obj: Any) -> dict[str, Any]:
    """Serialize a SQLAlchemy ORM row into a redacted, JSON-safe dict.

    Iterates the mapped table columns so every column is returned verbatim
    except those in SENSITIVE_COLUMNS. Adding a new column to the table makes
    it appear here automatically with no code change.
    """
    table = getattr(orm_obj, "__table__", None)
    if table is None:
        raise TypeError(f"{type(orm_obj)!r} is not a SQLAlchemy ORM instance")

    result: dict[str, Any] = {}
    for column in table.columns:
        col_name = column.name
        # Read from the mapped attribute when it differs from the column name
        # (e.g. provider `_api_key` -> column `api_key`). Fall back to column.
        value = getattr(orm_obj, col_name, None)
        if value is None and hasattr(orm_obj, f"_{col_name}"):
            value = getattr(orm_obj, f"_{col_name}")
        result[col_name] = redact_value(col_name, value)
    return result


def serialize_rows(orm_objs: Any) -> list[dict[str, Any]]:
    """Serialize an iterable of ORM rows."""
    return [serialize_row(obj) for obj in orm_objs]


def serialize_model(model: Any) -> dict[str, Any]:
    """Serialize a Pydantic domain model (or any object exposing model_dump).

    Redacts sensitive keys and makes the result JSON-safe. Use this when a
    service already returns a domain model rather than a raw ORM row.
    """
    if hasattr(model, "model_dump"):
        data = model.model_dump()
    elif isinstance(model, dict):
        data = model
    else:
        raise TypeError(f"Cannot serialize {type(model)!r}")
    return redact_dict(data)


def serialize_models(models: Any) -> list[dict[str, Any]]:
    """Serialize an iterable of domain models."""
    return [serialize_model(m) for m in models]
