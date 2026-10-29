# Optional commercial access (schema v1)

Disabled by default. The gateway remains independently usable without private portal code.

Set `COMMERCIAL_ENABLED=true`, `COMMERCIAL_ONLY=true`, PostgreSQL database configuration, and administrator credentials to run a dedicated commercial gateway. Initialize the gateway schema, then explicitly run `python -m squirrel_commercial.migrate` from backend. Startup checks the shared schema version. The Docker image includes the public shared Python package.

## Shared database contract

The `squirrel_commercial` package owns generic accounts, key associations, price versions, request reservations, ledger entries, audit records and operator resolution requests. It contains no payment provider or private login implementation. A separate portal may use this package and the same database; no portal RPC occurs during inference.

- `api_keys.id` remains the log identity. Commercial secrets start with `sqb-`; only SHA-256 digests are persisted in `api_keys.key_value`. Digest strings cannot authenticate as bearer tokens.
- `billing_keys.account_id` identifies the payer. A commercial account is not a gateway administrator or resource owner.
- The deployment has one global resource pool. This feature does not add resource multi-tenancy.
- Money uses integer micro-CNY; price rates are micro-CNY per million tokens. Each request snapshots rates and rounds the combined charge upward once to a micro-CNY.
- Account-row transactions serialize reservations, payments and refunds. Model calls run outside database transactions. A request ledger ID is globally unique, so settlement retries cannot debit twice.
- Commercial user identity is saved separately from caller-supplied `X-User-ID`. Log list and statistics support exact `commercial_user_id` filtering.
- Deleting a commercial key marks it revoked and retains its historical identity. User pause cannot undo administrator disable. Commercial keys cannot acquire MCP admin rights, reveal their original secret, or use log replay.

## Request policy

Initial interfaces: text chat completions and Anthropic messages, with explicit positive output-token limits; no tools, media, multiple completions or other endpoints. `/v1/models` filters to sale-enabled models. Cache input counts toward total input at the normal input rate.

Input budget uses a conservative UTF-8 estimate plus framing allowance. Complete streams use final upstream usage; interrupted or incomplete streams use the larger of reported usage and local estimates for each token count. A zero completion count is valid. An unsuccessful initial upstream response cancels the reservation without charge. After a successful stream starts, failures with measured usage are charged; failures without usage and charges above the reservation enter `review`. Review accounts cannot authorize further calls until the pending case is resolved. A blocked account fails all keys. Each account has at most eight outstanding requests and sixty authorizations per minute.

Commercial key detail logging defaults to false in the shared creator. The gateway ignores caller-provided defaults and reads the actual key setting. Only explicit administrator key updates enable details. Diagnostics are redacted in commercial request context, including stream processing; free-form upstream errors and arbitrary usage payloads are not saved to commercial logs. Metadata and billing remain available when payload logging is off.

Commercial OpenAI streams request `stream_options.include_usage=true` after protocol conversion. For a provider that explicitly rejects this parameter, set `provider_options.supports_stream_usage=false`; incomplete usage then falls back to local estimates. Upstream usage is trusted only after an OpenAI final usage chunk or Anthropic `message_delta` followed by `message_stop`, including when protocols are converted.

Admin Playground and Retry reject logs associated with hashed commercial keys with HTTP 403, preserving the administrator session. Admin model tests explicitly bypass commercial-only restrictions and never reserve or charge customer funds.

## Recovery and operations

`COMMERCIAL_RECOVERY_DIR` must be a writable persistent volume. Before final settlement, the gateway writes a body-free recovery record, flushes it, then commits the ledger. A scheduled job retries records still reserved or under review. Settled records are removed; review records move into the recovery volume’s `review/` directory for investigation. Startup probes use `.probe` files and are excluded from settlement recovery. Loss of this volume may leave unconfirmed use requiring manual review, not automatic free settlement.

Nonstream work and streaming iteration each have a one-hour deadline. Orphan reservations older than three hours enter review rather than being refunded while they might still execute. Operators can enqueue a waiver in `billing_resolutions`; only the gateway recovery worker applies it. Explicit disconnects, cancellations and timeouts settle from available usage and local estimates. Nonstream cancellation while waiting for a response uses the input estimate and zero output because no output estimate is available. Response cleanup also settles streams that were never consumed. Recovery applies each pending operator decision independently.

Log retention is not billing retention. Never delete ledger data while pruning diagnostics. Watch pending recovery files, review requests and reserved amounts. Infrastructure backups must cover both the database and recovery volume. Test rollback by stopping new traffic and draining in-flight requests before downgrading; schema version mismatch fails closed.

Commercial mode disabled: normal keys retain existing behavior; `sqb-` keys fail authentication. Commercial-only enabled: ordinary keys cannot bypass payment via public model routes. PostgreSQL and explicit admin authentication are required at commercial startup.

Tests: `python -m pytest tests/commercial -q` from backend. Optional `BILLING_TEST_DATABASE_URL` exercises a dedicated PostgreSQL database using temporary isolated schemas. Full regression tests remain required for changes to proxy behavior.
