"""Redis-only proxy reads with database persistence in a background worker."""
import asyncio
import contextlib
from contextvars import ContextVar
import hashlib
import json
import logging
import uuid

from app.common.errors import AppError
from app.domain.api_key import ApiKeyModel
from app.domain.log import RequestLogCreate
from app.domain.model import ModelMapping, ModelMappingProviderResponse
from app.domain.provider import Provider

logger = logging.getLogger(__name__)
PREFIX = "squirrel:runtime:v1"
SNAPSHOT = PREFIX + ":snapshot"
JOURNAL = PREFIX + ":journal"
GROUP = "database"
_runtime_request = ContextVar("proxy_redis_runtime_request", default=False)


class RuntimeBoundaryMiddleware:
    """Reject any accidental SQL fallback inside proxy POST/stream handling."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/v1/") or scope.get("method") == "GET":
            return await self.app(scope, receive, send)
        token = _runtime_request.set(True)
        try:
            await self.app(scope, receive, send)
        finally:
            _runtime_request.reset(token)


def install_sql_boundary(engine):
    from sqlalchemy import event
    if not event.contains(engine.sync_engine, "before_cursor_execute", reject_runtime_sql):
        event.listen(engine.sync_engine, "before_cursor_execute", reject_runtime_sql)


def reject_runtime_sql(*_):
    if _runtime_request.get():
        raise RuntimeError("Proxy requests must use local Redis; SQL belongs in background workers")


def key_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


async def load_snapshot(client):
    raw = await client.get(SNAPSHOT)
    try:
        data = json.loads(raw) if raw else None
        if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in ("keys", "models", "providers", "mappings")):
            raise ValueError("Invalid snapshot")
        return data
    except (ValueError, TypeError):
        raise AppError("Proxy configuration is refreshing; retry shortly", code="runtime_not_ready", status_code=503) from None


async def enqueue(client, kind, data):
    await client.xadd(JOURNAL, {"kind": kind, "data": json.dumps(data)})


class RuntimeApiKeys:
    def __init__(self, client):
        self.client = client

    async def get_by_key_value(self, value):
        data = (await load_snapshot(self.client))["keys"].get(key_hash(value))
        return ApiKeyModel.model_validate(data) if data else None

    async def update_last_used(self, id, last_used_at):
        await enqueue(self.client, "last_used", {"id": id, "at": last_used_at.isoformat()})


class RuntimeRoutes:
    """Pin one complete Redis revision for all routing reads in a request."""
    def __init__(self, client):
        self.client = client
        self.snapshot = None

    async def _load(self):
        if self.snapshot is None:
            self.snapshot = await load_snapshot(self.client)
        return self.snapshot

    async def get_mapping(self, requested_model):
        data = (await self._load())["models"].get(requested_model)
        return ModelMapping.model_validate(data) if data else None

    async def get_provider_mappings(self, requested_model, is_active=None):
        rows = (await self._load())["mappings"].get(requested_model, [])
        return [ModelMappingProviderResponse.model_validate(row) for row in rows
                if is_active is None or row["is_active"] == is_active]

    async def get_by_id(self, id):
        data = (await self._load())["providers"].get(str(id))
        if data is None:
            return None
        from datetime import datetime
        # This document comes from validated persisted admin configuration.
        # Re-validating a URL here performs blocking DNS on the event loop.
        data = dict(data)
        for field in ("created_at", "updated_at"):
            if isinstance(data.get(field), str):
                data[field] = datetime.fromisoformat(data[field])
        return Provider.model_construct(**data)


class RuntimeLogs:
    def __init__(self, client):
        self.client = client

    async def create_initial(self, data):
        # Internal handle only; database IDs are allocated by the worker.
        handle = -(uuid.uuid4().int % (2**63 - 1) + 1)
        payload = data.model_dump(mode="json")
        payload["runtime_handle"] = handle
        await enqueue(self.client, "initial", payload)
        return handle

    async def create(self, data):
        await enqueue(self.client, "attempt", data.model_dump(mode="json"))

    async def update(self, log_id, data):
        await enqueue(self.client, "complete", data.model_dump(mode="json"))


class RedisRuntime:
    def __init__(self, client, session_factory):
        self.client = client
        self.session_factory = session_factory
        self.tasks = []
        self.consumer = str(uuid.uuid4())

    async def refresh(self):
        from app.repositories.sqlalchemy import SQLAlchemyApiKeyRepository, SQLAlchemyModelRepository, SQLAlchemyProviderRepository
        async with self.session_factory() as session:
            async def all_pages(method):
                rows, page = [], 1
                while True:
                    values, total = await method(page=page, page_size=500)
                    rows.extend(values)
                    if len(rows) >= total:
                        return rows
                    page += 1
            keys = await all_pages(SQLAlchemyApiKeyRepository(session).get_all)
            model_repo = SQLAlchemyModelRepository(session)
            models = await all_pages(model_repo.get_all_mappings)
            mappings = await model_repo.get_all_provider_mappings()
            providers = await all_pages(SQLAlchemyProviderRepository(session, validate_reads=False).get_all)
            document = {
                "keys": {key_hash(x.key_value): x.model_dump(mode="json") for x in keys},
                "models": {x.requested_model: x.model_dump(mode="json") for x in models},
                "providers": {str(x.id): x.model_dump(mode="json") for x in providers},
                "mappings": {},
            }
            for row in mappings:
                document["mappings"].setdefault(row.requested_model, []).append(row.model_dump(mode="json"))
        # One atomic revision; expiration bounds stale-key authorization on outage.
        await self.client.set(SNAPSHOT, json.dumps(document), ex=60)

    async def persist(self, fields):
        from datetime import datetime
        from app.repositories.sqlalchemy import SQLAlchemyApiKeyRepository, SQLAlchemyLogRepository
        data = json.loads(fields["data"])
        async with self.session_factory() as session:
            if fields["kind"] == "last_used":
                await SQLAlchemyApiKeyRepository(session).update_last_used(data["id"], datetime.fromisoformat(data["at"]))
                return
            log = RequestLogCreate.model_validate(data)
            if not log.trace_id:
                raise ValueError("Runtime journal requires a trace ID")
            repo = SQLAlchemyLogRepository(session)
            # Failed attempts share a trace ID with the main request but have
            # their own start time. Never overwrite the main receipt with one.
            from sqlalchemy import select
            from app.common.time import to_utc_naive
            from app.db.models import RequestLog as RequestLogORM
            row_id = await session.scalar(select(RequestLogORM.id).where(
                RequestLogORM.trace_id == log.trace_id,
                RequestLogORM.request_time == to_utc_naive(log.request_time),
            ).order_by(RequestLogORM.id).limit(1))
            existing = await repo.get_by_id(row_id) if row_id is not None else None
            if existing is None:
                existing = await repo.create(log)
            elif fields["kind"] == "complete" and not existing.is_completed:
                existing = await repo.update(existing.id, log)
            if "runtime_handle" in data:
                from app.services.active_requests import active_requests
                await active_requests.bind_alias(existing.id, data["runtime_handle"])

    async def drain_once(self):
        # One writer, including overlapping instances during a rolling restart.
        lock = PREFIX + ":writer"
        if not await self.client.set(lock, self.consumer, nx=True, ex=30):
            return False
        try:
            pending = await self.client.xautoclaim(JOURNAL, GROUP, self.consumer, min_idle_time=0, start_id="0-0", count=1)
            entries = pending[1]
            if not entries:
                rows = await self.client.xreadgroup(GROUP, self.consumer, {JOURNAL: ">"}, count=1)
                entries = rows[0][1] if rows else []
            for event_id, fields in entries:
                # Persistence cannot outlive the writer lease.
                async with asyncio.timeout(10):
                    await self.persist(fields)
                async with self.client.pipeline(transaction=True) as pipe:
                    pipe.xack(JOURNAL, GROUP, event_id)
                    pipe.xdel(JOURNAL, event_id)
                    await pipe.execute()
            return bool(entries)
        finally:
            await self.client.eval("if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) end return 0", 1, lock, self.consumer)

    async def _refresh_loop(self):
        while True:
            await asyncio.sleep(2)
            try:
                async with asyncio.timeout(10):
                    await self.refresh()
            except Exception:
                logger.exception("Redis runtime configuration refresh failed")

    async def _journal_loop(self):
        while True:
            try:
                if not await self.drain_once():
                    await asyncio.sleep(0.2)
            except Exception:
                logger.exception("Redis runtime journal retained for retry")
                await asyncio.sleep(1)

    async def start(self):
        from redis.exceptions import ResponseError
        try:
            await self.client.xgroup_create(JOURNAL, GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
        async with asyncio.timeout(15):
            await self.refresh()
        self.tasks = [asyncio.create_task(self._refresh_loop()), asyncio.create_task(self._journal_loop())]

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
