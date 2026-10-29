# Portal transaction composition

GUL-559 portal composition adds `pricing.quote_order(package, fx_snapshot)` for integer rational purchase quotes and `core.set_key_monthly_limit_in_transaction`, `user_key_action_in_transaction`, `admin_key_action_in_transaction`, and `resolve_review_in_transaction`. These accept an existing async connection and never commit; the original engine entrypoints remain compatible. Audit actor prefixes classify `admin:*` as `admin`, `system:*` as `system`, and `gateway-admin` as `gateway_admin` while preserving the full actor ID.
