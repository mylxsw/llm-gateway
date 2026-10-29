"""Regressions for G1–G8 and G10, including actual proxy/response lifecycles."""
import asyncio
import json
from types import SimpleNamespace
from starlette.requests import ClientDisconnect
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.common.errors import AppError
from app.common.protocol_conversion import convert_request_for_supplier
from app.common.stream_usage import StreamUsageAccumulator
from app.common.time import utc_now
from app.config import get_settings
from app.domain.api_key import ApiKeyUpdate
from app.domain.log import RequestLogCreate
from app.domain.model import ModelMapping
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services import commercial
from app.services.api_key_service import ApiKeyService
from app.services.proxy_service import ProxyService
from app.repositories.sqlalchemy.api_key_repo import SQLAlchemyApiKeyRepository
from squirrel_commercial import core
from squirrel_commercial.schema import accounts, keys, ledger, prices, requests, resolutions


def event(payload):
    return ('data: ' + json.dumps(payload) + '\n\n').encode()


@pytest.fixture
async def commercial_gateway(billing, monkeypatch, tmp_path):
    import app.db.session as database
    monkeypatch.setattr(database, 'engine', billing)
    monkeypatch.setattr(get_settings(), 'COMMERCIAL_ENABLED', True)
    monkeypatch.setattr(get_settings(), 'COMMERCIAL_RECOVERY_DIR', str(tmp_path / 'journal'))
    async with billing.begin() as c:
        await c.execute(update(accounts).values(balance=100000))
        await c.execute(update(prices).values(max_input=5000))
    kid, _ = await core.create_key(billing, 'alice', 'test')
    return billing, kid


@pytest.mark.parametrize('source,target,path', [
    ('openai', 'openai', '/v1/chat/completions'),
    ('anthropic', 'openai', '/v1/messages'),
])
def test_commercial_stream_requests_include_usage(monkeypatch, source, target, path):
    monkeypatch.setattr(get_settings(), 'COMMERCIAL_ENABLED', True)
    token = commercial.request_id.set('commercial')
    try:
        _, body = convert_request_for_supplier(
            request_protocol=source, supplier_protocol=target, path=path,
            body={'model': 'model', 'stream': True, 'max_tokens': 100,
                  'messages': [{'role': 'user', 'content': 'hi'}],
                  'stream_options': {'include_usage': False}}, target_model='model')
        assert body['stream_options']['include_usage'] is True
        assert 'stream_options' not in commercial.apply_stream_usage(body, target, {'supports_stream_usage': False})
        assert commercial.apply_stream_usage(body, 'anthropic') is body
    finally:
        commercial.request_id.reset(token)


def test_only_terminal_usage_is_trusted():
    acc = StreamUsageAccumulator('anthropic', 'model')
    acc.feed(event({'type': 'message_start', 'message': {'usage': {'input_tokens': 10, 'output_tokens': 1}}}))
    assert not acc.finalize().final_usage
    acc.feed(event({'type': 'message_delta', 'usage': {'output_tokens': 10}}))
    assert not acc.finalize().final_usage
    acc.feed(event({'type': 'message_stop'}))
    assert acc.finalize().final_usage
    acc = StreamUsageAccumulator('openai', 'model')
    acc.feed(event({'choices': [{'delta': {}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 1}}))
    assert not acc.finalize().final_usage
    acc.feed(event({'choices': [], 'usage': {'prompt_tokens': 10, 'completion_tokens': 0}}))
    result = acc.finalize()
    assert result.final_usage and result.output_tokens == 0


async def make_stream(monkeypatch, kid, *, upstream='openai', client='openai', mode='complete', options=None, initial_status=None):
    mapping = ModelMapping(requested_model='model', strategy='priority', is_active=True,
                           created_at=utc_now(), updated_at=utc_now())
    candidate = CandidateProvider(provider_id=1, provider_name='test', base_url='https://example.com',
                                  protocol=upstream, api_key='test', target_model='model', priority=1,
                                  provider_options=options)
    logs = AsyncMock()
    logs.create_initial.return_value = 991
    logs.get_provider_mappings.return_value = []
    service = ProxyService(model_repo=logs, provider_repo=AsyncMock(), log_repo=logs)
    service._resolve_candidates = AsyncMock(return_value=(mapping, [candidate], 8, client, {}))
    closed = asyncio.Event()
    seen = []

    async def forward_stream(**kwargs):
        seen.append(kwargs['body'])
        response = ProviderResponse(status_code=initial_status or 200)
        try:
            if initial_status:
                yield event({'error': {'message': 'upstream rejected'}}), response
                return
            if upstream == 'anthropic':
                yield event({'type': 'message_start', 'message': {'id': 'msg', 'type': 'message', 'role': 'assistant',
                            'model': 'model', 'content': [], 'usage': {'input_tokens': 10, 'output_tokens': 1}}}), response
                yield event({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': 'hello world ' * 20}}), response
            else:
                yield event({'choices': [{'delta': {'content': 'hello world ' * 20}}]}), response
            if mode == 'wait':
                await asyncio.Event().wait()
            elif mode in ('error', 'upstream_timeout'):
                yield b'', ProviderResponse(status_code=504 if mode == 'upstream_timeout' else 502, error='failed after output')
            elif mode == 'complete':
                if upstream == 'anthropic':
                    yield event({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 0}}), response
                    yield event({'type': 'message_stop'}), response
                else:
                    yield event({'choices': [], 'usage': {'prompt_tokens': 10, 'completion_tokens': 0}}), response
                    yield b'data: [DONE]\n\n', response
        finally:
            closed.set()
            if mode == 'close_failure':
                raise OSError('upstream close failed')

    provider = AsyncMock()
    provider.forward_stream = forward_stream
    monkeypatch.setattr('app.services.proxy_service.get_provider_client', lambda _: provider)
    path = '/v1/messages' if client == 'anthropic' else '/v1/chat/completions'
    result = await service.process_request_stream(
        api_key_id=kid, api_key_name='test', request_protocol=client, path=path, request_url=path,
        method='POST', headers={}, body={'model': 'model', 'stream': True, 'max_tokens': 100,
                                       'messages': [{'role': 'user', 'content': 'hi'}]})
    return result, service, logs, closed, seen


async def request_row(engine, rid):
    async with engine.connect() as c:
        return (await c.execute(select(requests).where(requests.c.id == rid))).mappings().one()


@pytest.mark.parametrize('upstream,client', [('openai', 'openai'), ('anthropic', 'anthropic'), ('anthropic', 'openai'), ('openai', 'anthropic')])
@pytest.mark.parametrize('mode', ['complete', 'eof', 'error', 'upstream_timeout', 'close', 'close_failure', 'unstarted', 'cancel', 'timeout'])
async def test_stream_settlement_lifecycle(commercial_gateway, monkeypatch, upstream, client, mode):
    engine, kid = commercial_gateway
    (response, stream, info), owner, logs, closed, seen = await make_stream(
        monkeypatch, kid, upstream=upstream, client=client, mode='wait' if mode in ('cancel', 'timeout') else mode)
    if mode == 'unstarted':
        # Sending response headers can fail before StreamingResponse reads one item.
        async def send(message):
            raise OSError('connection lost before iteration')
        with pytest.raises(ClientDisconnect):
            await commercial.SettlingStreamingResponse(stream)(
                {'type': 'http', 'asgi': {'spec_version': '2.4'}}, AsyncMock(), send)
    elif mode in ('close', 'close_failure'):
        while b'hello' not in await anext(stream):
            pass
        await stream.aclose()
    elif mode in ('cancel', 'timeout'):
        while b'hello' not in await anext(stream):
            pass
        if mode == 'timeout':
            stream.deadline = asyncio.get_running_loop().time() - 1
            with pytest.raises(TimeoutError):
                await anext(stream)
        else:
            task = asyncio.create_task(anext(stream))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    else:
        _ = [chunk async for chunk in stream]
    assert closed.is_set()
    assert not owner._commercial_identities
    row = await request_row(engine, info['trace_id'])
    assert row['status'] == 'settled'
    assert logs.update.call_args.args[1].usage_details['stream_started'] is True
    if mode == 'complete':
        assert row['input_tokens'] == 10 and row['output_tokens'] == 0
    elif mode == 'unstarted':
        assert row['input_tokens'] >= 8 and row['output_tokens'] >= 0
    else:
        assert row['input_tokens'] >= 8 and row['output_tokens'] > 1
    if upstream == 'openai':
        assert seen[0]['stream_options']['include_usage'] is True
    from app.services.active_requests import active_requests
    assert not await active_requests.is_active(991)
    await stream.aclose()
    async with engine.connect() as c:
        assert len((await c.execute(select(ledger))).all()) == 1
        assert await c.scalar(select(accounts.c.reserved).where(accounts.c.id == 'alice')) == 0
    assert commercial.request_id.get() is None


@pytest.mark.parametrize('stream', [False, True])
async def test_admin_model_test_allowed_without_billing(commercial_gateway, stream):
    engine, _ = commercial_gateway
    previous_only = get_settings().COMMERCIAL_ONLY
    get_settings().COMMERCIAL_ONLY = True
    try:
        @commercial.commercial_call
        async def call(api_key_id, admin_model_test=False):
            return 'tested'
        assert await call(None, admin_model_test=True) == 'tested'
        with pytest.raises(AppError) as exc:
            await call(None)
        assert exc.value.status_code == 403
        from app.api.admin.models import ModelTestRequest, test_model as run_model_test
        service = AsyncMock()
        if stream:
            async def chunks():
                yield event({'choices': [{'delta': {'content': 'ok'}}]})
            service.process_request_stream.return_value = (ProviderResponse(status_code=200), chunks(), {})
        else:
            service.process_request.return_value = (ProviderResponse(status_code=200, body={'choices': [{'message': {'content': 'ok'}}]}), {})
        await run_model_test('model', ModelTestRequest(protocol='openai', stream=stream), service)
        method = service.process_request_stream if stream else service.process_request
        assert method.call_args.kwargs['admin_model_test'] is True
        async with engine.connect() as c:
            assert not (await c.execute(select(requests))).all()
    finally:
        get_settings().COMMERCIAL_ONLY = previous_only


@pytest.mark.parametrize('enabled', [False, True])
async def test_admin_replay_rejects_hashed_keys(commercial_gateway, monkeypatch, enabled):
    engine, kid = commercial_gateway
    monkeypatch.setattr(get_settings(), 'COMMERCIAL_ENABLED', enabled)
    from app.api.admin.logs import execute_playground_request, retry_log, PlaygroundExecuteRequest
    logs, proxy = AsyncMock(), AsyncMock()
    logs.get_by_id.return_value = SimpleNamespace(api_key_id=kid, id=1, request_path='/v1/chat/completions', detail_available=True, request_body={})
    async with async_sessionmaker(engine)() as session:
        service = ApiKeyService(SQLAlchemyApiKeyRepository(session))
        response = await execute_playground_request(1, PlaygroundExecuteRequest(request_body={}), logs, proxy, service)
        assert response.status_code == 403 and b'commercial_key_hidden' in response.body
        response = await retry_log(1, SimpleNamespace(), logs, service)
        assert response.status_code == 403 and b'commercial_key_hidden' in response.body
        with pytest.raises(AppError) as exc:
            await service.get_raw_key_value(kid)
        assert exc.value.status_code == 403
        assert not proxy.process_request.called and not proxy.process_request_stream.called


async def test_admin_rename_conflict_returns_409(commercial_gateway):
    engine, kid = commercial_gateway
    other, _ = await core.create_key(engine, 'bob', 'other')
    async with engine.begin() as c:
        await c.execute(text('UPDATE api_keys SET key_name=:name WHERE id=:id'), {'name': 'taken', 'id': other})
    async with async_sessionmaker(engine)() as session:
        service = ApiKeyService(SQLAlchemyApiKeyRepository(session))
        with pytest.raises(AppError) as exc:
            await service.update(kid, ApiKeyUpdate(key_name='taken'))
        assert exc.value.status_code == 409
    async with engine.connect() as c:
        assert (await c.scalar(text('SELECT key_name FROM api_keys WHERE id=:id'), {'id': kid})) != 'taken'


async def test_recovery_filters_history_isolates_errors_and_archives(commercial_gateway, monkeypatch):
    engine, kid = commercial_gateway
    for rid in ('old', 'bad', 'good', 'unknown'):
        await core.reserve(engine, rid, kid, 'model', 100, 100)
    await core.settle(engine, 'old', 1, 1)
    async with engine.begin() as c:
        await c.execute(insert(resolutions), [dict(request_id=rid, action='waive', reason='verified', created_at=core.now()) for rid in ('old', 'bad', 'good')])
    calls = []
    original = core.settle
    async def settle(engine, request_id, *args, **kwargs):
        rid = request_id
        calls.append(rid)
        if rid == 'bad':
            raise OSError('database temporarily unavailable')
        return await original(engine, rid, *args, **kwargs)
    monkeypatch.setattr(core, 'settle', settle)
    path = commercial.write_journal({'request_id': 'unknown'})
    probe = commercial.write_journal({'request_id': 'probe-leftover'}, probe=True)
    await commercial.recover()
    assert 'old' not in calls and 'good' in calls
    assert (await request_row(engine, 'good'))['status'] == 'cancelled'
    assert (await request_row(engine, 'unknown'))['status'] == 'review'
    assert not path.exists() and (path.parent / 'review' / path.name).exists()
    assert probe.suffix == '.probe' and probe.exists()
    calls.clear()
    await commercial.recover()
    assert calls == ['bad']
