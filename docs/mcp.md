# MCP Management Interface

Squirrel exposes a **Model Context Protocol (MCP)** interface so AI agents can
inspect and manage the gateway — providers, model mappings, API keys, request
logs, and cost statistics — through a standard MCP client.

The interface follows a "raw data" design: tools return database rows almost
verbatim (only secrets are redacted) so an agent sees as much diagnostic detail
as possible.

## Endpoint & transport

- **Transport:** Streamable HTTP (stateless), official `mcp` Python SDK.
- **URL:** `<gateway-base-url>/mcp` (e.g. `http://localhost:8000/mcp`).
- **Auth:** `Authorization: Bearer <api-key>` (or `x-api-key: <api-key>`).

## Authentication & authorization

MCP reuses the gateway's own API keys. A request is authorized only when the key
is **active** AND has been granted **MCP admin capability** (`is_mcp_admin`).

> ⚠️ **A key granted MCP admin is effectively a system administrator.** It can
> read all request/response logs (including bodies), view provider
> configuration, and manage API keys via MCP. Grant it only to trusted
> automation agents.

Granting is a **Web-admin-only** action (API Keys page → edit key → *MCP admin
capability*, with a red warning and a type-the-name confirmation). The MCP tools
themselves **never** expose grant/revoke, so a key can never escalate or spread
its own privilege. `update_api_key` over MCP silently strips any `is_mcp_admin`
field.

Secrets are always redacted in tool output, even for an admin: upstream provider
API keys, gateway key values, proxy credentials, and sensitive request headers.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `MCP_ENABLED` | `false` | Mount the `/mcp` interface. |
| `MCP_ALLOW_WRITE` | `false` | Expose write/management tools. Read-only when false. |
| `MCP_DNS_REBINDING_PROTECTION` | `false` | Enable Host/Origin validation on the MCP transport. |
| `MCP_ALLOWED_HOSTS` | `""` | Comma-separated allowed `Host` values (when protection on). |
| `MCP_ALLOWED_ORIGINS` | `""` | Comma-separated allowed `Origin` values (when protection on). |

## Tools

### Read-only (always available when `MCP_ENABLED`)

| Tool | Purpose |
|---|---|
| `whoami` | Identity & privileges of the current MCP caller. |
| `list_providers` / `get_provider` | Service providers (upstream `api_key` redacted). |
| `list_provider_upstream_models` | Probe a provider for the models it exposes. |
| `list_models` / `get_model` | Model mappings + per-provider mappings. |
| `get_model_stats` / `get_model_provider_stats` | Aggregated call stats. |
| `list_api_keys` / `get_api_key` | API keys (`key_value` redacted). |
| `list_request_logs` / `get_request_log` | Request logs; detail bodies included, headers redacted. |
| `get_log_cost_stats` | Cost/usage aggregation over time/model/provider/key. |

### Write (only when `MCP_ALLOW_WRITE=true`)

`create_provider` / `update_provider` / `delete_provider`,
`create_model` / `update_model` / `delete_model`,
`create_model_provider` / `update_model_provider` / `delete_model_provider`,
`create_api_key` / `update_api_key` / `delete_api_key`,
`cancel_request`.

> Grant/revoke of MCP admin is intentionally **not** a tool — use the Web admin
> console.

## Quick start

1. Set `MCP_ENABLED=true` (and optionally `MCP_ALLOW_WRITE=true`) and restart.
2. In the dashboard → **API Keys**, edit a key and enable **MCP admin
   capability** (confirm the warning).
3. Point an MCP client at `http://<host>:8000/mcp` with
   `Authorization: Bearer <that-key>`.
4. Call `whoami` to confirm, then explore with `list_providers`,
   `list_request_logs`, `get_log_cost_stats`, etc.

## Auditing

Every MCP tool call and every auth rejection is logged (logger `app.mcp.audit`
for tools, `app.common.mcp_auth` for rejections) with the acting key id/name.
