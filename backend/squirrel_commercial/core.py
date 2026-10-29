"""Transactions shared by the gateway and a separately deployed customer portal.

Amounts are integer microcredits. Rates are microcredits per million tokens.
No network calls, private login data, or payment provider code belongs here.
"""
import hashlib
import secrets
import time
import uuid
from sqlalchemy import select, insert, update, text
from sqlalchemy.exc import IntegrityError
from . import VERSION
from .schema import metadata, version, accounts, keys, prices, requests, ledger, audit, resolutions

from .validation import BillingError, integer
from . import PROTOCOL_VERSION
from .schema import buckets, months, oauth_apps, oauth_grants
from .pricing import quote_rate, sync_price, read_price, configure_price, set_global_margin
from .funds import credit_in_transaction, offset_idle_debt
from .estimator import ESTIMATOR_VERSION

def now():
    return int(time.time())

def digest(token):
    return 'sha256:' + hashlib.sha256(token.encode()).hexdigest()

def cost(input_tokens, output_tokens, input_rate, output_rate):
    for value in (input_tokens, output_tokens, input_rate, output_rate):
        integer(value)
    return integer((input_tokens * input_rate + output_tokens * output_rate + 999999) // 1000000)

async def migrate(engine):
    from .migration import initialize
    await initialize(engine)

async def check_version(engine):
    async with engine.connect() as c:
        row = (await c.execute(select(version).where(version.c.id == 1))).mappings().first()
        if not row or (row['version'], row['protocol_version'], row['unit']) != (VERSION, PROTOCOL_VERSION, 'microcredit'):
            raise BillingError('incompatible_billing_schema', 503)

async def account_lock(c, account_id):
    # A write lock also serializes local SQLite tests. Production uses PostgreSQL.
    result = await c.execute(update(accounts).where(accounts.c.id == account_id).values(row_version=accounts.c.row_version + 1))
    if result.rowcount != 1:
        raise BillingError('account_not_found')
    return (await c.execute(select(accounts).where(accounts.c.id == account_id))).mappings().one()

async def add_audit(c, actor, action, target, reason):
    await c.execute(insert(audit).values(id=str(uuid.uuid4()), actor=actor, action=action,
                                        target=str(target), reason=reason, actor_type='system' if actor.startswith('system:') else 'user', actor_id=actor, created_at=now()))

async def create_key(engine, account_id, name):
    if not isinstance(name, str):
        raise BillingError('invalid_key_name', 400)
    name = name.strip()
    if not name or len(name) > 100:
        raise BillingError('invalid_key_name', 400)
    token = 'sqb-' + secrets.token_urlsafe(32)
    async with engine.begin() as c:
        account = await account_lock(c, account_id)
        if account['blocked']:
            raise BillingError('account_blocked')
        existing = await c.scalar(select(keys.c.api_key_id).where(keys.c.account_id == account_id, keys.c.name == name, keys.c.revoked == False))
        if existing:
            raise BillingError('duplicate_key_name', 409)
        # Existing api_keys owns the canonical log identity. Never store the secret.
        result = await c.execute(text('INSERT INTO api_keys (key_name,key_value,is_active,record_details,is_mcp_admin,created_at) VALUES (:name,:value,true,false,false,CURRENT_TIMESTAMP) RETURNING id'),
                                 {'name': 'commercial-' + str(uuid.uuid4()), 'value': digest(token)})
        key_id = result.scalar_one()
        await c.execute(insert(keys).values(api_key_id=key_id, account_id=account_id,
            name=name, prefix=token[:12], paused=False, revoked=False, created_at=now()))
        await add_audit(c, account_id, 'create_key', key_id, 'User created key')
    return key_id, token

async def key_state(c, key_id):
    result = (await c.execute(select(keys, accounts.c.blocked).join(accounts, accounts.c.id == keys.c.account_id).where(keys.c.api_key_id == key_id))).mappings().first()
    if not result or result['revoked'] or result['paused'] or result['blocked']:
        raise BillingError('commercial_key_disabled')
    return result

async def user_key_action(engine, account_id, key_id, action):
    if action not in ('pause', 'resume', 'revoke'):
        raise BillingError('invalid_action', 400)
    async with engine.begin() as c:
        account = await account_lock(c, account_id)
        key = (await c.execute(select(keys).where(keys.c.api_key_id == key_id, keys.c.account_id == account_id))).mappings().first()
        if not key:
            raise BillingError('key_not_found', 404)
        if account['blocked'] or key['revoked']:
            raise BillingError('key_change_forbidden')
        values = {'revoked': True} if action == 'revoke' else {'paused': action == 'pause'}
        await c.execute(update(keys).where(keys.c.api_key_id == key_id).values(**values))
        await add_audit(c, account_id, action, key_id, 'User key action')

async def credit(engine, account_id, amount, reference, kind='credit', eligibility='regular'):
    async with engine.begin() as c:
        await credit_in_transaction(c, account_id, amount, reference, kind, eligibility)

async def admin_key_action(engine, key_id, changes, actor='gateway-admin', reason='Explicit administrator update'):
    async with engine.begin() as c:
        key = (await c.execute(select(keys).where(keys.c.api_key_id == key_id))).mappings().first()
        if not key:
            raise BillingError('commercial_key_not_found',404)
        await account_lock(c,key['account_id'])
        key = (await c.execute(select(keys).where(keys.c.api_key_id == key_id))).mappings().one()
        if key['revoked']:
            if changes == {'revoke': True}:
                return
            raise BillingError('key_revoked')
        if changes.get('is_mcp_admin'):
            raise BillingError('commercial_admin_forbidden')
        if changes.get('key_name') is not None:
            conflict = await c.scalar(text('SELECT id FROM api_keys WHERE key_name=:name AND id<>:id'),
                                      {'name': changes['key_name'], 'id': key_id})
            conflict = conflict or await c.scalar(select(keys.c.api_key_id).where(keys.c.account_id == key['account_id'], keys.c.name == changes['key_name'], keys.c.revoked == False, keys.c.api_key_id != key_id))
            if conflict:
                raise BillingError('duplicate_key_name', 409)
        if changes.get('revoke'):
            await c.execute(update(keys).where(keys.c.api_key_id == key_id).values(revoked=True))
        else:
            for field in ('is_active','record_details','key_name'):
                if field in changes and changes[field] is not None:
                    try:
                        # Savepoint handles a concurrent rename without aborting the transaction.
                        async with c.begin_nested():
                            await c.execute(text(f'UPDATE api_keys SET {field}=:value WHERE id=:id'),{'id':key_id,'value':changes[field]})
                    except IntegrityError as exc:
                        if field == 'key_name':
                            raise BillingError('duplicate_key_name', 409) from exc
                        raise
        if changes.get('key_name') is not None:
            await c.execute(update(keys).where(keys.c.api_key_id == key_id).values(name=changes['key_name']))
        await add_audit(c,actor,'key_update',key_id,reason + ': ' + ','.join(sorted(changes)))

from .metering import reserve, settle, resolve_review, UsageEvidence


async def create_account_in_transaction(c, account_id):
    """Create an empty account and both funding buckets atomically."""
    await c.execute(insert(accounts).values(id=account_id, blocked=False, balance=0, reserved=0, created_at=now()))
    for kind in ('regular', 'welcome'):
        await c.execute(insert(buckets).values(account_id=account_id, kind=kind, created_at=now(), updated_at=now()))
