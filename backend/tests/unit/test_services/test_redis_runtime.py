"""Exercise Redis-only proxy wiring and durable database retries."""
import asyncio
import json
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.common.errors import AppError, AuthenticationError
from app.common.time import utc_now
from app.domain.api_key import ApiKeyCreate
from app.domain.log import RequestLogCreate
from app.domain.model import ModelMappingCreate, ModelMappingProviderCreate
from app.domain.provider import ProviderCreate
from app.repositories.sqlalchemy import SQLAlchemyApiKeyRepository, SQLAlchemyModelRepository, SQLAlchemyProviderRepository
from app.services.api_key_service import ApiKeyService
from app.services.redis_runtime import GROUP, JOURNAL, SNAPSHOT, RedisRuntime, RuntimeApiKeys, RuntimeLogs, RuntimeRoutes


@pytest.fixture
async def runtime(async_engine):
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    sessions = async_sessionmaker(async_engine, expire_on_commit=False)
    worker = RedisRuntime(client, sessions)
    async with sessions() as session:
        await SQLAlchemyApiKeyRepository(session).create(ApiKeyCreate(key_name="typeflux"), "test-secret")
        provider = await SQLAlchemyProviderRepository(session).create(ProviderCreate(name="DeepSeek", base_url="https://api.deepseek.com", protocol="deepseek", api_key="provider-secret"))
        models = SQLAlchemyModelRepository(session)
        await models.create_mapping(ModelMappingCreate(requested_model="deepseek-flash"))
        await models.add_provider_mapping(ModelMappingProviderCreate(requested_model="deepseek-flash", provider_id=provider.id, target_model_name="deepseek-flash", input_price=0.3, output_price=1.2))
    await worker.refresh()
    await client.xgroup_create(JOURNAL, GROUP, id="0", mkstream=True)
    yield worker
    await worker.stop()
    await client.aclose()


async def test_auth_routing_and_missing_cache_never_open_sql(runtime):
    original = runtime.session_factory
    runtime.session_factory = lambda: (_ for _ in ()).throw(AssertionError("SQL in foreground"))
    client = runtime.client
    key = await ApiKeyService(RuntimeApiKeys(client)).authenticate("Bearer test-secret")
    assert key.key_name == "typeflux"
    with pytest.raises(AuthenticationError):
        await ApiKeyService(RuntimeApiKeys(client)).authenticate("wrong")
    routes = RuntimeRoutes(client)
    assert (await routes.get_mapping("deepseek-flash")).is_active
    mappings = await routes.get_provider_mappings("deepseek-flash", True)
    assert (await routes.get_by_id(mappings[0].provider_id)).api_key == "provider-secret"
    assert await routes.get_mapping("missing") is None
    # A request keeps the coherent revision even if the published key expires.
    await client.delete(SNAPSHOT)
    assert await routes.get_mapping("deepseek-flash")
    with pytest.raises(AppError) as exc:
        await RuntimeRoutes(client).get_mapping("deepseek-flash")
    assert exc.value.status_code == 503
    runtime.session_factory = original
    await runtime.refresh()
    data = json.loads(await client.get(SNAPSHOT))
    for key_data in data["keys"].values():
        key_data["is_active"] = False
    await client.set(SNAPSHOT, json.dumps(data))
    with pytest.raises(AuthenticationError):
        await ApiKeyService(RuntimeApiKeys(client)).authenticate("test-secret")


async def test_journal_retry_restart_and_duplicate_delivery(runtime):
    from app.db.models import RequestLog
    logs = RuntimeLogs(runtime.client)
    initial = RequestLogCreate(request_time=utc_now(), trace_id="test-trace", is_completed=False)
    handle = await logs.create_initial(initial)
    complete = initial.model_copy(update={"is_completed": True, "response_status": 200, "input_tokens": 5, "output_tokens": 2})
    await logs.update(handle, complete)
    original = runtime.session_factory
    runtime.session_factory = lambda: (_ for _ in ()).throw(RuntimeError("database unavailable"))
    with pytest.raises(RuntimeError):
        await runtime.drain_once()
    assert await runtime.client.xlen(JOURNAL) == 2
    # Another worker resumes the pending item and then its completion in order.
    replacement = RedisRuntime(runtime.client, original)
    assert await replacement.drain_once()
    assert await replacement.drain_once()
    assert await runtime.client.xlen(JOURNAL) == 0
    await logs.update(handle, complete)
    await logs.create_initial(initial)
    assert await replacement.drain_once()
    assert await replacement.drain_once()
    async with original() as session:
        assert await session.scalar(select(func.count()).select_from(RequestLog)) == 1
        result = await session.scalar(select(RequestLog))
        assert result.is_completed and result.input_tokens == 5 and result.output_tokens == 2


async def test_runtime_dependencies_use_redis_repositories(runtime, monkeypatch):
    from app.api import deps
    from app.db import redis as redis_db
    settings = deps.get_settings().model_copy(update={"PROXY_REDIS_RUNTIME": True})
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr(redis_db, "get_redis", lambda: runtime.client)
    monkeypatch.setattr(deps, "AsyncSessionLocal", lambda: (_ for _ in ()).throw(AssertionError("SQL dependency")))
    service = deps.get_proxy_service()
    assert service._session_factory is None
    key = await deps.get_current_api_key(None, "Bearer test-secret", None)
    assert key.key_name == "typeflux"
    mapping, candidates, _, _, _ = await service._resolve_candidates("deepseek-flash", "openai", {}, {"messages":[]})
    assert mapping.requested_model == "deepseek-flash" and candidates
    # Stream reasoning-cache writes also stay in the existing Redis backend.
    hooks = service._protocol_hooks
    from app.repositories.redis import RedisKVStoreRepository
    assert isinstance(hooks._kv_repo, RedisKVStoreRepository)


async def test_live_task_alias_is_cleaned_after_finish():
    from app.services.active_requests import ActiveRequestTracker
    tracker = ActiveRequestTracker()
    task = asyncio.current_task()
    await tracker.register(-1, task)
    await tracker.bind_alias(123, -1)
    assert await tracker.is_active(123)
    await tracker.deregister(-1)
    assert not await tracker.is_active(123)


async def test_failed_attempt_does_not_replace_final_success(runtime):
    from datetime import timedelta
    from app.db.models import RequestLog
    logs = RuntimeLogs(runtime.client)
    initial = RequestLogCreate(request_time=utc_now(), trace_id="retry-trace", is_completed=False)
    handle = await logs.create_initial(initial)
    attempt = initial.model_copy(update={"request_time": initial.request_time + timedelta(microseconds=1), "is_completed": True, "retry_count":1, "response_status":503})
    await logs.create(attempt)
    await logs.update(handle, initial.model_copy(update={"is_completed":True, "retry_count":1, "response_status":200}))
    for _ in range(3):
        assert await runtime.drain_once()
    async with runtime.session_factory() as session:
        results = list((await session.scalars(select(RequestLog).order_by(RequestLog.id))).all())
        assert [x.response_status for x in results] == [200, 503]


@pytest.mark.parametrize("stream", [False, True])
async def test_full_proxy_request_and_reasoning_cache_without_sql(runtime, monkeypatch, async_engine, stream):
    from sqlalchemy import event
    from app.api import deps
    from app.db import redis as redis_db
    from app.providers.base import ProviderResponse
    settings = deps.get_settings().model_copy(update={"PROXY_REDIS_RUNTIME": True})
    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr(redis_db, "get_redis", lambda: runtime.client)
    service = deps.get_proxy_service()
    captured = []
    response = ProviderResponse(status_code=200, body={"id":"chat-test", "choices":[{"message":{"role":"assistant","content":"整理完成"},"finish_reason":"stop"}], "usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}})
    async def forward(**kwargs):
        captured.append(kwargs["body"])
        return response
    async def forward_stream(**kwargs):
        captured.append(kwargs["body"])
        for delta in ({"reasoning_content":"synthetic reasoning cache test"},{"content":"整理完成"}):
            yield ("data: " + json.dumps({"id":"chat-test", "choices":[{"index":0,"delta":delta}]}, ensure_ascii=False)+"\n\n").encode(), response
        yield b'data: {"id":"chat-test","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}\n\n', response
        yield b"data: [DONE]\n\n", response
    provider = AsyncMock()
    provider.forward = forward
    provider.forward_stream = forward_stream
    monkeypatch.setattr("app.services.proxy_service.get_provider_client", lambda *_: provider)
    def deny_sql(*_):
        raise AssertionError("Foreground SQL access")
    event.listen(async_engine.sync_engine, "before_cursor_execute", deny_sql)
    try:
        key = await deps.get_current_api_key(None, "Bearer test-secret", None)
        kwargs = dict(api_key_id=key.id, api_key_name=key.key_name, request_protocol="openai", path="/v1/chat/completions", request_url="/v1/chat/completions", method="POST", headers={}, body={"model":"deepseek-flash","messages":[{"role":"user","content":"test"}],"reasoning":{"effort":"none"},"stream":stream})
        if stream:
            result, output, _ = await service.process_request_stream(**kwargs)
            content = b"".join([part async for part in output])
            assert "整理完成" in content.decode()
            assert await runtime.client.get("chat_reasoning:chat-test")
        else:
            result, _ = await service.process_request(**kwargs)
        assert result.status_code == 200
        assert captured[0]["thinking"] == {"type":"disabled"}
    finally:
        event.remove(async_engine.sync_engine, "before_cursor_execute", deny_sql)
    while await runtime.drain_once():
        pass


async def test_http_boundary_denies_sql_until_stream_finishes(async_engine):
    from sqlalchemy import text
    from app.services.redis_runtime import RuntimeBoundaryMiddleware, install_sql_boundary
    install_sql_boundary(async_engine)
    async def request(scope, receive, send):
        async with async_engine.connect() as connection:
            await connection.execute(text("select 1"))
    app = RuntimeBoundaryMiddleware(request)
    with pytest.raises(RuntimeError, match="local Redis"):
        await app({"type":"http", "method":"POST", "path":"/v1/chat/completions"}, None, None)
    # Background tasks and admin reads remain outside the HTTP runtime boundary.
    await app({"type":"http", "method":"GET", "path":"/api/logs"}, None, None)


async def test_runtime_snapshot_reads_do_not_perform_blocking_dns(runtime, monkeypatch):
    def reject_dns(*_):
        raise AssertionError("Blocking DNS validation on the event loop")
    monkeypatch.setattr("app.common.url_validator.socket.gethostbyname", reject_dns)
    # Projection reads trusted persisted configuration; admin write validation remains intact.
    await runtime.refresh()
    routes = RuntimeRoutes(runtime.client)
    mapping = (await routes.get_provider_mappings("deepseek-flash"))[0]
    provider = await routes.get_by_id(mapping.provider_id)
    assert provider.base_url == "https://api.deepseek.com"
    assert provider.created_at.tzinfo is not None
    from app.domain.provider import ProviderCreate
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="Blocking DNS"):
        ProviderCreate(name="New provider", base_url="https://api.deepseek.com", protocol="deepseek")
