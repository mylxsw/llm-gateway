"""Acceptance regressions: protocol termination, rejection/timeout evidence and Key APIs."""
import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.common.stream_usage import StreamUsageAccumulator
from app.common.time import utc_now
from app.domain.log import RequestLogCreate
from app.services import commercial
from squirrel_commercial import core
from squirrel_commercial.schema import keys, audit, accounts, months, requests, oauth_grants
from squirrel_commercial.estimator import estimate_input, estimate_input_async
from test_metering import commercial_gateway, make_stream, request_row, event
from test_v2 import oauth


@pytest.mark.parametrize('client',['openai','anthropic'])
async def test_responses_stream_settles_without_chat_done(commercial_gateway,monkeypatch,client):
    engine,kid=commercial_gateway
    (_,stream,info),_,logs,closed,_=await make_stream(monkeypatch,kid,upstream='openai_responses',client=client)
    chunks=[chunk async for chunk in stream]
    assert chunks and closed.is_set()
    row=await request_row(engine,info['trace_id'])
    assert row['status']=='settled' and row['charged_microcredits']==16
    assert row['input_tokens']==10 and row['output_tokens']==3
    assert logs.update.call_args.args[1].usage_details['final_usage']


def test_responses_text_and_terminal_usage_are_independent_of_chat_done():
    acc=StreamUsageAccumulator('openai_responses','model')
    acc.feed(event({'type':'response.output_text.delta','delta':'hello'}))
    assert acc.finalize().output_text=='hello' and not acc.finalize().final_usage
    acc.feed(event({'type':'response.completed','response':{'usage':{'input_tokens':10,'output_tokens':1}}}))
    assert acc.finalize().final_usage


@pytest.mark.parametrize('protocol',['openai','anthropic'])
async def test_provider_timeout_before_output_is_estimated_not_review(commercial_gateway,monkeypatch,protocol):
    engine,kid=commercial_gateway
    monkeypatch.setattr(get_settings(),'RETRY_MAX_ATTEMPTS',1)
    (_,stream,info),_,_,_,_=await make_stream(monkeypatch,kid,upstream=protocol,client=protocol,initial_status=504,initial_interrupted=True)
    await stream.aclose()
    row=await request_row(engine,info['trace_id'])
    assert row['status']=='settled' and row['charged_microcredits']==row['input_estimate']
    assert row['evidence_json']['interrupted'] and not row['evidence_json']['upstream_rejected']


@pytest.mark.parametrize('interrupted,output,reported,expected', [
    (False,False,False,'cancelled'),
    (True,False,False,'settled'),
    (False,True,False,'review'),
    (False,False,True,'review'),
])
async def test_nonstream_http_504_requires_transport_evidence(commercial_gateway,interrupted,output,reported,expected):
    engine,kid=commercial_gateway
    await core.reserve(engine,'504',kid,'model',100,10)
    await commercial.settle_log(RequestLogCreate(request_time=utc_now(),trace_id='504',commercial_user_id='alice',
        response_status=504,is_stream=False,input_tokens=7,output_tokens=1 if output else 0,
        usage_details={'source':'estimated','has_upstream_usage':reported,'has_output':output,'interrupted':interrupted}))
    row=await request_row(engine,'504')
    assert row['status']==expected
    if expected=='settled':
        assert row['charged_microcredits']==100


@pytest.mark.parametrize('limit',[None,0,100])
async def test_key_monthly_limit_creation_and_update(billing,limit):
    kid,_=await core.create_key(billing,'alice','limited',monthly_limit_microcredits=limit)
    async with billing.connect() as c:
        assert await c.scalar(select(keys.c.monthly_limit_microcredits).where(keys.c.api_key_id==kid))==limit
    await core.set_key_monthly_limit(billing,'alice',kid,50)
    await core.reserve(billing,'limit-request',kid,'model',10,10)
    await core.set_key_monthly_limit(billing,'alice',kid,0)
    with pytest.raises(core.BillingError,match='monthly_limit_exceeded'):
        await core.reserve(billing,'zero-request',kid,'model',1,1)
    await core.set_key_monthly_limit(billing,'alice',kid,None)
    await core.reserve(billing,'unlimited',kid,'model',100,100)
    async with billing.connect() as c:
        assert await c.scalar(select(func.sum(months.c.reserved_microcredits)))==330
        rows=(await c.execute(select(audit).where(audit.c.action=='set_key_monthly_limit'))).mappings().all()
        row=next(r for r in rows if r['after_json']=={'monthly_limit_microcredits':None})
        assert row['before_json']=={'monthly_limit_microcredits':0}
        assert row['after_json']=={'monthly_limit_microcredits':None}
        assert row['actor']=='alice'


@pytest.mark.parametrize('invalid',[-1,True,1.2,'10',2**63])
async def test_key_monthly_limit_validation_and_ownership(billing,invalid):
    with pytest.raises(core.BillingError):
        await core.create_key(billing,'alice','invalid',monthly_limit_microcredits=invalid)
    kid,_=await core.create_key(billing,'alice','owner')
    with pytest.raises(core.BillingError):
        await core.set_key_monthly_limit(billing,'alice',kid,invalid)
    with pytest.raises(core.BillingError,match='key_not_found'):
        await core.set_key_monthly_limit(billing,'bob',kid,100)
    await core.user_key_action(billing,'alice',kid,'revoke')
    with pytest.raises(core.BillingError,match='key_change_forbidden'):
        await core.set_key_monthly_limit(billing,'alice',kid,100)
    async with billing.connect() as c:
        assert await c.scalar(select(keys.c.revoked_at).where(keys.c.api_key_id==kid)) is not None


async def test_manual_limit_api_does_not_silently_change_oauth_limit(billing):
    kid=await oauth(billing)
    with pytest.raises(core.BillingError,match='oauth_grant_limit_required'):
        await core.set_key_monthly_limit(billing,'alice',kid,1)
    async with billing.connect() as c:
        assert await c.scalar(select(oauth_grants.c.monthly_limit_microcredits))==100


async def test_tokenizer_load_failure_falls_back_off_event_loop(monkeypatch):
    import tiktoken
    loop=asyncio.get_running_loop()
    entered=asyncio.Event()
    release=threading.Event()
    def offline(model):
        assert threading.current_thread() is not threading.main_thread()
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        raise OSError('offline')
    monkeypatch.setattr(tiktoken,'encoding_for_model',offline)
    body={'model':'gpt-4','messages':[{'content':'中文😀abc'}]}
    task=asyncio.create_task(estimate_input_async(body))
    try:
        await asyncio.wait_for(entered.wait(),timeout=2)
        # The event loop can run while tokenizer initialization is blocked.
        assert not task.done()
    finally:
        release.set()
    amount,version=await task
    assert version=='unicode-v1' and amount==66


async def test_deleted_model_is_not_for_sale_and_reservation_snapshot_survives(billing,monkeypatch):
    from app.repositories.sqlalchemy.model_repo import SQLAlchemyModelRepository
    monkeypatch.setattr(get_settings(),'COMMERCIAL_ENABLED',True)
    kid,_=await core.create_key(billing,'alice','deleted-model')
    await core.reserve(billing,'before-delete',kid,'model',10,10)
    async with async_sessionmaker(billing)() as session:
        await SQLAlchemyModelRepository(session).delete_mapping('model')
    with pytest.raises(core.BillingError,match='model_not_for_sale'):
        await core.reserve(billing,'after-delete',kid,'model',10,10)
    await core.settle(billing,'before-delete',core.UsageEvidence(10,1,source='upstream',terminal_complete=True))
    assert (await request_row(billing,'before-delete'))['charged_microcredits']==12


@pytest.mark.parametrize('module,classname',[
    ('openai_client','OpenAIClient'),('anthropic_client','AnthropicClient'),
    ('gemini_client','GeminiClient'),('jev_client','JevClient'),
])
@pytest.mark.parametrize('stream',[False,True])
@pytest.mark.parametrize('failure',['timeout','http504','partial_timeout'])
async def test_real_provider_marks_only_transport_timeouts(monkeypatch,module,classname,stream,failure):
    import importlib
    provider=getattr(importlib.import_module('app.providers.'+module),classname)()
    class PartialTimeout(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
            raise httpx.ReadTimeout('read timed out')
    def handle(request):
        if failure=='timeout':
            raise httpx.ReadTimeout('connection timed out',request=request)
        if failure=='partial_timeout':
            return httpx.Response(200,stream=PartialTimeout())
        return httpx.Response(504,json={'error':{'message':'upstream returned 504'}})
    client_type=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client_type(transport=httpx.MockTransport(handle),**kw))
    args=dict(base_url='https://example.com',api_key='test',path='/v1/chat/completions',
        method='POST',headers={},body={'messages':[{'role':'user','content':'hi'}]},target_model='model')
    if stream:
        responses=[response async for _,response in provider.forward_stream(**args)]
        response=responses[-1]
        if module=='jev_client':
            assert response.status_code==400 and not response.interrupted
            return
        if failure=='partial_timeout':
            assert len(responses)==2
    else:
        response=await provider.forward(**args)
    assert response.status_code==504 and response.interrupted==(failure!='http504')


@pytest.mark.parametrize('status,interrupted,body,expected',[
    (400,False,{'error':{'message':'context too long'}},'cancelled'),
    (429,False,{'error':{'message':'rate limited'}},'cancelled'),
    (500,False,'upstream failure','cancelled'),
    (504,False,{'error':{'message':'upstream HTTP timeout'}},'cancelled'),
    (504,True,None,'settled'),
    (502,False,{'choices':[{'message':{'content':'a'}}]},'review'),
])
async def test_real_nonstream_proxy_rejection_and_timeout_evidence(commercial_gateway,monkeypatch,status,interrupted,body,expected):
    from app.services.proxy_service import ProxyService
    from app.providers.base import ProviderResponse
    from app.domain.model import ModelMapping
    from app.rules.models import CandidateProvider
    engine,kid=commercial_gateway
    monkeypatch.setattr(get_settings(),'RETRY_MAX_ATTEMPTS',1)
    logs=AsyncMock()
    logs.create_initial.return_value=992
    logs.get_provider_mappings.return_value=[]
    service=ProxyService(logs,AsyncMock(),logs)
    mapping=ModelMapping(requested_model='model',strategy='priority',is_active=True,created_at=utc_now(),updated_at=utc_now())
    candidate=CandidateProvider(provider_id=1,provider_name='test',base_url='https://example.com',protocol='openai',api_key='test',target_model='model',priority=1)
    service._resolve_candidates=AsyncMock(return_value=(mapping,[candidate],8,'openai',{}))
    provider=AsyncMock()
    provider.forward.return_value=ProviderResponse(status_code=status,body=body,interrupted=interrupted)
    monkeypatch.setattr('app.services.proxy_service.get_provider_client',lambda _:provider)
    _,info=await service.process_request(api_key_id=kid,api_key_name='test',request_protocol='openai',
        path='/v1/chat/completions',request_url=None,method='POST',headers={},
        body={'model':'model','max_tokens':100,'messages':[{'role':'user','content':'hi'}]},force_parse_response=True)
    row=await request_row(engine,info['trace_id'])
    assert row['status']==expected
    if expected=='settled':
        assert row['charged_microcredits']==row['input_estimate']
    if expected=='cancelled':
        assert row['charged_microcredits']==0
        async with engine.connect() as c:
            assert await c.scalar(select(accounts.c.reserved_microcredits).where(accounts.c.id=='alice'))==0


async def test_limit_update_and_reservation_share_account_lock(billing):
    kid,_=await core.create_key(billing,'alice','concurrent-limit',monthly_limit_microcredits=100)
    async def reserve():
        try:
            await core.reserve(billing,'race-limit',kid,'model',10,10)
            return True
        except core.BillingError as exc:
            assert exc.code=='monthly_limit_exceeded'
            return False
    reserved,_=await asyncio.gather(reserve(),core.set_key_monthly_limit(billing,'alice',kid,0))
    async with billing.connect() as c:
        assert await c.scalar(select(keys.c.monthly_limit_microcredits).where(keys.c.api_key_id==kid))==0
        assert await c.scalar(select(accounts.c.reserved_microcredits).where(accounts.c.id=='alice'))==(30 if reserved else 0)


@pytest.mark.parametrize('module,classname',[
    ('openai_client','OpenAIClient'),('anthropic_client','AnthropicClient'),
    ('gemini_client','GeminiClient'),('jev_client','JevClient'),
])
async def test_model_listing_transport_timeout_keeps_explicit_evidence(monkeypatch,module,classname):
    import importlib
    provider=getattr(importlib.import_module('app.providers.'+module),classname)()
    def handle(request):
        raise httpx.ReadTimeout('timeout',request=request)
    client_type=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client_type(transport=httpx.MockTransport(handle),**kw))
    response=await provider.list_models(base_url='https://example.com',api_key='test')
    assert response.status_code==504 and response.interrupted


@pytest.mark.parametrize('body',[{'choices':1},{'output':2},{'choices':[None,1]},{'content':None},'invalid JSON'])
def test_malformed_error_payload_is_not_output(body):
    assert not commercial.response_has_output(body)


@pytest.mark.parametrize('usage',[None,[],1,{'input_tokens':True,'output_tokens':1},{'input_tokens':1},{'input_tokens':1,'output_tokens':-1}])
def test_malformed_responses_terminal_usage_remains_untrusted(usage):
    acc=StreamUsageAccumulator('openai_responses','model')
    acc.feed(event([]))
    acc.feed(event({'type':'response.completed','response':{'usage':usage}}))
    assert not acc.finalize().final_usage
