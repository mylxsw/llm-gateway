# Redis-only Typeflux proxy runtime

Set `PROXY_REDIS_RUNTIME=true` and set `REDIS_URL` to the existing Redis on the gateway host. No additional Redis service or database migration is needed. Keep each region on its own Redis. Runtime mode also moves protocol/tool/reasoning KV data to Redis, even when the legacy KV setting is `database`.

The startup worker publishes API keys, model mappings and providers as one Redis snapshot, then refreshes it every two seconds. Admin configuration remains database-backed. A missing or malformed runtime snapshot returns 503 without an SQL fallback. The snapshot expires after 60 seconds if the database is unavailable, bounding stale key permissions. A request pins its routing snapshot until it finishes.

Authentication usage timestamps and request logs are appended to `squirrel:runtime:v1:journal`. A background writer persists them to the existing database and acknowledges only successful events. Pending entries survive process restarts and are retried. A writer lease prevents overlapping deployments from duplicating writes. Main requests and failed provider attempts remain separate records even when they share a trace ID. A SQL boundary rejects accidental database operations inside proxy POST requests, including streaming.

Build the narrow patch using `Dockerfile.runtimepatch`, with `BASE_IMAGE` pinned to the image already deployed and `SOURCE_SHA` pinned to the reviewed commit. The preparation workflow publishes a dedicated immutable image; it does not move the `uat`, `latest` or production release tags and has no deployment callback. Keep source branches isolated until the emergency patch is reviewed and merged.

Before switching traffic, verify Redis connectivity, snapshot readiness and journal persistence on a temporary instance using the same existing networks and secrets. Route new requests to the healthy instance, drain old connections, update the canonical service, then drain the temporary instance. Retain the original compose file, environment, image digest and Nginx configuration for rollback. Do not copy credentials to logs or documentation.

Verify real Typeflux requests against the domestic public origin, using an explicitly authorized account, synthetic text, and unique request IDs. Check first content time, total time, final usage, effective upstream thinking controls, one settlement per invocation, journal backlog and errors. Never retry an ambiguous billable request automatically.

Backend regression tests include SQL-denial during full streaming and non-streaming proxy handling, Redis reasoning-cache writes, configuration misses, disabled keys, retry recovery, duplicate log delivery and failed-provider attempts. Install development dependencies with `uv sync --group dev`, then run `uv run pytest` from `backend/`.

Tokenizers are included in both the normal image and runtime patch image under `/app/tiktoken-cache`. Startup loads them in a worker thread before readiness. The preparation workflow verifies token counting with Docker networking disabled, so a cold customer request never downloads tokenizer files. Saved provider reads also skip repeated blocking DNS validation; admin writes still validate URLs.
