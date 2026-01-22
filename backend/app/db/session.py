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
from sqlalchemy import inspect, text

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
        await conn.run_sync(_run_migrations)


def _run_migrations(sync_conn) -> None:
    """
    Lightweight, in-place schema migrations for existing databases.

    This project doesn't ship Alembic migrations; `create_all()` won't add new columns
    for already-created tables, so we ensure additive columns exist.
    """
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())

    def ensure_columns(table: str, columns: dict[str, str]) -> None:
        if table not in table_names:
            return
        existing = {c["name"] for c in inspector.get_columns(table)}
        for col_name, ddl in columns.items():
            if col_name in existing:
                continue
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))

    ensure_columns(
        "model_mappings",
        {
            "model_type": "model_type VARCHAR(50)",
            "input_price": "input_price NUMERIC(12,4)",
            "output_price": "output_price NUMERIC(12,4)",
        },
    )
    ensure_columns(
        "model_mapping_providers",
        {
            "input_price": "input_price NUMERIC(12,4)",
            "output_price": "output_price NUMERIC(12,4)",
            "billing_mode": "billing_mode VARCHAR(50)",
            "per_request_price": "per_request_price NUMERIC(12,4)",
            "tiered_pricing": "tiered_pricing JSON",
        },
    )
    ensure_columns(
        "request_logs",
        {
            "total_cost": "total_cost NUMERIC(12,4)",
            "input_cost": "input_cost NUMERIC(12,4)",
            "output_cost": "output_cost NUMERIC(12,4)",
            "price_source": "price_source VARCHAR(50)",
            "request_protocol": "request_protocol VARCHAR(50)",
            "supplier_protocol": "supplier_protocol VARCHAR(50)",
            "converted_request_body": "converted_request_body JSON",
            "upstream_response_body": "upstream_response_body TEXT",
            "response_headers": "response_headers JSON",
        },
    )
    ensure_columns(
        "service_providers",
        {
            "proxy_enabled": "proxy_enabled BOOLEAN DEFAULT FALSE",
            "proxy_url": "proxy_url TEXT",
        },
    )
