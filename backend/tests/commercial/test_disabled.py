"""Disabled startup must preserve the original schema and API payloads."""
import os
import subprocess
import sys


def test_disabled_boot_contract(tmp_path):
    code = r'''
import asyncio
from sqlalchemy import inspect
from app.db.session import init_db, engine, AsyncSessionLocal
from app.db.models import RequestLog
from app.main import app
from app.api.auth import auth_status
from app.domain.log import RequestLogCreate, RequestLogQuery
from app.domain.api_key import ApiKeyCreate
from app.services.log_service import LogService
from app.services.api_key_service import ApiKeyService
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository
from app.repositories.sqlalchemy.api_key_repo import SQLAlchemyApiKeyRepository
from app.common.time import utc_now
from app.services.commercial import commercial_call
async def main():
    await init_db()
    async with engine.connect() as c:
        tables = await c.run_sync(lambda x: inspect(x).get_table_names())
        columns = await c.run_sync(lambda x: [v['name'] for v in inspect(x).get_columns('request_logs')])
    assert not any(t.startswith('billing_') for t in tables)
    assert 'commercial_user_id' not in columns
    assert not hasattr(RequestLog, 'commercial_user_id')
    assert 'commercial_user_id' not in str(app.openapi())
    assert '/v1/credits' not in app.openapi()['paths']
    import httpx
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/v1/credits')).status_code == 404
    status = await auth_status(authorization=None, x_admin_token=None)
    assert set(status.model_dump()) == {'enabled','authenticated','enable_view_api_keys'}
    async with AsyncSessionLocal() as session:
        keys = ApiKeyService(SQLAlchemyApiKeyRepository(session))
        key = await keys.create(ApiKeyCreate(key_name='original-key'))
        assert (await keys.authenticate(key.key_value)).id == key.id
        logs = LogService(SQLAlchemyLogRepository(session))
        await logs.create(RequestLogCreate(request_time=utc_now(), api_key_id=key.id, trace_id='original'))
        rows, total = await logs.query(RequestLogQuery())
        assert total == 1 and 'commercial_user_id' not in rows[0].model_dump()
        await keys.delete(key.id)
    @commercial_call
    async def ordinary(**kwargs):
        return kwargs
    assert await ordinary(body={'unrestricted':'unchanged'},record_details=True) == {'body':{'unrestricted':'unchanged'},'record_details':True}
    await engine.dispose()
asyncio.run(main())
'''
    env={**os.environ,'COMMERCIAL_ENABLED':'false','DATABASE_TYPE':'sqlite','DATABASE_URL':'sqlite+aiosqlite:///'+str(tmp_path/'original.db'),'MCP_ENABLED':'false'}
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True)
    assert result.returncode == 0, result.stdout+result.stderr
