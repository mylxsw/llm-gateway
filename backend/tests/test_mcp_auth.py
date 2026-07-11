"""
Tests for MCP auth token extraction and the write-tool privilege-stripping.
"""

import pytest

from app.common.mcp_auth import MCPPrincipal, _extract_token


def test_extract_token_bearer():
    assert _extract_token({"authorization": "Bearer lgw-abc"}) == "lgw-abc"


def test_extract_token_x_api_key_priority():
    headers = {"authorization": "Bearer lgw-abc", "x-api-key": "lgw-xyz"}
    assert _extract_token(headers) == "lgw-xyz"


def test_extract_token_raw_authorization():
    assert _extract_token({"authorization": "lgw-raw"}) == "lgw-raw"


def test_extract_token_missing():
    assert _extract_token({}) is None


@pytest.mark.asyncio
async def test_update_api_key_strips_is_mcp_admin(monkeypatch):
    """update_api_key must never let is_mcp_admin change through MCP."""
    import app.mcp.tools.write as write_mod

    captured = {}

    class _FakeService:
        def __init__(self, *a, **k):
            pass

        async def update(self, key_id, data):
            captured["key_id"] = key_id
            captured["data"] = data
            # Return a minimal object with model_dump for serialize_model.
            from app.domain.api_key import ApiKeyResponse
            import datetime

            return ApiKeyResponse(
                id=key_id,
                key_name="x",
                key_value="lgw-***",
                is_active=True,
                record_details=True,
                is_mcp_admin=False,
                created_at=datetime.datetime(2026, 1, 1),
            )

    # Bypass the write gate and DB session.
    monkeypatch.setattr(write_mod, "ensure_writes_enabled", lambda: None)

    class _FakeSession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(write_mod, "db_session", lambda: _FakeSession())
    monkeypatch.setattr(write_mod, "ApiKeyService", _FakeService)
    monkeypatch.setattr(write_mod, "SQLAlchemyApiKeyRepository", lambda s: None)
    monkeypatch.setattr(write_mod, "audit", lambda *a, **k: None)

    result = await write_mod.update_api_key(
        7, {"key_name": "renamed", "is_mcp_admin": True}
    )

    # The privilege-escalation field was stripped before hitting the service.
    dumped = captured["data"].model_dump(exclude_unset=True)
    assert "is_mcp_admin" not in dumped
    assert dumped.get("key_name") == "renamed"
    # A warning is surfaced to the caller.
    assert "_warning" in result


def test_principal_dataclass():
    p = MCPPrincipal(id=1, key_name="k", is_mcp_admin=True)
    assert p.id == 1 and p.is_mcp_admin is True
