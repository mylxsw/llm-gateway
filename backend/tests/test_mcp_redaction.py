"""
Tests for MCP redaction / serialization (Scheme A).

These verify the single maintenance hotspot: secrets are always masked while
ordinary columns pass through verbatim and JSON-safe.
"""

import datetime
from decimal import Decimal

from app.db.models import ApiKey, ServiceProvider
from app.mcp.redaction import (
    redact_dict,
    serialize_row,
    serialize_rows,
)


def test_serialize_provider_masks_api_key_and_proxy_url():
    provider = ServiceProvider(
        name="openai-main",
        base_url="https://api.openai.com",
        protocol="openai",
        proxy_url="http://user:pass@proxy.local:8080",
    )
    provider.api_key = "sk-supersecret-abcdef1234567890"

    row = serialize_row(provider)

    # Ordinary columns pass through.
    assert row["name"] == "openai-main"
    assert row["base_url"] == "https://api.openai.com"
    # Secret never leaks in clear text.
    assert "supersecret" not in str(row["api_key"])
    assert "***" in str(row["api_key"])
    # Proxy credentials masked.
    assert "pass" not in str(row["proxy_url"])
    assert "****" in str(row["proxy_url"])


def test_serialize_api_key_masks_key_value_but_keeps_flags():
    key = ApiKey(
        key_name="agent-1",
        key_value="lgw-abcdefghijklmnopqrstuvwxyz",
        is_active=True,
        record_details=True,
        is_mcp_admin=True,
    )
    row = serialize_row(key)

    assert row["key_name"] == "agent-1"
    assert row["is_mcp_admin"] is True
    assert "abcdefghij" not in row["key_value"]
    assert "***" in row["key_value"]


def test_redact_dict_is_json_safe():
    data = {
        "created_at": datetime.datetime(2026, 7, 11, 12, 0, 0),
        "total_cost": Decimal("1.2345"),
        "api_key": "sk-secret-value-123456",
        "request_headers": {"Authorization": "Bearer sk-xyz1234567", "X-Trace": "abc"},
        "nested": {"key_value": "lgw-innersecret-1234"},
    }
    out = redact_dict(data)

    assert out["created_at"] == "2026-07-11T12:00:00"
    assert isinstance(out["total_cost"], float)
    assert "secret" not in str(out["api_key"])
    # Header sanitization applied to header containers.
    assert "sk-xyz1234567" not in str(out["request_headers"]["Authorization"])
    assert out["request_headers"]["X-Trace"] == "abc"
    # Nested sensitive keys masked recursively.
    assert "innersecret" not in str(out["nested"]["key_value"])


def test_serialize_rows_handles_multiple():
    keys = [
        ApiKey(key_name="a", key_value="lgw-aaaaaaaaaaaa", is_active=True),
        ApiKey(key_name="b", key_value="lgw-bbbbbbbbbbbb", is_active=False),
    ]
    rows = serialize_rows(keys)
    assert len(rows) == 2
    assert all("***" in r["key_value"] for r in rows)
