"""
Tests for MCP server tool registration invariants and write gating.
"""

import asyncio

import pytest

from app.config import get_settings
from app.mcp.server import build_mcp_server
from app.mcp.tools import WriteDisabledError, ensure_writes_enabled


def _tool_names(monkeypatch, allow_write: bool) -> set[str]:
    get_settings.cache_clear()
    monkeypatch.setenv("MCP_ALLOW_WRITE", "true" if allow_write else "false")
    get_settings.cache_clear()
    mcp = build_mcp_server()
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


def test_readonly_mode_excludes_write_tools(monkeypatch):
    names = _tool_names(monkeypatch, allow_write=False)
    # Read tools present.
    assert "list_providers" in names
    assert "get_request_log" in names
    assert "whoami" in names
    # Write tools absent.
    assert "create_provider" not in names
    assert "delete_api_key" not in names


def test_write_mode_includes_write_tools(monkeypatch):
    names = _tool_names(monkeypatch, allow_write=True)
    assert "create_provider" in names
    assert "update_api_key" in names
    assert "cancel_request" in names


def test_grant_revoke_never_exposed(monkeypatch):
    """MCP admin grant/revoke must never be an MCP tool (Web-admin-only)."""
    for allow_write in (False, True):
        names = _tool_names(monkeypatch, allow_write=allow_write)
        assert not any("grant" in n or "revoke" in n for n in names)
        assert "grant_mcp_admin" not in names
        assert "revoke_mcp_admin" not in names


def test_ensure_writes_enabled_guard(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MCP_ALLOW_WRITE", "false")
    get_settings.cache_clear()
    with pytest.raises(WriteDisabledError):
        ensure_writes_enabled()

    monkeypatch.setenv("MCP_ALLOW_WRITE", "true")
    get_settings.cache_clear()
    # Should not raise.
    ensure_writes_enabled()
    get_settings.cache_clear()
