import pytest
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.models import Base
from squirrel_commercial import core
from squirrel_commercial.schema import accounts, prices, buckets

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
        await c.execute(insert(accounts),[dict(id='alice',blocked=False,balance=0,reserved=0,balance_microcredits=1000,created_at=core.now()),dict(id='bob',blocked=False,balance=0,reserved=0,balance_microcredits=1000,created_at=core.now())])
        await c.execute(insert(prices).values(model='model',version=1,enabled=True,input_rate=1000000,output_rate=2000000,max_input=1000,max_output=1000))
        for uid in ('alice', 'bob'):
            await c.execute(insert(buckets), [dict(account_id=uid, kind='regular', balance_microcredits=1000), dict(account_id=uid, kind='welcome', balance_microcredits=0)])
        from app.db.models import ModelMapping
        await c.execute(insert(ModelMapping.__table__).values(requested_model='model', strategy='priority', model_type='chat', input_price='0.0109', output_price='0.0219', billing_mode='token_flat', is_active=True))
        await core.configure_price(c, 'model', sales_enabled=True, actor='test', reason='Fixture')
    yield engine
    await engine.dispose()
    if admin:
        async with admin.begin() as c:
            await c.execute(text('DROP SCHEMA ' + schema + ' CASCADE'))
        await admin.dispose()



async def settle_usage(engine, rid, input_tokens=None, output_tokens=None, failed=False):
    # Test shorthand for a verified complete upstream response or proven local cancellation.
    return await core.settle(engine, rid, core.UsageEvidence(input_tokens=input_tokens, output_tokens=output_tokens,
        source='upstream', terminal_complete=input_tokens is not None and output_tokens is not None,
        sent_upstream=not failed))
