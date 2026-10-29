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

async def add_audit(c, actor, action, target, reason, *, before=None, after=None):
    await c.execute(insert(audit).values(id=str(uuid.uuid4()), actor=actor, action=action,
                                        target=str(target), reason=reason, before_json=before, after_json=after, actor_type=('admin' if actor.startswith('admin:') else 'system' if actor.startswith('system:') else 'gateway_admin' if actor == 'gateway-admin' else 'user'), actor_id=actor, created_at=now()))

async def create_key(engine, account_id, name, monthly_limit_microcredits=None):
    if monthly_limit_microcredits is not None:
        integer(monthly_limit_microcredits)
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
            name=name, prefix=token[:12], paused=False, revoked=False, monthly_limit_microcredits=monthly_limit_microcredits, created_at=now()))
        await add_audit(c, account_id, 'create_key', key_id, 'User created key', after={'monthly_limit_microcredits': monthly_limit_microcredits})
    return key_id, token

async def set_key_monthly_limit(engine, account_id, key_id, monthly_limit_microcredits, *, actor=None, reason='User updated monthly limit'):
    async with engine.begin() as c:
        return await set_key_monthly_limit_in_transaction(c, account_id, key_id, monthly_limit_microcredits, actor=actor, reason=reason)


async def set_key_monthly_limit_in_transaction(c, account_id, key_id, monthly_limit_microcredits, *, actor=None, reason='User updated monthly limit'):
    """Update a manual Key limit without resetting its existing month bucket."""
    if monthly_limit_microcredits is not None:
        integer(monthly_limit_microcredits)
    account = await account_lock(c, account_id)
    key = (await c.execute(select(keys).where(keys.c.api_key_id == key_id, keys.c.account_id == account_id))).mappings().first()
    if key is None:
        raise BillingError('key_not_found', 404)
    if account['blocked'] or key['revoked']:
        raise BillingError('key_change_forbidden')
    if key['source'] != 'manual':
        raise BillingError('oauth_grant_limit_required', 400)
    if key['monthly_limit_microcredits'] == monthly_limit_microcredits:
        return
    await c.execute(update(keys).where(keys.c.api_key_id == key_id).values(monthly_limit_microcredits=monthly_limit_microcredits))
    await add_audit(c, actor or account_id, 'set_key_monthly_limit', key_id, reason,
        before={'monthly_limit_microcredits': key['monthly_limit_microcredits']},
        after={'monthly_limit_microcredits': monthly_limit_microcredits})


async def key_state(c, key_id, required_scope=None):
    result = (await c.execute(select(keys, accounts.c.blocked).join(accounts, accounts.c.id == keys.c.account_id).where(keys.c.api_key_id == key_id))).mappings().first()
    if not result or result['revoked'] or result['paused']:
        raise BillingError('commercial_key_disabled')
    if result['blocked']:
        raise BillingError('account_blocked')
    if result['source'] == 'oauth':
        grant = (await c.execute(select(oauth_grants).where(
            oauth_grants.c.id == result['oauth_grant_id']))).mappings().first()
        if not grant or grant['revoked_at'] is not None or grant['active_key_id'] != key_id or grant['account_id'] != result['account_id']:
            raise BillingError('oauth_grant_disabled')
        app = (await c.execute(select(oauth_apps).where(
            oauth_apps.c.id == grant['app_id']))).mappings().first()
        if app and app['status'] == 'suspended':
            raise BillingError('application_suspended')
        if not app or (app['status'] != 'verified' and app['owner_account_id'] != result['account_id']):
            raise BillingError('oauth_grant_disabled')
        if required_scope and required_scope not in grant['scope'].split():
            raise BillingError('insufficient_scope')
    return result

async def user_key_action(engine, account_id, key_id, action):
    async with engine.begin() as c:
        return await user_key_action_in_transaction(c, account_id, key_id, action)


async def user_key_action_in_transaction(c, account_id, key_id, action):
    if action not in ('pause', 'resume', 'revoke'):
        raise BillingError('invalid_action', 400)
    account = await account_lock(c, account_id)
    key = (await c.execute(select(keys).where(keys.c.api_key_id == key_id, keys.c.account_id == account_id))).mappings().first()
    if not key:
        raise BillingError('key_not_found', 404)
    if account['blocked'] or key['revoked']:
        raise BillingError('key_change_forbidden')
    values = {'revoked': True, 'revoked_at': now()} if action == 'revoke' else {'paused': action == 'pause'}
    await c.execute(update(keys).where(keys.c.api_key_id == key_id).values(**values))
    await add_audit(c, account_id, action, key_id, 'User key action')

async def credit(engine, account_id, amount, reference, kind='credit', eligibility='regular'):
    async with engine.begin() as c:
        await credit_in_transaction(c, account_id, amount, reference, kind, eligibility)

async def admin_key_action(engine, key_id, changes, actor='gateway-admin', reason='Explicit administrator update'):
    async with engine.begin() as c:
        return await admin_key_action_in_transaction(c, key_id, changes, actor=actor, reason=reason)


async def admin_key_action_in_transaction(c, key_id, changes, actor='gateway-admin', reason='Explicit administrator update'):
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
        await c.execute(update(keys).where(keys.c.api_key_id == key_id).values(revoked=True, revoked_at=now()))
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

from .metering import reserve, settle, resolve_review, resolve_review_in_transaction, UsageEvidence


async def create_account_in_transaction(c, account_id):
    """Create an empty account and both funding buckets atomically."""
    await c.execute(insert(accounts).values(id=account_id, blocked=False, balance=0, reserved=0, created_at=now()))
    for kind in ('regular', 'welcome'):
        await c.execute(insert(buckets).values(account_id=account_id, kind=kind, created_at=now(), updated_at=now()))
