import asyncio
import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.models import Base
from squirrel_commercial import core
from squirrel_commercial.schema import accounts, prices, requests, keys, ledger

@pytest.fixture
async def billing(tmp_path):
    import os, uuid
    url = os.environ.get('BILLING_TEST_DATABASE_URL')
    schema = 'test_' + uuid.uuid4().hex
    admin = None
    if url:
        admin = create_async_engine(url)
        async with admin.begin() as c:
            await c.execute(text('CREATE SCHEMA ' + schema))
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    else:
        engine = create_async_engine('sqlite+aiosqlite:///' + str(tmp_path/'billing.db'))
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    await core.migrate(engine)
    async with engine.begin() as c:
        await c.execute(insert(accounts),[dict(id='alice',blocked=False,balance=1000,reserved=0,created_at=core.now()),dict(id='bob',blocked=False,balance=1000,reserved=0,created_at=core.now())])
        await c.execute(insert(prices).values(model='model',version=1,enabled=True,input_rate=1000000,output_rate=2000000,max_input=1000,max_output=1000))
    yield engine
    await engine.dispose()
    if admin:
        async with admin.begin() as c:
            await c.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        await admin.dispose()

async def test_keys_and_isolation(billing):
    kid, token=await core.create_key(billing,'alice','laptop')
    async with billing.connect() as c:
        stored=await c.scalar(text('SELECT key_value FROM api_keys WHERE id=:id'),{'id':kid})
        assert stored==core.digest(token) and stored != token
        assert not await c.scalar(text('SELECT record_details FROM api_keys WHERE id=:id'),{'id':kid})
    with pytest.raises(core.BillingError):
        await core.user_key_action(billing,'bob',kid,'revoke')
    await core.user_key_action(billing,'alice',kid,'revoke')
    with pytest.raises(core.BillingError):
        await core.user_key_action(billing,'alice',kid,'resume')
    async with billing.connect() as c:
        assert await c.scalar(text('SELECT id FROM api_keys WHERE id=:id'),{'id':kid})==kid

async def test_admin_disable_not_cleared_by_resume(billing):
    kid,_=await core.create_key(billing,'alice','laptop')
    async with billing.begin() as c:
        await c.execute(text('UPDATE api_keys SET is_active=false WHERE id=:id'),{'id':kid})
    await core.user_key_action(billing,'alice',kid,'resume')
    with pytest.raises(core.BillingError):
        await core.reserve(billing,'r',kid,'model',100,100)

async def test_concurrent_reservation_and_once_only_settlement(billing):
    kid,_=await core.create_key(billing,'alice','laptop')
    async def reserve(rid):
        try:
            await core.reserve(billing,rid,kid,'model',100,300)
            return rid
        except core.BillingError:
            return None
    result=await asyncio.gather(reserve('one'),reserve('two'))
    assert sum(v is not None for v in result)==1
    rid=next(v for v in result if v)
    await asyncio.gather(core.settle(billing,rid,50,20),core.settle(billing,rid,50,20))
    async with billing.connect() as c:
        a=(await c.execute(select(accounts).where(accounts.c.id=='alice'))).mappings().one()
        assert a['balance']==910 and a['reserved']==0
        assert len((await c.execute(select(ledger))).all())==1

async def test_price_snapshot_unknown_and_credit_idempotency(billing):
    kid,_=await core.create_key(billing,'alice','laptop')
    await core.reserve(billing,'one',kid,'model',100,100)
    async with billing.begin() as c:
        await c.execute(update(prices).values(input_rate=9000000,version=2))
    await core.settle(billing,'one')
    async with billing.connect() as c:
        assert await c.scalar(select(requests.c.status))=='review'
    await core.settle(billing,'one',10,10)
    await core.credit(billing,'alice',100,'payment:test')
    await core.credit(billing,'alice',100,'payment:test')
    with pytest.raises(core.BillingError):
        await core.credit(billing,'bob',100,'payment:test')
    async with billing.connect() as c:
        assert await c.scalar(select(accounts.c.balance).where(accounts.c.id=='alice'))==1070

async def test_digest_not_a_bearer_secret(billing):
    from app.repositories.sqlalchemy.api_key_repo import SQLAlchemyApiKeyRepository
    kid,token=await core.create_key(billing,'alice','laptop')
    async with async_sessionmaker(billing)() as session:
        repo=SQLAlchemyApiKeyRepository(session)
        assert (await repo.get_by_key_value(token)).id==kid
        assert await repo.get_by_key_value(core.digest(token)) is None

async def test_gateway_key_lifecycle_and_logging_policy(billing,monkeypatch):
    import app.db.session as database
    from app.config import get_settings
    from app.services.api_key_service import ApiKeyService
    from app.repositories.sqlalchemy.api_key_repo import SQLAlchemyApiKeyRepository
    from app.domain.api_key import ApiKeyUpdate
    from app.common.errors import AuthenticationError
    from app.domain.log import RequestLogCreate
    from app.services.proxy_service import ProxyService
    from app.services.commercial import account_id, request_id
    from app.common.time import utc_now
    from app.logging_config import CommercialPrivacyFilter
    import logging
    monkeypatch.setattr(database,'engine',billing)
    monkeypatch.setattr(get_settings(),'COMMERCIAL_ENABLED',True)
    kid,token=await core.create_key(billing,'alice','Laptop')
    async with async_sessionmaker(billing,expire_on_commit=False)() as session:
        service=ApiKeyService(SQLAlchemyApiKeyRepository(session))
        key=await service.authenticate(token)
        assert key.record_details is False
        with pytest.raises(AuthenticationError):
            await service.get_raw_key_value(kid)
        with pytest.raises(AuthenticationError):
            await service.update(kid,ApiKeyUpdate(is_mcp_admin=True))
        await service.update(kid,ApiKeyUpdate(record_details=True))
        await session.rollback()
        session.expire_all()
        assert (await service.authenticate(token)).record_details is True
        await service.delete(kid)
        with pytest.raises(AuthenticationError):
            await service.authenticate(token)
    a=account_id.set('alice'); r=request_id.set('request-test')
    try:
        log=RequestLogCreate(request_time=utc_now(),trace_id='request-test',error_info='PRIVATE-ERROR',usage_details={'source':'upstream','raw_usage':{'secret':'no'},'input_tokens':20})
        proxy=ProxyService(None,None,None)
        await proxy._commercial_log_identity(log)
        assert log.commercial_user_id=='alice' and 'PRIVATE' not in log.error_info
        assert 'raw_usage' not in log.usage_details
        record=logging.LogRecord('app.provider',logging.ERROR,'',0,'SECRET %s',('PROMPT',),None)
        assert CommercialPrivacyFilter().filter(record)
        assert 'PROMPT' not in record.getMessage()
    finally:
        account_id.reset(a);request_id.reset(r)

async def test_blocking_unknown_usage_and_overage(billing):
    kid,_=await core.create_key(billing,'alice','Laptop')
    await core.reserve(billing,'one',kid,'model',10,10)
    await core.settle(billing,'one',1000,1000)
    async with billing.connect() as c:
        assert await c.scalar(select(requests.c.status).where(requests.c.id=='one'))=='review'
        assert await c.scalar(select(accounts.c.balance).where(accounts.c.id=='alice'))==1000
    with pytest.raises(core.BillingError):
        await core.reserve(billing,'two',kid,'model',10,10)
    await core.settle(billing,'one',failed=True)
    async with billing.connect() as c:
        assert await c.scalar(select(accounts.c.reserved).where(accounts.c.id=='alice'))==0

async def test_recovery_journal_survives_database_failure(billing,monkeypatch,tmp_path):
    import app.db.session as database
    import app.services.commercial as integration
    from app.config import get_settings
    from app.domain.log import RequestLogCreate
    from app.common.time import utc_now
    monkeypatch.setattr(database,'engine',billing)
    monkeypatch.setattr(get_settings(),'COMMERCIAL_ENABLED',True)
    monkeypatch.setattr(get_settings(),'COMMERCIAL_RECOVERY_DIR',str(tmp_path/'recovery'))
    kid,_=await core.create_key(billing,'alice','test')
    await core.reserve(billing,'durable',kid,'model',100,100)
    log=RequestLogCreate(request_time=utc_now(),trace_id='durable',commercial_user_id='alice',response_status=200,input_tokens=10,output_tokens=5,usage_details={'source':'upstream'})
    original=core.settle
    async def fail(*args,**kwargs):
        raise OSError('database unavailable')
    monkeypatch.setattr(core,'settle',fail)
    with pytest.raises(OSError):
        await integration.settle_log(log)
    files=list((tmp_path/'recovery').glob('*.json'))
    assert len(files)==1 and 'request_body' not in files[0].read_text()
    monkeypatch.setattr(core,'settle',original)
    await integration.recover()
    await integration.recover()
    async with billing.connect() as c:
        assert await c.scalar(select(accounts.c.balance).where(accounts.c.id=='alice'))==980
    assert not list((tmp_path/'recovery').glob('*.json'))

async def test_global_detail_argument_cannot_enable_commercial_logging(billing,monkeypatch):
    import app.db.session as database
    from app.config import get_settings
    from app.services.commercial import commercial_call
    monkeypatch.setattr(database,'engine',billing)
    monkeypatch.setattr(get_settings(),'COMMERCIAL_ENABLED',True)
    async with billing.begin() as c:
        await c.execute(update(prices).values(max_input=5000,input_rate=1000,output_rate=1000))
    kid,_=await core.create_key(billing,'alice','test')
    seen=[]
    @commercial_call
    async def process_request(self,api_key_id,path,body,record_details=True):
        seen.append(record_details)
        return 'result'
    body={'model':'model','messages':[{'role':'user','content':'text'}],'max_tokens':20}
    assert await process_request(None,api_key_id=kid,path='/v1/chat/completions',body=body,record_details=True)=='result'
    assert seen==[False]
    await core.admin_key_action(billing,kid,{'record_details':True})
    await process_request(None,api_key_id=kid,path='/v1/chat/completions',body=body,record_details=False)
    assert seen==[False,True]

async def test_commercial_identity_survives_log_list_serialization(billing):
    from app.services.log_service import LogService
    from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository
    from app.domain.log import RequestLogCreate,RequestLogQuery
    from app.common.time import utc_now
    async with async_sessionmaker(billing,expire_on_commit=False)() as session:
        service=LogService(SQLAlchemyLogRepository(session))
        await service.create(RequestLogCreate(request_time=utc_now(),commercial_user_id='alice',trace_id='a'))
        await service.create(RequestLogCreate(request_time=utc_now(),commercial_user_id='bob',trace_id='b'))
        rows,total=await service.query(RequestLogQuery(commercial_user_id='alice'))
        assert total==1 and rows[0].commercial_user_id=='alice'
