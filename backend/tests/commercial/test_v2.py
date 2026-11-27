"""Financial invariants exercised identically on PostgreSQL and SQLite."""
import asyncio
import pytest
from sqlalchemy import select, insert, update, func
from squirrel_commercial import core
from squirrel_commercial.schema import accounts, buckets, keys, requests, months, ledger, price_configs, price_versions, oauth_apps, oauth_grants
from squirrel_commercial.estimator import estimate_input, text_tokens
from squirrel_commercial.pricing import models, nano


async def balance(engine, uid='alice'):
    async with engine.connect() as c:
        return (await c.execute(select(accounts).where(accounts.c.id == uid))).mappings().one()


async def trusted(engine, rid, inp, out):
    await core.settle(engine, rid, core.UsageEvidence(inp, out, source='upstream', terminal_complete=True))


@pytest.mark.parametrize('base,margin,expected', [(10**9,3000,91000000),(1,0,10000),(0,100000,0),(10**9,0,70000000)])
def test_quote(base, margin, expected):
    assert core.quote_rate(base, margin) == expected
    assert nano('0.0000000001') == 1
    assert nano('-1') is None
    assert core.cost(1,1,1,1) == 1


@pytest.mark.parametrize('value', [True,-1,2**63,1.5])
def test_integer_boundaries(value):
    with pytest.raises(core.BillingError):
        core.cost(value,0,0,0)


@pytest.mark.parametrize('content,expected', [('abc',1),('中文',4),('😀',2),('abcd中😀',6)])
def test_unicode_estimator(content, expected):
    assert text_tokens(content) == expected
    a,v = estimate_input({'model':'unknown-v2', 'messages':[{'content':content}], 'max_tokens':1})
    assert a == ((48+expected)*120+99)//100 and v=='unicode-v1'
    b,_=estimate_input({'model':'unknown-v2', 'messages':[{'content':content}], 'metadata':'x'*10000})
    assert a==b


async def test_monthly_limit_is_concurrent_and_review_keeps_reservation(billing):
    kid,_=await core.create_key(billing,'alice','monthly')
    async with billing.begin() as c:
        await c.execute(update(keys).where(keys.c.api_key_id==kid).values(monthly_limit_microcredits=100))
    async def reserve(rid):
        try:
            await core.reserve(billing,rid,kid,'model',10,30)
            return rid
        except core.BillingError as e:
            assert e.code=='monthly_limit_exceeded'
    result=await asyncio.gather(reserve('a'),reserve('b'))
    winner=next(r for r in result if r)
    assert len([r for r in result if r])==1
    await core.settle(billing,winner)
    with pytest.raises(core.BillingError, match='monthly_limit_exceeded'):
        await core.reserve(billing,'c',kid,'model',10,20)
    # Another Key can spend while this one is in review.
    other,_=await core.create_key(billing,'alice','other')
    await core.reserve(billing,'d',other,'model',1,1)
    await core.resolve_review(billing,winner,'charge',20,0,actor='admin:1',reason='verified',reference='decision-a')
    async with billing.connect() as c:
        row=(await c.execute(select(months).where(months.c.owner_id==str(kid)))).mappings().one()
        assert row['settled_microcredits']==20 and row['reserved_microcredits']==0


@pytest.mark.parametrize('second,remaining,debt', [(10,10,0),(40,0,20)])
async def test_overage_protects_other_reservations_and_offsets_idle_debt(billing,second,remaining,debt):
    kid,_=await core.create_key(billing,'alice','debt')
    async with billing.begin() as c:
        await c.execute(update(accounts).where(accounts.c.id=='alice').values(balance_microcredits=100))
        await c.execute(update(buckets).where(buckets.c.account_id=='alice', buckets.c.kind=='regular').values(balance_microcredits=100))
    await asyncio.gather(core.reserve(billing,'a',kid,'model',50,1),core.reserve(billing,'b',kid,'model',46,1))
    # A reserves 52, B 48 (total 100), then A costs 80.
    await trusted(billing,'a',80,0)
    a=await balance(billing)
    assert (a['balance_microcredits'],a['reserved_microcredits'],a['debt_microcredits'])==(48,48,28)
    await asyncio.gather(trusted(billing,'b',second,0),trusted(billing,'b',second,0))
    a=await balance(billing)
    assert (a['balance_microcredits'],a['reserved_microcredits'],a['debt_microcredits'])==(remaining,0,debt)
    await trusted(billing,'a',80,0)
    async with billing.connect() as c:
        events=(await c.execute(select(ledger).where(ledger.c.account_id=='alice'))).mappings().all()
        assert sum(e['amount_microcredits'] for e in events)==remaining-100
        assert sum(e['debt_delta_microcredits'] for e in events)==debt
        assert sum(e['charged_microcredits'] for e in events)==80+second
    await core.credit(billing,'alice',100,'purchase')
    await core.credit(billing,'alice',100,'purchase')
    assert (await balance(billing))['balance_microcredits']==remaining+100-debt
    with pytest.raises(core.BillingError, match='credit_reference_conflict'):
        await core.credit(billing,'alice',101,'purchase')


async def test_review_resolution_concurrent_idempotency_and_late_usage(billing):
    kid,_=await core.create_key(billing,'alice','review')
    await core.reserve(billing,'review',kid,'model',10,10)
    await core.settle(billing,'review')
    async def resolve():
        await core.resolve_review(billing,'review','charge',500,500,actor='admin:1',reason='ticket',reference='ticket-1')
    await asyncio.gather(resolve(),resolve())
    await trusted(billing,'review',0,0)
    a=await balance(billing)
    assert a['balance_microcredits']==0 and a['debt_microcredits']==500
    with pytest.raises(core.BillingError, match='resolution_conflict'):
        await core.resolve_review(billing,'review','waive',actor='admin:1',reason='ticket',reference='ticket-1')


async def oauth(billing, status='draft'):
    kid,_=await core.create_key(billing,'alice','oauth')
    async with billing.begin() as c:
        await c.execute(insert(oauth_apps).values(id='app',owner_account_id='alice',client_id='client',name='app',domain='example.com',client_type='public',status=status))
        await c.execute(insert(oauth_grants).values(id='grant',account_id='alice',app_id='app',active_key_id=kid,scope='models:invoke credits:read',monthly_limit_microcredits=100))
        await c.execute(update(keys).where(keys.c.api_key_id==kid).values(source='oauth',oauth_grant_id='grant'))
    return kid


async def test_oauth_grant_month_survives_rotation_and_suspension(billing):
    kid=await oauth(billing,'verified')
    await core.reserve(billing,'oauth-a',kid,'model',50,10)
    new,_=await core.create_key(billing,'alice','rotated')
    async with billing.begin() as c:
        await c.execute(update(keys).where(keys.c.api_key_id==new).values(source='oauth',oauth_grant_id='grant'))
        await c.execute(update(oauth_grants).where(oauth_grants.c.id=='grant').values(active_key_id=new))
    with pytest.raises(core.BillingError,match='monthly_limit_exceeded'):
        await core.reserve(billing,'oauth-b',new,'model',30,10)
    with pytest.raises(core.BillingError,match='oauth_grant_disabled'):
        await core.reserve(billing,'oauth-old',kid,'model',1,1)
    async with billing.begin() as c:
        await c.execute(update(oauth_apps).values(status='suspended'))
    with pytest.raises(core.BillingError,match='application_suspended'):
        await core.reserve(billing,'oauth-c',new,'model',1,1)


async def test_unverified_oauth_never_consumes_welcome_or_launders_debt(billing):
    kid=await oauth(billing)
    await core.credit(billing,'alice',100,'welcome','welcome',eligibility='welcome')
    await core.reserve(billing,'oa',kid,'model',10,10)
    await trusted(billing,'oa',1100,0)
    a=await balance(billing)
    assert a['balance_microcredits']==100 and a['regular_only_debt_microcredits']==100
    # Verification later cannot change the source eligibility of the recorded debt.
    async with billing.begin() as c:
        await c.execute(update(oauth_apps).values(status='verified'))
    with pytest.raises(core.BillingError,match='debt_outstanding'):
        await core.reserve(billing,'blocked',kid,'model',1,1)
    await core.credit(billing,'alice',80,'more-welcome','welcome',eligibility='welcome')
    assert (await balance(billing))['debt_microcredits']==100
    await core.credit(billing,'alice',120,'purchase')
    a=await balance(billing)
    assert a['debt_microcredits']==0 and a['balance_microcredits']==200


async def test_price_publication_staleness_and_snapshot(billing):
    kid,_=await core.create_key(billing,'alice','price')
    await core.reserve(billing,'old',kid,'model',1,1)
    async with billing.begin() as c:
        await c.execute(update(models).values(input_price='1'))
    with pytest.raises(core.BillingError,match='price_sync_pending'):
        await core.reserve(billing,'stale',kid,'model',1,1)
    async with billing.begin() as c:
        await core.sync_price(c,'model')
        await core.sync_price(c,'model')
    await trusted(billing,'old',10,0)
    assert (await balance(billing))['balance_microcredits']==990
    async with billing.connect() as c:
        assert await c.scalar(select(func.count()).select_from(price_versions))==3  # disabled, enabled, changed
    async with billing.begin() as c:
        await core.set_global_margin(c,0,'operator','global')
        await core.configure_price(c,'model',margin_bps=10000,sales_enabled=True,actor='operator',reason='override')
    async with billing.connect() as c:
        row=await core.read_price(c,'model')
        assert row['input_rate_microcredits']==140000000


@pytest.mark.parametrize('changes,reason', [({'input_price':None},'missing_base_price'),({'model_type':'embedding'},'unsupported_model_type'),({'billing_mode':'per_request'},'unsupported_billing_mode'),({'is_active':False},'model_disabled')])
async def test_unsellable(billing,changes,reason):
    async with billing.begin() as c:
        await c.execute(update(models).values(**changes))
        row=await core.sync_price(c,'model')
        assert not row['sellable'] and row['unavailable_reason']==reason


async def test_reservation_retry_and_conflict(billing):
    kid,_=await core.create_key(billing,'alice','retry')
    rows=await asyncio.gather(core.reserve(billing,'same',kid,'model',1,1),core.reserve(billing,'same',kid,'model',1,1))
    assert rows[0]['reserved_microcredits']==rows[1]['reserved_microcredits']==3
    assert (await balance(billing))['reserved_microcredits']==3
    with pytest.raises(core.BillingError,match='request_reference_conflict'):
        await core.reserve(billing,'same',kid,'model',2,1)


async def test_interrupted_evidence_uses_each_dimension_and_no_max_output(billing):
    kid,_=await core.create_key(billing,'alice','interrupted')
    await core.reserve(billing,'i',kid,'model',100,100)
    await core.settle(billing,'i',core.UsageEvidence(1,1,source='upstream',interrupted=True,estimated_output=10))
    async with billing.connect() as c:
        r=(await c.execute(select(requests).where(requests.c.id=='i'))).mappings().one()
        assert (r['input_tokens'],r['output_tokens'],r['charged_microcredits'])==(100,10,120)


async def test_v1_migration_conversion_idempotency_and_drain(billing):
    from squirrel_commercial.schema import metadata, version, migration_snapshots
    from squirrel_commercial.migration import upgrade
    from v1_schema import metadata as v1, accounts as a1, ledger as l1, requests as r1, version as v1version
    async with billing.begin() as c:
        await c.run_sync(metadata.drop_all)
        await c.run_sync(v1.create_all)
        await c.execute(insert(v1version).values(id=1,version=1))
        await c.execute(insert(a1).values(id='old',balance=123,reserved=0,blocked=False,created_at=1))
        await c.execute(insert(l1).values(id='payment:old',account_id='old',amount=150,kind='credit',created_at=1))
        await c.execute(insert(l1).values(id='request:old',account_id='old',amount=-27,kind='consume',created_at=1))
        await c.execute(insert(r1).values(id='old',account_id='old',api_key_id=1,model='model',price_version=1,input_rate=3,output_rate=4,reserved=30,charged=27,status='review',created_at=1,updated_at=1))
    with pytest.raises(core.BillingError,match='migration_requests_not_drained'):
        await upgrade(billing)
    async with billing.begin() as c:
        await c.execute(update(r1).values(status='settled'))
    assert (await upgrade(billing))['version']==1
    with pytest.raises(core.BillingError,match='migration_backup_required'):
        await upgrade(billing,apply=True)
    assert (await upgrade(billing,apply=True,backup_ref='verified-backup'))['version']==2
    assert (await upgrade(billing,apply=True,backup_ref='verified-backup'))['already_applied']
    await core.check_version(billing)
    async with billing.connect() as c:
        a=(await c.execute(select(accounts).where(accounts.c.id=='old'))).mappings().one()
        assert a['balance']==123 and a['balance_microcredits']==1230
        r=(await c.execute(select(requests))).mappings().one()
        assert r['charged_microcredits']==270 and r['charged']==27 and r['input_rate_microcredits']==30
        assert await c.scalar(select(func.sum(ledger.c.amount_microcredits)))==1230
        assert await c.scalar(select(func.count()).select_from(migration_snapshots))==4


async def test_price_publication_concurrent_idempotency_and_reserve_has_no_price_locks(billing):
    from squirrel_commercial.schema import settings
    async def publish():
        async with billing.begin() as c:
            return await core.sync_price(c,'model')
    rows=await asyncio.gather(publish(),publish())
    assert rows[0]['version']==rows[1]['version']
    kid,_=await core.create_key(billing,'alice','no-price-locks')
    if billing.dialect.name=='postgresql':
        async with billing.begin() as c:
            await c.execute(select(settings).with_for_update())
            await c.execute(select(models).with_for_update())
            await c.execute(select(price_configs).with_for_update())
            await asyncio.wait_for(core.reserve(billing,'fast',kid,'model',1,1),timeout=2)


async def test_cross_account_credit_reference_conflict_is_typed_and_rolls_back(billing):
    async def credit(uid):
        try:
            await core.credit(billing,uid,10,'same-global-reference')
            return 'credited'
        except core.BillingError as exc:
            return exc.code
    result=await asyncio.gather(credit('alice'),credit('bob'))
    assert sorted(result)==['credit_reference_conflict','credited']
    assert (await balance(billing,'alice'))['balance_microcredits']+(await balance(billing,'bob'))['balance_microcredits']==2010


async def test_account_creation_and_cancel_offsets_ordinary_debt_using_welcome(billing):
    async with billing.begin() as c:
        await core.create_account_in_transaction(c,'new')
    await core.credit(billing,'new',10,'opening')
    kid,_=await core.create_key(billing,'new','new-key')
    await core.reserve(billing,'new-a',kid,'model',4,1)
    await core.reserve(billing,'new-b',kid,'model',2,1)
    await trusted(billing,'new-a',20,0)
    a=await balance(billing,'new')
    assert a['debt_microcredits']==14 and a['reserved_microcredits']==4
    await core.credit(billing,'new',10,'welcome-new','welcome',eligibility='welcome')
    await core.settle(billing,'new-b',core.UsageEvidence(sent_upstream=False))
    a=await balance(billing,'new')
    assert a['debt_microcredits']==0 and a['balance_microcredits']==0


async def test_migration_cli_modes(billing,monkeypatch,capsys):
    from squirrel_commercial import migrate
    import sys
    monkeypatch.setattr(migrate,'create_async_engine',lambda _:billing)
    monkeypatch.setenv('DATABASE_URL','unused')
    monkeypatch.setattr(sys,'argv',['migrate'])
    await migrate.main()
    monkeypatch.setattr(sys,'argv',['migrate','--from-version','1','--to-version','2','--dry-run'])
    await migrate.main()
    assert 'already_applied' in capsys.readouterr().out
    monkeypatch.setattr(sys,'argv',['migrate','--from-version','1'])
    with pytest.raises(SystemExit):
        await migrate.main()


@pytest.mark.parametrize('enabled',[False,True])
async def test_gateway_model_edit_price_hook_is_atomic_and_optional(billing,monkeypatch,enabled):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy import event
    from app.config import get_settings
    from app.domain.model import ModelMappingUpdate
    from app.repositories.sqlalchemy.model_repo import SQLAlchemyModelRepository
    monkeypatch.setattr(get_settings(),'COMMERCIAL_ENABLED',enabled)
    seen=[]
    def record(conn,cursor,statement,parameters,context,executemany):
        import re
        if re.search(r'\b(?:FROM|INTO|UPDATE|JOIN) billing_',statement):
            seen.append(statement)
    event.listen(billing.sync_engine,'before_cursor_execute',record)
    try:
        async with async_sessionmaker(billing,expire_on_commit=False)() as session:
            await SQLAlchemyModelRepository(session).update_mapping('model',ModelMappingUpdate(input_price=2))
    finally:
        event.remove(billing.sync_engine,'before_cursor_execute',record)
    assert bool(seen)==enabled
    async with billing.connect() as c:
        if enabled:
            row=await core.read_price(c,'model')
            assert row['input_rate_microcredits']==182000000
        else:
            with pytest.raises(core.BillingError,match='price_sync_pending'):
                await core.read_price(c,'model')


@pytest.mark.parametrize('enabled',[False,True])
async def test_gateway_models_follow_v2_sellability(billing,monkeypatch,enabled):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from app.config import get_settings
    from app.api.proxy.openai import list_models
    import app.db.session as database
    monkeypatch.setattr(get_settings(),'COMMERCIAL_ENABLED',enabled)
    monkeypatch.setattr(database,'engine',billing)
    service=AsyncMock()
    service.get_all_mappings.return_value=([SimpleNamespace(requested_model='model')],1)
    key=SimpleNamespace(key_value='sha256:test')
    assert len((await list_models(key,service))['data'])==1
    async with billing.begin() as c:
        await core.configure_price(c,'model',sales_enabled=False,actor='operator',reason='disable')
    assert len((await list_models(key,service))['data'])==(0 if enabled else 1)


@pytest.mark.parametrize('value',['10',10.5,True,-1])
def test_upstream_usage_must_be_integer_and_semantically_valid(value):
    from app.services.commercial import complete_usage
    from app.common.stream_usage import StreamUsageAccumulator
    import json
    assert not complete_usage({'usage':{'input_tokens':value,'output_tokens':0}})
    acc=StreamUsageAccumulator('anthropic','model')
    for payload in [dict(type='message_start',message={'usage':{'input_tokens':value}}),dict(type='message_delta',usage={'output_tokens':0}),dict(type='message_stop')]:
        acc.feed(('data: '+json.dumps(payload)+'\n\n').encode())
    assert not acc.finalize().final_usage


async def test_price_pending_retry_header(billing,monkeypatch):
    from app.services.commercial import commercial_call
    from app.config import get_settings
    from app.common.errors import AppError
    import app.db.session as database
    monkeypatch.setattr(get_settings(),'COMMERCIAL_ENABLED',True)
    monkeypatch.setattr(database,'engine',billing)
    kid,_=await core.create_key(billing,'alice','pending-price')
    async with billing.begin() as c:
        await c.execute(update(models).values(input_price=1))
    called=[]
    @commercial_call
    async def call(api_key_id,path,body,record_details=True):
        called.append(True)
    with pytest.raises(AppError) as exc:
        await call(kid,'/v1/messages',{'model':'model','messages':[{'content':'hi'}],'max_tokens':1})
    assert exc.value.status_code==503 and exc.value.headers=={'Retry-After':'1'}
    assert not called and (await balance(billing))['reserved_microcredits']==0


async def test_zero_month_limit_and_cross_month_settlement(billing,monkeypatch):
    kid,_=await core.create_key(billing,'alice','month-boundary')
    async with billing.begin() as c:
        await c.execute(update(keys).where(keys.c.api_key_id==kid).values(monthly_limit_microcredits=0))
    with pytest.raises(core.BillingError,match='monthly_limit_exceeded'):
        await core.reserve(billing,'zero',kid,'model',1,1)
    async with billing.begin() as c:
        await c.execute(update(keys).where(keys.c.api_key_id==kid).values(monthly_limit_microcredits=100))
    monkeypatch.setattr(core,'now',lambda:1790812799)  # 2026-09-30 23:59:59 UTC
    await core.reserve(billing,'month-old',kid,'model',10,10)
    monkeypatch.setattr(core,'now',lambda:1790812801)
    await trusted(billing,'month-old',200,0)
    await core.reserve(billing,'month-new',kid,'model',10,10)
    async with billing.connect() as c:
        rows=(await c.execute(select(months).where(months.c.owner_id==str(kid)).order_by(months.c.month))).mappings().all()
        assert len(rows)==2
        assert rows[0]['settled_microcredits']==200 and rows[0]['reserved_microcredits']==0
        assert rows[1]['settled_microcredits']==0 and rows[1]['reserved_microcredits']==30
