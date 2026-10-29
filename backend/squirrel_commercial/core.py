"""Transactions shared by the gateway and a separately deployed customer portal.

Amounts are integer micro-CNY. Rates are micro-CNY per million tokens.
No network calls, private login data, or payment provider code belongs here.
"""
import hashlib
import secrets
import time
import uuid
from sqlalchemy import select, insert, update, text
from . import VERSION
from .schema import metadata, version, accounts, keys, prices, requests, ledger, audit, resolutions

class BillingError(Exception):
    def __init__(self, code, status=403):
        self.code, self.status = code, status
        super().__init__(code)

def now():
    return int(time.time())

def digest(token):
    return 'sha256:' + hashlib.sha256(token.encode()).hexdigest()

def cost(input_tokens, output_tokens, input_rate, output_rate):
    return (input_tokens * input_rate + output_tokens * output_rate + 999999) // 1000000

async def migrate(engine):
    async with engine.begin() as c:
        if c.dialect.name == 'postgresql':
            await c.execute(text("SELECT pg_advisory_xact_lock(85273419)"))
        await c.run_sync(metadata.create_all)
        current = await c.scalar(select(version.c.version).where(version.c.id == 1))
        if current is None:
            await c.execute(insert(version).values(id=1, version=VERSION))
        elif current != VERSION:
            raise BillingError('incompatible_billing_schema', 503)

async def check_version(engine):
    async with engine.connect() as c:
        if await c.scalar(select(version.c.version).where(version.c.id == 1)) != VERSION:
            raise BillingError('incompatible_billing_schema', 503)

async def account_lock(c, account_id):
    # A write lock also serializes local SQLite tests. Production uses PostgreSQL.
    result = await c.execute(update(accounts).where(accounts.c.id == account_id).values(balance=accounts.c.balance))
    if result.rowcount != 1:
        raise BillingError('account_not_found')
    return (await c.execute(select(accounts).where(accounts.c.id == account_id))).mappings().one()

async def add_audit(c, actor, action, target, reason):
    await c.execute(insert(audit).values(id=str(uuid.uuid4()), actor=actor, action=action,
                                        target=str(target), reason=reason, created_at=now()))

async def create_key(engine, account_id, name):
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

async def credit(engine, account_id, amount, reference, kind='credit'):
    if type(amount) is not int or amount <= 0:
        raise BillingError('invalid_amount', 400)
    async with engine.begin() as c:
        await credit_in_transaction(c, account_id, amount, reference, kind)

async def credit_in_transaction(c, account_id, amount, reference, kind='credit'):
    if type(amount) is not int or amount <= 0:
        raise BillingError('invalid_amount', 400)
    await account_lock(c, account_id)
    old = (await c.execute(select(ledger).where(ledger.c.id == reference))).mappings().first()
    if old:
        if old['account_id'] != account_id or old['amount'] != amount or old['kind'] != kind:
            raise BillingError('credit_reference_conflict', 409)
        return
    await c.execute(update(accounts).where(accounts.c.id == account_id).values(balance=accounts.c.balance + amount))
    await c.execute(insert(ledger).values(id=reference, account_id=account_id, amount=amount, kind=kind, created_at=now()))

async def reserve(engine, request_id, key_id, model, input_bound, output_bound):
    if type(input_bound) is not int or type(output_bound) is not int or input_bound < 0 or output_bound <= 0:
        raise BillingError('invalid_token_limits', 400)
    async with engine.begin() as c:
        key = await key_state(c, key_id)
        account = await account_lock(c, key['account_id'])
        key = await key_state(c, key_id)
        active = await c.scalar(text('SELECT is_active FROM api_keys WHERE id=:id'), {'id': key_id})
        if not active or account['blocked']:
            raise BillingError('commercial_key_disabled')
        price = (await c.execute(select(prices).where(prices.c.model == model, prices.c.enabled == True))).mappings().first()
        if not price:
            raise BillingError('model_not_for_sale')
        if input_bound > price['max_input'] or output_bound > price['max_output'] or output_bound <= 0:
            raise BillingError('request_limit_exceeded', 400)
        pending = await c.scalar(select(requests.c.id).where(requests.c.account_id == key['account_id'], requests.c.status == 'review').limit(1))
        if pending:
            raise BillingError('account_requires_review')
        from sqlalchemy import func
        count = await c.scalar(select(func.count()).select_from(requests).where(requests.c.account_id == key['account_id'], requests.c.status == 'reserved'))
        recent = await c.scalar(select(func.count()).select_from(requests).where(requests.c.account_id == key['account_id'], requests.c.created_at > now()-60))
        if recent >= 60:
            raise BillingError('request_rate_limit', 429)
        if count >= 8:
            raise BillingError('concurrency_limit', 429)
        amount = cost(input_bound, output_bound, price['input_rate'], price['output_rate'])
        if account['balance'] - account['reserved'] < amount:
            raise BillingError('insufficient_balance', 402)
        await c.execute(update(accounts).where(accounts.c.id == key['account_id']).values(reserved=accounts.c.reserved + amount))
        await c.execute(insert(requests).values(id=request_id, account_id=key['account_id'], api_key_id=key_id,
            model=model, price_version=price['version'], input_rate=price['input_rate'], output_rate=price['output_rate'],
            reserved=amount, charged=0, status='reserved', created_at=now(), updated_at=now()))

async def settle(engine, request_id, input_tokens=None, output_tokens=None, failed=False):
    async with engine.begin() as c:
        r = (await c.execute(select(requests).where(requests.c.id == request_id))).mappings().first()
        if not r:
            raise BillingError('request_not_found', 404)
        await account_lock(c, r['account_id'])
        r = (await c.execute(select(requests).where(requests.c.id == request_id))).mappings().one()
        if r['status'] not in ('reserved', 'review'):
            return
        if await c.scalar(select(resolutions.c.action).where(resolutions.c.request_id == request_id)) == 'waive':
            failed = True
        if not failed and (type(input_tokens) is not int or type(output_tokens) is not int or min(input_tokens, output_tokens) < 0):
            await c.execute(update(requests).where(requests.c.id == request_id).values(status='review', updated_at=now()))
            return
        amount = 0 if failed else cost(input_tokens, output_tokens, r['input_rate'], r['output_rate'])
        if amount > r['reserved']:
            await c.execute(update(requests).where(requests.c.id == request_id).values(status='review', input_tokens=input_tokens, output_tokens=output_tokens, updated_at=now()))
            return
        await c.execute(update(accounts).where(accounts.c.id == r['account_id']).values(balance=accounts.c.balance - amount, reserved=accounts.c.reserved - r['reserved']))
        await c.execute(insert(ledger).values(id='request:' + request_id, account_id=r['account_id'], amount=-amount, kind='consume', created_at=now()))
        await c.execute(update(requests).where(requests.c.id == request_id).values(status='cancelled' if failed else 'settled', charged=amount, input_tokens=input_tokens, output_tokens=output_tokens, updated_at=now()))

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
        if changes.get('revoke'):
            await c.execute(update(keys).where(keys.c.api_key_id == key_id).values(revoked=True))
        else:
            for field in ('is_active','record_details','key_name'):
                if field in changes and changes[field] is not None:
                    await c.execute(text(f'UPDATE api_keys SET {field}=:value WHERE id=:id'),{'id':key_id,'value':changes[field]})
        await add_audit(c,actor,'key_update',key_id,reason + ': ' + ','.join(sorted(changes)))
