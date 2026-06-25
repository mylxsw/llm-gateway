"""
Tests proving the streaming pool-exhaustion fix: ProxyService and
ProtocolConversionHooks acquire short-lived sessions per DB operation and
release the pooled connection immediately, rather than holding it for the
whole request/stream.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.common.time import utc_now
from app.db.models import Base
from app.domain.log import RequestLogCreate
from app.repositories.sqlalchemy import (
    SQLAlchemyKVStoreRepository,
    SQLAlchemyLogRepository,
    SQLAlchemyModelRepository,
    SQLAlchemyProviderRepository,
)
from app.services.protocol_hooks import ProtocolConversionHooks
from app.services.proxy_service import ProxyService


@pytest_asyncio.fixture
async def pooled_engine():
    """A real (file-backed) engine with an explicit small pool so we can assert
    on checked-out connections. In-memory SQLite uses a non-counting pool, so
    we use a temp file URL to get a QueuePool with observable counters."""
    import tempfile, os

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        pool_size=2,
        max_overflow=0,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    os.unlink(path)


@pytest.mark.asyncio
async def test_write_log_releases_connection(pooled_engine):
    """_write_log opens a short-lived session and returns the connection to the
    pool, so checkedout() is back to 0 afterwards."""
    session_factory = async_sessionmaker(pooled_engine, class_=AsyncSession, expire_on_commit=False)
    service = ProxyService(
        session_factory=session_factory,
        model_repo_factory=lambda s: SQLAlchemyModelRepository(s),
        provider_repo_factory=lambda s: SQLAlchemyProviderRepository(s),
        log_repo_factory=lambda s: SQLAlchemyLogRepository(s),
    )

    log_data = RequestLogCreate(
        request_time=utc_now(),
        api_key_id=1,
        api_key_name="k",
        requested_model="m",
        response_status=200,
        is_stream=True,
    )

    assert pooled_engine.pool.checkedout() == 0
    await service._write_log(log_data, record_details=True)
    # Connection released back to the pool immediately after the write.
    assert pooled_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_hooks_kv_releases_connection_per_chunk(pooled_engine):
    """In DB mode the hooks open a short-lived session per stream chunk and
    release the connection, so the pool is never pinned across a stream."""
    session_factory = async_sessionmaker(pooled_engine, class_=AsyncSession, expire_on_commit=False)
    hooks = ProtocolConversionHooks(
        kv_repo_factory=lambda s: SQLAlchemyKVStoreRepository(s),
        session_factory=session_factory,
    )

    chunk = (
        b'data: {"id":"chat-1","choices":[{"delta":{"tool_calls":'
        b'[{"id":"tc-1","extra_content":{"sig":"abc"}}]}}]}\n\n'
    )

    assert pooled_engine.pool.checkedout() == 0
    await hooks.before_stream_chunk_conversion(chunk, "openai", "openai")
    # No connection held between chunks.
    assert pooled_engine.pool.checkedout() == 0

    # And the value was actually persisted via the short-lived session.
    async with session_factory() as session:
        repo = SQLAlchemyKVStoreRepository(session)
        cached = await repo.get("tool_call_extra:tc-1")
    assert cached is not None
    assert "abc" in cached.value


@pytest.mark.asyncio
async def test_hooks_disabled_when_no_kv_configured():
    """With neither a repo nor a factory, KV caching is a no-op (no session,
    no error)."""
    hooks = ProtocolConversionHooks()
    assert hooks._kv_enabled is False
    chunk = b'data: {"id":"c","choices":[{"delta":{"tool_calls":[{"id":"t","extra_content":{"x":1}}]}}]}\n\n'
    # Should not raise.
    out = await hooks.before_stream_chunk_conversion(chunk, "openai", "openai")
    assert out == chunk
