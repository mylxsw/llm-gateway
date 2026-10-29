# Portal transaction composition

GUL-559 portal composition adds `pricing.quote_order(package, fx_snapshot)` for integer rational purchase quotes and `core.set_key_monthly_limit_in_transaction`, `user_key_action_in_transaction`, `admin_key_action_in_transaction`, and `resolve_review_in_transaction`. These accept an existing async connection and never commit; the original engine entrypoints remain compatible. Audit actor prefixes classify `admin:*` as `admin`, `system:*` as `system`, and `gateway-admin` as `gateway_admin` while preserving the full actor ID.

OAuth composition (`GUL-560`) adds `oauth.issue_key_in_transaction` and
`oauth.change_grant_in_transaction`. The private authorization server first locks
`billing_oauth_apps`, then calls these helpers on the same connection. They lock
the account and grant, never commit, store only the key digest, and preserve the
grant/month bucket across revocation and reauthorization. Issuance returns the
secret once. Revoke is idempotent; limit changes support `expected_revision`.
Limits are integer microcredits divisible by 10^6 (null means unlimited).
App suspension/reapproval uses the same app lock as `metering.reserve`; accepted
in-flight reservations remain settleable after suspension or key rotation.
