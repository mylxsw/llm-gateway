import pytest
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.models import Base
from squirrel_commercial import core
from squirrel_commercial.schema import accounts, prices

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

