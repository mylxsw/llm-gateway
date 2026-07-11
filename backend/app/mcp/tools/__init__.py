"""
MCP tool helpers

Shared utilities for MCP tools: short-lived DB sessions and audit logging.
Each tool opens its own short session (mirrors the proxy service pattern) so a
tool call never pins a pooled connection.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from app.common.mcp_auth import current_principal
from app.db.session import AsyncSessionLocal

logger = logging.getLogger("app.mcp.audit")


@asynccontextmanager
async def db_session():
    """Yield a short-lived async DB session."""
    async with AsyncSessionLocal() as session:
        yield session


def audit(tool: str, **fields: Any) -> None:
    """Emit a structured audit log line for an MCP tool invocation."""
    principal = current_principal()
    actor = (
        f"key#{principal.id}({principal.key_name})" if principal else "unauthenticated"
    )
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.info("mcp_tool=%s actor=%s %s", tool, actor, extra)


class WriteDisabledError(Exception):
    """Raised when a write tool is called while MCP writes are disabled."""


def ensure_writes_enabled() -> None:
    """Guard for write tools; raises when MCP_ALLOW_WRITE is false."""
    from app.config import get_settings

    if not get_settings().MCP_ALLOW_WRITE:
        raise WriteDisabledError(
            "MCP write operations are disabled (set MCP_ALLOW_WRITE=true to enable)"
        )
