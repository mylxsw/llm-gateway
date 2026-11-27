# Optional commercial access (schema/protocol v2)

Disabled by default. The gateway remains independently usable without private portal code. `COMMERCIAL_ENABLED=false` never reads commercial tables. A commercial deployment requires PostgreSQL, explicit administrator authentication and `COMMERCIAL_ENABLED=true`; use `COMMERCIAL_ONLY=true` to reject ordinary public API Keys.

Initialize the gateway schema first, then a **fresh** commercial database with `python -m squirrel_commercial.migrate`. Existing v1 installations must use the explicit maintenance migration below. Startup requires schema=2, protocol=2 and unit=microcredit. Deploy the private portal/worker with the same shared package version (2.0.0); v1 writers must never run against v2.

## Units, pricing and transaction contract

All amounts are integer microcredits (1 Credit = 1,000,000). Prices are microcredits per million tokens. `quote_rate(base_nano_usd, margin_bps)` computes the model-level USD base price × 70 × (1+margin), rounded upward to 0.01 Credit. A model override wins over the global margin (default 3000 basis points). `cost` rounds the combined input/output charge once. Cached tokens are already included in input usage.

`configure_price(connection, model, margin_bps=..., sales_enabled=..., actor=..., reason=...)`, `set_global_margin(connection, ...)` and `sync_price(connection, ...)` publish immutable versions. These accept the caller's transaction; the private portal must use them for configuration writes. Gateway model edits publish before commit; recovery synchronizes directly edited sources in bounded pages. Only active `chat` models with nonnegative base prices, `token_flat` billing and sales enabled are sellable. Alias prices never inherit from a target. `/v1/models` uses the same sale checks as reservation.

Reserve reads all price sources and the immutable version in one MVCC statement, without price locks. A missing or mismatched version returns `price_sync_pending` (503) without calling the upstream. Settle and operator review use the request's frozen rates. Lock order: price settings → model → price config; financial transactions: OAuth app → account → grant/Key → month → request. Model calls run outside database transactions.

Use `create_account_in_transaction` to create an empty account and regular/welcome buckets, and `credit_in_transaction` to add funds alongside a payment transaction. `credit(engine, ...)` owns its transaction. `eligibility='welcome'` is exclusively for welcome funds; purchases, bonuses and compensation use the default regular bucket. Credit references are globally unique and retries with different parameters return 409. Every balance/debt change has a ledger event; old v1 amount columns remain untouched and new v2 rows fill required old amounts with zero. Reports must select columns by protocol version.

## Credit resource

With commercial access enabled, `GET /v1/credits` accepts a commercial Key through
`Authorization: Bearer` or `x-api-key`. OAuth grants require `credits:read`; manual
Keys allow this by default. The response contains `balance`, `reserved`, `available`,
`debt`, `monthly_limit`, `month_settled` and `month_reserved`, all integer microcredit
strings except a nullable unlimited `monthly_limit`. Available credit is balance
minus reservations. Unverified developer apps see only the regular funding bucket.
Month counters use UTC and belong to the grant for OAuth Keys, surviving rotation.

Recognized Keys on blocked accounts return 403 `account_blocked`; suspended OAuth
apps return 403 `application_suspended`. Unknown Keys still return 401. When
`COMMERCIAL_ENABLED=false`, the route is absent from both HTTP and OpenAPI.

## Requests, monthly limits and evidence

Commercial requests support text `/v1/chat/completions` and `/v1/messages`, one completion, no tools/media. Exactly one positive `max_tokens` or `max_completion_tokens` is required. There is no per-call input/output Token cap. The versioned estimator counts actual messages/system text with the model tokenizer when available; fallback counts ASCII runs as ceil(length/3), every other code point as 2, adds 16 per message plus 32 framing, then rounds 120% upward. Metadata and JSON byte length are excluded.

Manual Keys use their own UTC month bucket; OAuth Keys use the persistent grant bucket, including across Key rotations. `settled + reserved + new reservation` must fit `monthly_limit_microcredits`; NULL is unlimited and zero prevents spending. Review reservations remain frozen in their original month. Accounts allow eight active reservations and sixty new requests/minute; review does not consume concurrency. Request ID retries are parameter-checked and idempotent; the gateway generates IDs internally.

`settle(engine, request_id, UsageEvidence(...))` accepts explicit upstream/termination evidence. OpenAI Chat Completions SSE needs final usage followed by `[DONE]`; Anthropic needs final `message_delta` usage and `message_stop`. Complete nonstream responses must contain nonnegative integer usage. Zero output is valid. HTTP error status alone never proves no work was done. A confirmed local rejection (`sent_upstream=False`) cancels with zero charge. Explicit disconnect/cancel/timeout charges the per-dimension maximum of reported and estimated usage, including the original input estimate; it estimates only observed output. Other incomplete/ambiguous responses enter review and freeze only their own reservation.

`resolve_review(engine, request_id, 'charge'|'waive', input_tokens=..., output_tokens=..., actor=..., reason=..., reference=...)` atomically records the decision, audit and settlement. Charge requires verified nonnegative usage; waive takes no tokens. Identical retries are no-ops, conflicting decisions return 409, and late upstream evidence cannot override the result.

A charge can exceed its reservation. It consumes only funds not reserved by other requests and records the shortfall as debt. The full charge counts toward that original month's usage. Settlement/release/credit and subsequent reservations offset idle eligible funds against debt with a separate idempotent ledger event, without counting consumption twice. Debt blocks further spending after eligible offsets. Unverified OAuth uses only regular funds; its debt remains regular-only even if the application is later verified. Welcome funds cannot repay that debt.

## Privacy and recovery

`api_keys.id` remains the log identity. Secrets begin `sqb-`; only SHA-256 digests are persisted and digest strings cannot authenticate. Commercial accounts do not confer gateway administrator rights. Pausing/resuming cannot undo administrator disable. Key deletion retains historical identity. Playground/Retry reject commercial logs even after revocation. Authenticated admin model tests bypass customer billing.

Detail logging defaults off and follows the actual Key setting. Diagnostics redact free-form errors and arbitrary usage payloads. `COMMERCIAL_RECOVERY_DIR` must be a writable persistent volume. The gateway fsyncs body-free v2 journals before settlement. Recovery processes at most 100 journals per pass, isolates malformed/incompatible journals into `quarantine/`, archives review evidence for 30 days, and deletes terminal journals. `.probe` files are excluded. Reservations untouched for three hours enter review. Decisions apply synchronously through the shared API, never via ad hoc SQL insertion.

Nonstream and stream execution have one-hour deadlines. The response owns its finalizer in ASGI try/finally, including disconnect before first iteration; cleanup closes the upstream and shields settlement. Database failures leave journal evidence for recovery. Billing history is retained independently of log retention.

## Maintenance migration

Stop new commercial traffic and portal writes/workers; ordinary traffic can continue. Drain all v1 reserved/review requests and journals using v1. Resolve old refunds and close/expire unpaid orders at the provider. Back up the database and recovery volume and verify restoration. Reconcile v1 account balances with ledger totals; documented opening adjustments must be recorded explicitly before upgrade.

From backend, using the configured `DATABASE_URL`:

```sh
python -m squirrel_commercial.migrate --from-version 1 --to-version 2 --dry-run
python -m squirrel_commercial.migrate --from-version 1 --to-version 2 --apply --backup-ref VERIFIED_BACKUP_ID
```

The advisory-locked DDL transaction preserves old columns, snapshots old financial rows/checksums, adds v2 tables/columns/indexes/checks, and converts old balances, request amounts/rates and ledger amounts ×10. Historical funds go into regular, welcome/debt start at zero, and migrated Keys have unlimited manual monthly limits. A zero-value migration ledger event records each account's conversion. The schema/protocol pointer advances last. Failure rolls back; repeated apply never multiplies twice. The package refuses outstanding requests, reservations, refunds/orders, overflow, duplicate active Key names or unreconciled money.

Migrate the private portal separately before reopening traffic. Before reopening, rollback means restoring pre-upgrade software/data under maintenance; old columns are intact. Once v2 money or OAuth writes exist, never downgrade to v1 or divide balances by 10. Restore a verified full backup and reconcile external events, or fix forward with v2.

Run `python -m pytest` from backend. Set `BILLING_TEST_DATABASE_URL` to an isolated PostgreSQL database to exercise real locks using disposable test schemas. Test both `COMMERCIAL_ENABLED=false` and `true`.

Manual Key creation accepts `monthly_limit_microcredits=None` (unlimited), zero (no spending), or a nonnegative BIGINT. `set_key_monthly_limit(engine, account_id, key_id, limit, actor=..., reason=...)` checks ownership under the account lock, records the old/new limit in audit, and preserves existing monthly usage/reservations. OAuth limits belong to the grant and must be updated by the grant service.

A Responses stream terminates with `response.completed` containing complete integer usage; it does not require `[DONE]`. Chat Completions still requires final usage plus `[DONE]`. An upstream error with neither output nor reported usage cancels at zero cost. Provider-detected transport timeouts carry explicit interruption evidence and settle from estimates; an HTTP 504 returned by the upstream does not by itself prove a transport timeout. Successful responses missing usage, and partial output without complete evidence, remain in review.

Gemini streaming termination evidence is not yet validated for automatic commercial settlement and can leave reservations in review. JEV currently rejects streaming requests; use OpenAI Chat Completions, Responses, or Anthropic for automatic stream settlement. Tokenizer initialization runs outside the event loop and falls back to `unicode-v1` if loading fails, including offline deployments.
