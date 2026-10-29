"""
Test Configuration Module
"""

import pytest
import pytest_asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.models import Base


# Use in-memory database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_engine(monkeypatch):
    """Create async database engine for testing"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    from app.config import get_settings
    if get_settings().COMMERCIAL_ENABLED:
        from squirrel_commercial.core import migrate
        import app.db.session as database
        await migrate(engine)
        monkeypatch.setattr(database, 'engine', engine)

    yield engine
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing"""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session

@pytest_asyncio.fixture(autouse=True)
async def commercial_test_database(request, monkeypatch):
    """Mock-only proxy tests still need the optional Key lookup in enabled mode."""
    from app.config import get_settings
    if (not get_settings().COMMERCIAL_ENABLED
        or 'async_engine' in request.fixturenames or 'billing' in request.fixturenames):
        yield
        return
    import app.db.session as database
    from squirrel_commercial.core import migrate
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    await migrate(engine)
    monkeypatch.setattr(database, 'engine', engine)
    try:
        yield
    finally:
        await engine.dispose()
