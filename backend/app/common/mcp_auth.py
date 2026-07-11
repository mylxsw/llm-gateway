"""
MCP Authentication

The MCP interface reuses the gateway's own API keys. A request is authorized
only when it presents an API key that is BOTH active AND granted MCP admin
capability (``is_mcp_admin=True``).

WARNING: A key with is_mcp_admin=True is effectively a system administrator over
the MCP interface. Granting it is a Web-admin-only action; the MCP tools never
expose grant/revoke so a key cannot escalate or spread its own privileges.

Authentication runs as ASGI middleware in front of the mounted MCP app. The
authenticated principal is published on a ContextVar so tools can read it (for
``whoami`` and audit logging) without re-authenticating.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from app.common.errors import AppError
from app.db.session import AsyncSessionLocal
from app.repositories.sqlalchemy import SQLAlchemyApiKeyRepository
from app.services import ApiKeyService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPPrincipal:
    """The authenticated MCP caller."""

    id: int
    key_name: str
    is_mcp_admin: bool


# Published per-request; read by tools via current_principal().
_current_principal: ContextVar[Optional[MCPPrincipal]] = ContextVar(
    "mcp_current_principal", default=None
)


def current_principal() -> Optional[MCPPrincipal]:
    """Return the authenticated MCP principal for the current request, if any.

    Primary source is the ContextVar. As a fallback (in case the MCP transport
    runs the tool in a task that didn't inherit the ContextVar), we also read
    the principal stashed on the active request scope.
    """
    principal = _current_principal.get()
    if principal is not None:
        return principal
    return _principal_from_request_scope()


def _principal_from_request_scope() -> Optional[MCPPrincipal]:
    """Best-effort read of the principal from the active MCP request scope."""
    try:
        from mcp.server.lowlevel.server import request_ctx

        ctx = request_ctx.get()
    except Exception:
        return None
    if ctx is None:
        return None
    request = getattr(ctx, "request", None)
    scope = getattr(request, "scope", None)
    if isinstance(scope, dict):
        state = scope.get("state") or {}
        principal = state.get("mcp_principal")
        if isinstance(principal, MCPPrincipal):
            return principal
    return None


def require_principal() -> MCPPrincipal:
    """Return the current principal or raise if unauthenticated (defensive)."""
    principal = _current_principal.get()
    if principal is None:
        raise PermissionError("MCP request is not authenticated")
    return principal


def _extract_token(headers: dict[str, str]) -> Optional[str]:
    """Extract the API key from Authorization: Bearer or x-api-key headers."""
    x_api_key = headers.get("x-api-key")
    if x_api_key:
        return x_api_key.strip() or None
    authorization = headers.get("authorization")
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return authorization.strip() or None


async def authenticate_token(token: str) -> MCPPrincipal:
    """Authenticate a token and enforce MCP admin capability.

    Raises:
        PermissionError: token missing / invalid / disabled / not MCP admin.
    """
    if not token:
        raise PermissionError("Missing API key")

    async with AsyncSessionLocal() as session:
        service = ApiKeyService(SQLAlchemyApiKeyRepository(session))
        try:
            api_key = await service.authenticate(token)
        except AppError as exc:
            raise PermissionError(exc.message) from exc

    if not api_key.is_mcp_admin:
        raise PermissionError("API key is not authorized for MCP admin access")

    return MCPPrincipal(
        id=api_key.id,
        key_name=api_key.key_name,
        is_mcp_admin=api_key.is_mcp_admin,
    )


class MCPAuthMiddleware:
    """ASGI middleware that authenticates MCP requests before the MCP handler.

    On success, the principal is set on a ContextVar for the duration of the
    request. On failure, a 401 JSON response is returned and the inner app is
    never invoked.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        token = _extract_token(headers)

        try:
            principal = await authenticate_token(token or "")
        except PermissionError as exc:
            logger.warning("MCP auth rejected: %s", exc)
            await self._send_unauthorized(send, str(exc))
            return

        reset_token = _current_principal.set(principal)
        # Also stash on scope state as a fallback for tools that run in a task
        # not inheriting this ContextVar.
        scope.setdefault("state", {})
        scope["state"]["mcp_principal"] = principal
        try:
            await self.app(scope, receive, send)
        finally:
            _current_principal.reset(reset_token)

    @staticmethod
    async def _send_unauthorized(send, detail: str) -> None:
        body = json.dumps(
            {
                "error": {
                    "message": detail or "Not authenticated",
                    "type": "authentication_error",
                    "code": "mcp_unauthorized",
                }
            }
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
