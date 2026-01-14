"""
Database Session Management Module

Provides asynchronous database session management, supporting SQLite and PostgreSQL.
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

# Get configuration
settings = get_settings()

# Create asynchronous database engine
# echo=True prints SQL statements in DEBUG mode
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # SQLite specific configuration
    connect_args={"check_same_thread": False} 
    if settings.DATABASE_TYPE == "sqlite" 
    else {},
)

# Create asynchronous session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Do not expire objects after commit, avoids extra queries
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session (for dependency injection)
    
    Uses async with to ensure session is closed correctly.
    Used as Depends in FastAPI.
    
    Yields:
        AsyncSession: Async database session
    
    Example:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize Database
    
    Creates all defined table structures. Called on application startup.
    
    Note:
        In production, using Alembic for database migration is recommended.
    """
    from app.db.models import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)