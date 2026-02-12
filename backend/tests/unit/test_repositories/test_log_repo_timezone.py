"""
Test log repository timezone handling.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.domain.log import RequestLogCreate
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository, _pg_make_interval_minutes


@pytest.mark.asyncio
async def test_log_request_time_is_utc_aware(db_session):
    repo = SQLAlchemyLogRepository(db_session)

    created = await repo.create(
        RequestLogCreate(
            request_time=datetime.now(timezone.utc),
            api_key_id=1,
            api_key_name="test-key",
            requested_model="gpt-4",
            target_model="gpt-4",
            provider_id=1,
            provider_name="OpenAI",
            retry_count=0,
            matched_provider_count=1,
            response_status=200,
            trace_id="trace-utc",
            is_stream=False,
        )
    )

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.request_time.tzinfo == timezone.utc


def test_pg_make_interval_minutes_compiles():
    stmt = select(_pg_make_interval_minutes(480).label("iv"))
    compiled = stmt.compile(dialect=postgresql.dialect())
    compiled_sql = str(compiled)
    assert "make_interval" in compiled_sql
    assert len(compiled.params) == 6
