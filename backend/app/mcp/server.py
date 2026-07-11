"""
MCP server

Builds the FastMCP instance, registers read-only (and optionally write) tools,
and exposes a Starlette app (streamable HTTP, stateless) to be mounted under
/mcp by the main application. Authentication is applied by wrapping the app in
MCPAuthMiddleware at mount time.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.config import get_settings
from app.mcp.tools import readonly, write

logger = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "Squirrel LLM Gateway management interface. Use these tools to inspect "
    "providers, model mappings, API keys, request logs, and cost statistics, "
    "and (when write mode is enabled) to manage them. Secrets (upstream API "
    "keys, gateway key values) are always redacted. Start with `whoami`."
)

_READ_TOOLS = [
    readonly.whoami,
    readonly.list_providers,
    readonly.get_provider,
    readonly.list_provider_upstream_models,
    readonly.list_models,
    readonly.get_model,
    readonly.get_model_stats,
    readonly.get_model_provider_stats,
    readonly.list_api_keys,
    readonly.get_api_key,
    readonly.list_request_logs,
    readonly.get_request_log,
    readonly.get_log_cost_stats,
]

_WRITE_TOOLS = [
    write.create_provider,
    write.update_provider,
    write.delete_provider,
    write.create_model,
    write.update_model,
    write.delete_model,
    write.create_model_provider,
    write.update_model_provider,
    write.delete_model_provider,
    write.create_api_key,
    write.update_api_key,
    write.delete_api_key,
    write.cancel_request,
]


def build_mcp_server() -> FastMCP:
    """Construct and configure the FastMCP server with tools registered."""
    settings = get_settings()

    def _split(value: str) -> list[str]:
        return [v.strip() for v in value.split(",") if v.strip()]

    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=settings.MCP_DNS_REBINDING_PROTECTION,
        allowed_hosts=_split(settings.MCP_ALLOWED_HOSTS),
        allowed_origins=_split(settings.MCP_ALLOWED_ORIGINS),
    )

    mcp = FastMCP(
        name=settings.APP_NAME + " MCP",
        instructions=_INSTRUCTIONS,
        stateless_http=True,
        json_response=True,
        # Serve at the mount root so mounting at /mcp yields exactly /mcp
        # (avoids a 307 redirect to /mcp/mcp).
        streamable_http_path="/",
        transport_security=transport_security,
    )

    for tool in _READ_TOOLS:
        mcp.add_tool(tool)

    if settings.MCP_ALLOW_WRITE:
        for tool in _WRITE_TOOLS:
            mcp.add_tool(tool)
        logger.info("MCP write tools enabled (%d tools)", len(_WRITE_TOOLS))
    else:
        logger.info("MCP write tools disabled; read-only mode")

    logger.info(
        "MCP server built with %d tools",
        len(_READ_TOOLS) + (len(_WRITE_TOOLS) if settings.MCP_ALLOW_WRITE else 0),
    )
    return mcp
