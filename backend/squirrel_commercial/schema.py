from sqlalchemy import (MetaData, Table, Column as C, String, Integer, BigInteger,
                        Boolean, Text, CheckConstraint, text)

metadata = MetaData()
version = Table('billing_schema', metadata, C('id', Integer, primary_key=True), C('version', Integer, nullable=False))
accounts = Table('billing_accounts', metadata,
    C('id', String(36), primary_key=True), C('blocked', Boolean, nullable=False, default=False),
    C('balance', BigInteger, nullable=False, default=0), C('reserved', BigInteger, nullable=False, default=0),
    C('created_at', BigInteger, nullable=False),
    CheckConstraint('reserved >= 0'))
keys = Table('billing_keys', metadata,
    C('api_key_id', Integer, primary_key=True), C('account_id', String(36), nullable=False, index=True),
    C('name', String(100), nullable=False), C('prefix', String(24), nullable=False),
    C('paused', Boolean, nullable=False, default=False),
    C('revoked', Boolean, nullable=False, default=False),
    C('created_at', BigInteger, nullable=False))
prices = Table('billing_prices', metadata,
    C('model', String(100), primary_key=True), C('version', Integer, nullable=False),
    C('enabled', Boolean, nullable=False, default=False),
    C('input_rate', BigInteger, nullable=False), C('output_rate', BigInteger, nullable=False),
    C('max_input', Integer, nullable=False), C('max_output', Integer, nullable=False),
    CheckConstraint('input_rate >= 0 AND output_rate >= 0 AND max_input > 0 AND max_output > 0'))
requests = Table('billing_requests', metadata,
    C('id', String(64), primary_key=True), C('account_id', String(36), nullable=False, index=True),
    C('api_key_id', Integer, nullable=False), C('model', String(100), nullable=False),
    C('price_version', Integer, nullable=False), C('input_rate', BigInteger, nullable=False),
    C('output_rate', BigInteger, nullable=False), C('reserved', BigInteger, nullable=False),
    C('charged', BigInteger, nullable=False, default=0), C('status', String(24), nullable=False),
    C('input_tokens', BigInteger), C('output_tokens', BigInteger),
    C('created_at', BigInteger, nullable=False), C('updated_at', BigInteger, nullable=False))
ledger = Table('billing_ledger', metadata,
    C('id', String(100), primary_key=True), C('account_id', String(36), nullable=False, index=True),
    C('amount', BigInteger, nullable=False), C('kind', String(24), nullable=False),
    C('created_at', BigInteger, nullable=False))
audit = Table('billing_audit', metadata,
    C('id', String(36), primary_key=True), C('actor', String(100), nullable=False),
    C('action', String(80), nullable=False), C('target', String(100), nullable=False),
    C('reason', Text, nullable=False), C('created_at', BigInteger, nullable=False))
resolutions = Table('billing_resolutions', metadata,
    C('request_id', String(64), primary_key=True), C('action', String(24), nullable=False),
    C('reason', Text, nullable=False), C('created_at', BigInteger, nullable=False))

# v1 columns above are deliberately retained as immutable migration evidence.
from sqlalchemy import JSON, Index, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
JSON = JSON().with_variant(JSONB(), "postgresql")

def extend(table, *columns):
    for column in columns:
        table.append_column(column)


def money(name, default=0):
    return C(name, BigInteger, nullable=False, default=default, server_default=str(default))

extend(version, C('protocol_version', Integer, nullable=False, server_default='2'),
       C('unit', String(16), nullable=False, server_default='microcredit'),
       C('migration_id', String(64)), C('activated_at', BigInteger))
extend(accounts, money('balance_microcredits'), money('reserved_microcredits'),
       money('debt_microcredits'), money('regular_only_debt_microcredits'),
       C('chargeback_frozen', Boolean, nullable=False, server_default=text('false')), money('row_version', 1))
accounts.append_constraint(CheckConstraint('balance_microcredits >= reserved_microcredits AND reserved_microcredits >= 0 AND debt_microcredits >= regular_only_debt_microcredits AND regular_only_debt_microcredits >= 0'))
extend(keys, C('source', String(16), nullable=False, server_default='manual'),
       C('oauth_grant_id', String(36)), C('monthly_limit_microcredits', BigInteger), C('revoked_at', BigInteger))
keys.append_constraint(CheckConstraint("(source='manual' AND oauth_grant_id IS NULL) OR (source='oauth' AND oauth_grant_id IS NOT NULL)"))
Index('billing_keys_active_name', keys.c.account_id, keys.c.name, unique=True,
      postgresql_where=keys.c.revoked == False, sqlite_where=keys.c.revoked == False)

buckets = Table('billing_credit_buckets', metadata,
    C('account_id', String(36), ForeignKey('billing_accounts.id'), primary_key=True),
    C('kind', String(16), primary_key=True), money('balance_microcredits'), money('reserved_microcredits'),
    CheckConstraint("kind IN ('regular','welcome') AND balance_microcredits >= reserved_microcredits AND reserved_microcredits >= 0"))
months = Table('billing_key_months', metadata,
    C('owner_type', String(8), primary_key=True), C('owner_id', String(36), primary_key=True),
    C('month', String(7), primary_key=True), money('settled_microcredits'), money('reserved_microcredits'),
    CheckConstraint("owner_type IN ('key','grant') AND settled_microcredits >= 0 AND reserved_microcredits >= 0"))
settings = Table('billing_settings', metadata, C('key', String(80), primary_key=True),
    C('value_json', JSON, nullable=False), money('version', 1), C('updated_by', String(100), nullable=False),
    money('created_at'), money('updated_at'))
price_configs = Table('billing_price_configs', metadata, C('model', String(100), primary_key=True),
    C('margin_bps', Integer), C('sales_enabled', Boolean, nullable=False, server_default=text('false')),
    C('current_version', BigInteger), money('revision', 1), money('created_at'), money('updated_at'))
price_versions = Table('billing_price_versions', metadata,
    C('model', String(100), primary_key=True), C('version', BigInteger, primary_key=True),
    C('base_input_nano_usd', BigInteger), C('base_output_nano_usd', BigInteger),
    C('margin_bps', Integer, nullable=False), C('global_margin_bps', Integer, nullable=False),
    C('inherits_global', Boolean, nullable=False), C('pricing_factor', Integer, nullable=False, server_default='70'),
    C('input_rate_microcredits', BigInteger), C('output_rate_microcredits', BigInteger),
    C('sales_enabled', Boolean, nullable=False), C('model_enabled', Boolean, nullable=False),
    C('model_type', String(50)), C('alias_target_model', String(100)), C('billing_mode', String(32)),
    C('sellable', Boolean, nullable=False), C('unavailable_reason', String(40)),
    C('source_fingerprint', String(64), nullable=False), C('actor', String(100), nullable=False),
    C('reason', Text, nullable=False), money('created_at'))
oauth_apps = Table('billing_oauth_apps', metadata, C('id', String(36), primary_key=True),
    C('owner_account_id', String(36), ForeignKey('billing_accounts.id'), nullable=False),
    C('client_id', String(64), unique=True, nullable=False), C('name', String(100), nullable=False),
    C('domain', String(253), nullable=False), C('client_type', String(16), nullable=False),
    C('status', String(16), nullable=False), money('revision', 1), C('review_reason', Text), money('created_at'), money('updated_at'))
oauth_grants = Table('billing_oauth_grants', metadata, C('id', String(36), primary_key=True),
    C('account_id', String(36), ForeignKey('billing_accounts.id'), nullable=False),
    C('app_id', String(36), ForeignKey('billing_oauth_apps.id'), nullable=False),
    C('active_key_id', Integer), C('scope', String(100), nullable=False),
    C('monthly_limit_microcredits', BigInteger), C('revoked_at', BigInteger), money('revision', 1),
    money('created_at'), money('updated_at'), UniqueConstraint('account_id', 'app_id'))
extend(requests, C('protocol_version', Integer, nullable=False, server_default='2'),
       money('reserved_microcredits'), money('charged_microcredits'), money('input_rate_microcredits'),
       money('output_rate_microcredits'), money('price_version_v2'), C('month', String(7)),
       C('month_owner_type', String(8)), C('month_owner_id', String(36)),
       money('regular_reserved_microcredits'), money('welcome_reserved_microcredits'),
       C('estimator_version', String(40)), money('input_estimate'), money('output_requested'),
       C('evidence_json', JSON), C('payload_fingerprint', String(64)),
       C('debt_welcome_eligible', Boolean, nullable=False, server_default=text('true')), C('resolved_at', BigInteger))
extend(ledger, C('protocol_version', Integer, nullable=False, server_default='2'),
       money('amount_microcredits'), money('debt_delta_microcredits'), money('regular_only_debt_delta_microcredits'),
       money('gross_microcredits'), money('charged_microcredits'), money('regular_delta_microcredits'),
       money('welcome_delta_microcredits'), C('reference', String(100), unique=True),
       C('request_id', String(64)), C('order_id', String(36)), C('metadata_json', JSON))
extend(resolutions, C('input_tokens', BigInteger), C('output_tokens', BigInteger),
       C('actor', String(100)), C('reference', String(100), unique=True), C('applied_at', BigInteger), C('decision_hash', String(64)))
extend(audit, C('actor_type', String(16)), C('actor_id', String(100)),
       C('before_json', JSON), C('after_json', JSON), C('correlation_id', String(64)))
Index('billing_requests_recovery', requests.c.status, requests.c.updated_at, requests.c.id)
Index('billing_resolutions_pending', resolutions.c.applied_at, resolutions.c.request_id)
Index('billing_keys_grant', keys.c.oauth_grant_id)
Index('billing_requests_account_time', requests.c.account_id, requests.c.created_at, requests.c.id)
migrations = Table('billing_migrations', metadata, C('id', String(64), primary_key=True),
    C('from_version', Integer, nullable=False), C('to_version', Integer, nullable=False),
    C('phase', String(24), nullable=False), money('started_at'), C('finished_at', BigInteger),
    C('checksum_json', JSON), C('backup_ref', Text, nullable=False))
migration_snapshots = Table('billing_migration_snapshots', metadata,
    C('migration_id', String(64), primary_key=True), C('table_name', String(100), primary_key=True),
    C('row_id', String(100), primary_key=True), C('row_json', JSON, nullable=False))

for table in (buckets, months):
    extend(table, money('created_at'), money('updated_at'))
Index('billing_ledger_reference_unique', ledger.c.reference, unique=True)
Index('billing_resolution_reference_unique', resolutions.c.reference, unique=True)
Index('billing_ledger_account_time', ledger.c.account_id, ledger.c.created_at, ledger.c.id)
Index('billing_grant_app_revoked', oauth_grants.c.app_id, oauth_grants.c.revoked_at)
Index('billing_request_key_month', requests.c.api_key_id, requests.c.month)
keys.append_constraint(CheckConstraint('monthly_limit_microcredits IS NULL OR monthly_limit_microcredits >= 0'))
price_configs.append_constraint(CheckConstraint('margin_bps IS NULL OR (margin_bps >= 0 AND margin_bps <= 100000)'))
oauth_grants.append_constraint(CheckConstraint('monthly_limit_microcredits IS NULL OR monthly_limit_microcredits >= 0'))

for table in (keys, requests, ledger):
    table.c.account_id.append_foreign_key(ForeignKey('billing_accounts.id'))
