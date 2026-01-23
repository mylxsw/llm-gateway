
import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.common.time import utc_now
from app.db.models import Base
from app.domain.log import RequestLogCreate
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository

# Setup in-memory SQLite
@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    
    await engine.dispose()

@pytest.mark.asyncio
async def test_create_log_with_protocol_fields(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    
    log_data = RequestLogCreate(
        request_time=utc_now(),
        request_protocol="openai",
        supplier_protocol="anthropic",
        converted_request_body={"model": "claude-3"},
        upstream_response_body='{"id": "msg_123"}',
        usage_details={"input_tokens": 10, "output_tokens": 5, "source": "upstream"},
        # Required fields (mostly optional in Create but good to be explicit)
        retry_count=0
    )
    
    # Test Create
    created_log = await repo.create(log_data)
    
    assert created_log.request_protocol == "openai"
    assert created_log.supplier_protocol == "anthropic"
    assert created_log.converted_request_body == {"model": "claude-3"}
    assert created_log.upstream_response_body == '{"id": "msg_123"}'
    
    # Test Retrieval
    retrieved_log = await repo.get_by_id(created_log.id)
    assert retrieved_log is not None
    assert retrieved_log.request_protocol == "openai"
    assert retrieved_log.supplier_protocol == "anthropic"
    assert retrieved_log.converted_request_body == {"model": "claude-3"}
    assert retrieved_log.upstream_response_body == '{"id": "msg_123"}'
    assert retrieved_log.usage_details == {"input_tokens": 10, "output_tokens": 5, "source": "upstream"}
