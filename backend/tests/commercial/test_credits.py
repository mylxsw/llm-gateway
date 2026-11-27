"""HTTP credit snapshots and recognized-key authorization failures."""
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.deps import get_db
from app.api.proxy.credits import router
from app.common.errors import AppError
from app.config import get_settings
from squirrel_commercial import core
from squirrel_commercial.oauth import issue_key_in_transaction
from squirrel_commercial.schema import accounts, buckets, keys, months, oauth_apps, oauth_grants


@pytest.fixture
async def client(billing, monkeypatch):
    import app.db.session as database
    monkeypatch.setattr(database, 'engine', billing)
    monkeypatch.setattr(get_settings(), 'COMMERCIAL_ENABLED', True)
    monkeypatch.setattr(get_settings(), 'COMMERCIAL_ONLY', False)
    app = FastAPI()
    app.include_router(router)

    @app.exception_handler(AppError)
    async def error_handler(request, exc):
        return JSONResponse(exc.to_dict(), status_code=exc.status_code)

    async def db():
        async with async_sessionmaker(billing, expire_on_commit=False)() as session:
            yield session
    app.dependency_overrides[get_db] = db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        yield client


async def oauth_key(engine, scope='models:invoke credits:read', status='verified'):
    async with engine.begin() as c:
        await c.execute(insert(oauth_apps).values(id='app', owner_account_id='alice', client_id='client',
            name='App', domain='example.com', client_type='public', status=status))
        app = (await c.execute(select(oauth_apps))).mappings().one()
        token = await issue_key_in_transaction(c, 'alice', app, scope, 1000000)
        grant = (await c.execute(select(oauth_grants))).mappings().one()
        return grant['active_key_id'], token, grant['id']


async def test_manual_snapshot_headers_and_limit(billing, client):
    kid, token = await core.create_key(billing, 'alice', 'manual')
    for headers in ({'Authorization': 'Bearer ' + token}, {'x-api-key': token}):
        response = await client.get('/v1/credits', headers=headers)
        assert response.status_code == 200
        assert response.json() == dict(balance='1000', reserved='0', available='1000', debt='0',
            monthly_limit=None, month_settled='0', month_reserved='0')
    await core.set_key_monthly_limit(billing, 'alice', kid, 900)
    response = await client.get('/v1/credits', headers={'x-api-key': token})
    assert response.json()['monthly_limit'] == '900'


@pytest.mark.parametrize('status,expected', [('verified', '1500'), ('draft', '1000')])
async def test_oauth_months_and_welcome_isolation(billing, client, status, expected):
    kid, token, gid = await oauth_key(billing, status=status)
    async with billing.begin() as c:
        await c.execute(update(buckets).where(buckets.c.account_id == 'alice', buckets.c.kind == 'welcome').values(balance_microcredits=500))
        await c.execute(update(accounts).where(accounts.c.id == 'alice').values(balance_microcredits=1500, debt_microcredits=50))
        await c.execute(insert(months), [
            dict(owner_type='grant', owner_id=gid, month=datetime.now(timezone.utc).strftime('%Y-%m'), settled_microcredits=12, reserved_microcredits=34),
            dict(owner_type='key', owner_id=str(kid), month=datetime.now(timezone.utc).strftime('%Y-%m'), settled_microcredits=999, reserved_microcredits=0),
            dict(owner_type='grant', owner_id=gid, month='2000-01', settled_microcredits=999, reserved_microcredits=0)])
    response = await client.get('/v1/credits', headers={'x-api-key': token})
    assert response.status_code == 200
    assert response.json() == dict(balance=expected, reserved='0', available=expected, debt='50',
        monthly_limit='1000000', month_settled='12', month_reserved='34')


async def test_reservation_settlement_and_rotation(billing, client):
    kid, token, _ = await oauth_key(billing)
    await core.reserve(billing, 'credits-request', kid, 'model', 10, 20)
    reserved = await client.get('/v1/credits', headers={'x-api-key': token})
    assert reserved.json()['reserved'] == reserved.json()['month_reserved'] == '50'
    assert reserved.json()['available'] == '950'
    await core.settle(billing, 'credits-request', core.UsageEvidence(input_tokens=10, output_tokens=10, source='upstream', terminal_complete=True))
    async with billing.begin() as c:
        app = (await c.execute(select(oauth_apps))).mappings().one()
        rotated = await issue_key_in_transaction(c, 'alice', app, 'credits:read', None)
    result = await client.get('/v1/credits', headers={'x-api-key': rotated})
    assert result.status_code == 200
    assert result.json() == dict(balance='970', reserved='0', available='970', debt='0',
        monthly_limit=None, month_settled='30', month_reserved='0')


async def test_missing_scope(billing, client):
    _, token, _ = await oauth_key(billing, scope='models:invoke')
    result = await client.get('/v1/credits', headers={'x-api-key': token})
    assert result.status_code == 403
    assert result.json()['error']['code'] == 'insufficient_scope'


@pytest.mark.parametrize('oauth', [False, True])
async def test_blocked_before_inactive_check(billing, client, oauth):
    _, token = (await oauth_key(billing))[:2] if oauth else await core.create_key(billing, 'alice', 'blocked')
    async with billing.begin() as c:
        await c.execute(update(accounts).where(accounts.c.id == 'alice').values(blocked=True))
        await c.execute(text('UPDATE api_keys SET is_active=false'))
    result = await client.get('/v1/credits', headers={'x-api-key': token})
    assert result.status_code == 403
    assert result.json()['error']['code'] == 'account_blocked'
    invalid = await client.get('/v1/credits', headers={'x-api-key': 'sqb-invalid'})
    assert invalid.status_code == 401
    assert invalid.json()['error']['code'] == 'invalid_api_key'


async def test_suspended_and_restored(billing, client):
    _, token, _ = await oauth_key(billing)
    async with billing.begin() as c:
        await c.execute(update(oauth_apps).values(status='suspended'))
    result = await client.get('/v1/credits', headers={'x-api-key': token})
    assert result.status_code == 403
    assert result.json()['error']['code'] == 'application_suspended'
    async with billing.begin() as c:
        await c.execute(update(oauth_apps).values(status='verified'))
    assert (await client.get('/v1/credits', headers={'x-api-key': token})).status_code == 200


@pytest.mark.parametrize('change', ['paused', 'revoked', 'inactive'])
async def test_disabled_keys(billing, client, change):
    kid, token = await core.create_key(billing, 'alice', 'disabled')
    async with billing.begin() as c:
        if change == 'inactive':
            await c.execute(text('UPDATE api_keys SET is_active=false WHERE id=:id'), {'id': kid})
        else:
            await c.execute(update(keys).where(keys.c.api_key_id == kid).values(**{change: True}))
    assert (await client.get('/v1/credits', headers={'x-api-key': token})).status_code == 401


async def test_ordinary_and_missing_key(client, billing):
    async with billing.begin() as c:
        await c.execute(text("INSERT INTO api_keys (key_name,key_value,is_active,record_details,is_mcp_admin,created_at) VALUES ('ordinary','sk-ordinary',true,false,false,CURRENT_TIMESTAMP)"))
    assert (await client.get('/v1/credits')).status_code == 401
    result = await client.get('/v1/credits', headers={'x-api-key': 'sk-ordinary'})
    assert result.status_code == 403
    assert result.json()['error']['code'] == 'commercial_key_required'


async def test_translates_failed_revalidation(billing, client, monkeypatch):
    from app.api.proxy import credits
    _, token = await core.create_key(billing, 'alice', 'race')
    async def failed_snapshot(*args):
        raise core.BillingError('account_blocked')
    monkeypatch.setattr(credits, 'snapshot', failed_snapshot)
    result = await client.get('/v1/credits', headers={'x-api-key': token})
    assert result.status_code == 403
    assert result.json()['error']['code'] == 'account_blocked'


async def test_admin_disable_between_auth_and_snapshot(billing, client, monkeypatch):
    from app.api.proxy import credits
    original = credits.snapshot
    _, token = await core.create_key(billing, 'alice', 'disable-race')

    async def disable_then_snapshot(engine, key_id):
        async with engine.begin() as c:
            await c.execute(text('UPDATE api_keys SET is_active=false WHERE id=:id'), {'id': key_id})
        return await original(engine, key_id)

    monkeypatch.setattr(credits, 'snapshot', disable_then_snapshot)
    result = await client.get('/v1/credits', headers={'x-api-key': token})
    assert result.status_code == 403
    assert result.json()['error']['code'] == 'commercial_key_disabled'
