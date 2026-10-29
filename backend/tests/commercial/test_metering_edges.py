from conftest import settle_usage
"""Failure boundaries and administration regressions for commercial metering."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.common.errors import AppError
from app.common.time import utc_now
from app.config import get_settings
from app.domain.log import RequestLogCreate
from app.repositories.sqlalchemy.api_key_repo import SQLAlchemyApiKeyRepository
from app.services import commercial
from app.services.api_key_service import ApiKeyService
from squirrel_commercial import core
from squirrel_commercial.schema import accounts, requests
from test_metering import commercial_gateway, make_stream, request_row


@pytest.mark.parametrize('failure', [asyncio.CancelledError, TimeoutError])
async def test_interrupted_before_response_settles_estimate(commercial_gateway, failure):
    engine, kid = commercial_gateway
    owner = SimpleNamespace(_commercial_identities={})
    @commercial.commercial_call
    async def call(self, api_key_id, path, body, record_details=True):
        self._commercial_identities[commercial.request_id.get()] = commercial.account_id.get()
        raise failure()
    with pytest.raises(failure):
        await call(owner, kid, '/v1/chat/completions',
                   {'model': 'model', 'max_tokens': 100, 'messages': [{'role': 'user', 'content': 'hello'}]})
    async with engine.connect() as c:
        row = (await c.execute(select(requests))).mappings().one()
        assert row['status'] == 'settled' and row['input_tokens'] > 0 and row['output_tokens'] == 0
    assert owner._commercial_identities == {}
    assert commercial.request_id.get() is None and commercial.account_id.get() is None


@pytest.mark.parametrize('status,is_stream,usage,expected', [
    (502, True, {'stream_started': True}, 'review'),
    (429, True, {'stream_started': False}, 'review'),
    (500, True, {'stream_started': False}, 'review'),
    (504, True, {'stream_started': False}, 'review'),
    (502, True, {'source': 'upstream', 'response_complete': True, 'final_usage': True}, 'settled'),
    (504, False, {'source': 'estimated'}, 'review'),
    (499, True, {'source': 'mixed'}, 'settled'),
    (400, False, None, 'review'),
    (200, False, {'source': 'upstream', 'response_complete': True}, 'settled'),
])
async def test_settlement_failure_policy(commercial_gateway, status, is_stream, usage, expected):
    engine, kid = commercial_gateway
    await core.reserve(engine, 'edge', kid, 'model', 100, 100)
    has_usage = usage is not None and 'source' in usage
    await commercial.settle_log(RequestLogCreate(
        request_time=utc_now(), trace_id='edge', commercial_user_id='alice',
        response_status=status, is_stream=is_stream, input_tokens=10 if has_usage else None,
        output_tokens=0 if has_usage else None, usage_details=usage))
    row = await request_row(engine, 'edge')
    assert row['status'] == expected
    if expected == 'settled':
        assert row['charged_microcredits'] == (100 if status == 499 else 10)


async def test_nonstream_zero_usage_is_not_reestimated(commercial_gateway, monkeypatch):
    from app.domain.model import ModelMapping
    from app.providers.base import ProviderResponse
    from app.rules.models import CandidateProvider
    from app.services.proxy_service import ProxyService
    engine, kid = commercial_gateway
    logs = AsyncMock()
    logs.create_initial.return_value = 992
    logs.get_provider_mappings.return_value = []
    service = ProxyService(logs, AsyncMock(), logs)
    mapping = ModelMapping(requested_model='model', strategy='priority', is_active=True, created_at=utc_now(), updated_at=utc_now())
    candidate = CandidateProvider(provider_id=1, provider_name='test', base_url='https://example.com', protocol='openai', api_key='test', target_model='model', priority=1)
    service._resolve_candidates = AsyncMock(return_value=(mapping, [candidate], 8, 'openai', {}))
    provider = AsyncMock()
    provider.forward.return_value = ProviderResponse(status_code=200, body={
        'choices': [{'message': {'content': ''}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 0, 'total_tokens': 10}})
    monkeypatch.setattr('app.services.proxy_service.get_provider_client', lambda _: provider)
    _, info = await service.process_request(api_key_id=kid, api_key_name='test', request_protocol='openai',
        path='/v1/chat/completions', request_url=None, method='POST', headers={},
        body={'model': 'model', 'max_tokens': 100, 'messages': [{'role': 'user', 'content': 'hi'}]}, force_parse_response=True)
    row = await request_row(engine, info['trace_id'])
    assert row['status'] == 'settled' and row['output_tokens'] == 0 and row['input_tokens'] == 10
    assert logs.update.call_args.args[1].usage_details['source'] == 'upstream'


async def test_provider_can_explicitly_disable_stream_usage(commercial_gateway, monkeypatch):
    _, kid = commercial_gateway
    (_, stream, _), _, _, _, seen = await make_stream(monkeypatch, kid, options={'supports_stream_usage': False})
    _ = [chunk async for chunk in stream]
    assert 'stream_options' not in seen[0]


async def test_recovery_database_failure_does_not_break_response_close(commercial_gateway, monkeypatch):
    engine, kid = commercial_gateway
    (_, stream, info), owner, _, closed, _ = await make_stream(monkeypatch, kid)
    original = core.settle
    async def fail(*args, **kwargs):
        raise OSError('database unavailable')
    monkeypatch.setattr(core, 'settle', fail)
    await stream.aclose()
    assert closed.is_set() and not owner._commercial_identities
    monkeypatch.setattr(core, 'settle', original)
    await commercial.recover()
    assert (await request_row(engine, info['trace_id']))['status'] == 'settled'


async def test_recovery_skips_terminal_journals_and_old_reservations_review(commercial_gateway):
    engine, kid = commercial_gateway
    await core.reserve(engine, 'old', kid, 'model', 100, 100)
    await core.reserve(engine, 'done', kid, 'model', 100, 100)
    await settle_usage(engine, 'done', 10, 0)
    path = commercial.write_journal({'request_id': 'done', 'failed': True})
    async with engine.begin() as c:
        await c.execute(update(requests).where(requests.c.id == 'old').values(updated_at=core.now() - 10801))
    await commercial.recover()
    assert not path.exists()
    assert (await request_row(engine, 'done'))['status'] == 'settled'
    assert (await request_row(engine, 'old'))['status'] == 'review'


async def test_rename_race_translates_integrity_error(commercial_gateway, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncConnection
    engine, kid = commercial_gateway
    original = AsyncConnection.execute
    async def execute(self, statement, *args, **kwargs):
        if str(statement).startswith('UPDATE api_keys SET key_name='):
            raise IntegrityError(str(statement), {}, Exception('unique constraint'))
        return await original(self, statement, *args, **kwargs)
    monkeypatch.setattr(AsyncConnection, 'execute', execute)
    with pytest.raises(core.BillingError) as exc:
        await core.admin_key_action(engine, kid, {'key_name': 'new-name'})
    assert exc.value.status == 409


async def test_ordinary_replay_check_does_not_block_normal_keys(commercial_gateway):
    engine, _ = commercial_gateway
    async with engine.begin() as c:
        result = await c.execute(text("INSERT INTO api_keys (key_name,key_value,is_active,record_details,is_mcp_admin,created_at) VALUES ('normal','sk-normal',true,true,false,CURRENT_TIMESTAMP) RETURNING id"))
        kid = result.scalar_one()
    async with async_sessionmaker(engine)() as session:
        await ApiKeyService(SQLAlchemyApiKeyRepository(session)).assert_replay_allowed(kid)


async def test_disabled_recovery_and_logging_do_not_query_database(monkeypatch):
    monkeypatch.setattr(get_settings(), 'COMMERCIAL_ENABLED', False)
    await commercial.recover()
    await commercial.settle_log(SimpleNamespace())


async def test_cancellation_before_first_upstream_event_cleans_tracker(commercial_gateway, monkeypatch):
    from app.services.active_requests import active_requests
    engine, kid = commercial_gateway
    # make_stream normally emits promptly; hold the first read inside retry.
    from app.services.retry_handler import RetryHandler
    entered = asyncio.Event()
    closed = asyncio.Event()
    async def waiting(*args, **kwargs):
        try:
            entered.set()
            await asyncio.Event().wait()
            yield
        finally:
            closed.set()
    monkeypatch.setattr(RetryHandler, 'execute_with_retry_stream', waiting)
    task = asyncio.create_task(make_stream(monkeypatch, kid))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set() and not await active_requests.is_active(991)
    async with engine.connect() as c:
        row = (await c.execute(select(requests))).mappings().one()
        assert row['status'] == 'settled' and row['input_tokens'] > 0


def test_openai_compatible_terminal_usage_with_finish_reason():
    from app.common.stream_usage import StreamUsageAccumulator
    from test_metering import event
    accumulator = StreamUsageAccumulator('openai', 'model')
    accumulator.feed(event({'choices': [{'delta': {}, 'finish_reason': 'stop'}],
                            'usage': {'prompt_tokens': 10, 'completion_tokens': 0}}))
    assert not accumulator.finalize().final_usage
    accumulator.feed(b'data: [DONE]\n\n')
    assert accumulator.finalize().final_usage
    accumulator = StreamUsageAccumulator('openai', 'model')
    accumulator.feed(event({'type': 'response.completed', 'response': {'usage': {'input_tokens': 10, 'output_tokens': 0}}}))
    assert not accumulator.finalize().final_usage
    accumulator.feed(b'data: [DONE]\n\n')
    assert accumulator.finalize().final_usage


@pytest.mark.parametrize('protocol', ['openai', 'anthropic'])
@pytest.mark.parametrize('status', [400, 429, 500, 502, 504])
async def test_initial_stream_error_releases_reservation(commercial_gateway, monkeypatch, protocol, status):
    from app.services.active_requests import active_requests
    engine, kid = commercial_gateway
    monkeypatch.setattr(get_settings(), 'RETRY_MAX_ATTEMPTS', 1)
    monkeypatch.setattr(get_settings(), 'RETRY_DELAY_MS', 0)
    result, owner, logs, closed, _ = await make_stream(
        monkeypatch, kid, upstream=protocol, client=protocol, initial_status=status)
    response, stream, info = result
    assert response.status_code == status
    # Exercise the controller's actual close-before-iteration branch.
    proxy = SimpleNamespace(process_request_stream=AsyncMock(return_value=result))
    body = {'model': 'model', 'stream': True, 'max_tokens': 100,
            'messages': [{'role': 'user', 'content': 'hi'}]}
    request = SimpleNamespace(headers={}, url='https://example.com/v1/messages', method='POST',
                              json=AsyncMock(return_value=body))
    key = SimpleNamespace(id=kid, key_name='test', record_details=False)
    if protocol == 'openai':
        from app.api.proxy.openai import _handle_proxy_request_with_body
        result = await _handle_proxy_request_with_body(request, key, proxy, '/v1/chat/completions', body)
    else:
        from app.api.proxy.anthropic import create_message
        result = await create_message(request, key, proxy)
    assert result.status_code == status
    row = await request_row(engine, info['trace_id'])
    assert row['status'] == 'review' and row['charged_microcredits'] == 0
    assert logs.update.call_args.args[1].usage_details['stream_started'] is False
    async with engine.connect() as c:
        account = (await c.execute(select(accounts).where(accounts.c.id == 'alice'))).mappings().one()
        assert account['reserved_microcredits'] > 0 and account['balance_microcredits'] == 100000
        assert await c.scalar(select(requests.c.id).where(requests.c.status == 'review'))
    assert closed.is_set() and not owner._commercial_identities
    assert not await active_requests.is_active(991)
    # A transient upstream error must not stop the next paid request.
    await core.reserve(engine, 'next', kid, 'model', 100, 100)
    await settle_usage(engine, 'next', failed=True)
