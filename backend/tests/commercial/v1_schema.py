from sqlalchemy import (MetaData, Table, Column as C, String, Integer, BigInteger,
                        Boolean, Text, CheckConstraint)

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
