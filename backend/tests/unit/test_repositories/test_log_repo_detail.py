"""
Test log detail table separation (request_log_details).
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy import select, text

from app.db.models import RequestLog as RequestLogORM
from app.db.models import RequestLogDetail as RequestLogDetailORM
from app.domain.log import RequestLogCreate, RequestLogQuery
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository


def _make_log_data(**overrides) -> RequestLogCreate:
    """Helper to create a RequestLogCreate with sensible defaults."""
    defaults = dict(
        request_time=datetime.now(timezone.utc),
        api_key_id=1,
        api_key_name="test-key",
        requested_model="gpt-4",
        target_model="gpt-4",
        provider_id=1,
        provider_name="OpenAI",
        retry_count=0,
        matched_provider_count=1,
        first_byte_delay_ms=100,
        total_time_ms=500,
        input_tokens=10,
        output_tokens=20,
        response_status=200,
        trace_id="trace-1",
        is_stream=False,
        request_body={"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}]},
        response_body='{"choices":[{"message":{"content":"hi"}}]}',
        request_headers={"authorization": "Bearer ***"},
        response_headers={"content-type": "application/json"},
        error_info=None,
        usage_details={"prompt_tokens": 10, "completion_tokens": 20},
        converted_request_body={"model": "gpt-4-turbo"},
        upstream_response_body='{"id":"resp-1"}',
    )
    defaults.update(overrides)
    return RequestLogCreate(**defaults)


@pytest.mark.asyncio
async def test_create_stores_detail_separately(db_session):
    """Verify create() writes large fields to request_log_details and NULLs on main table."""
    repo = SQLAlchemyLogRepository(db_session)

    log = await repo.create(_make_log_data())

    # Check main table: large fields should be NULL
    result = await db_session.execute(
        select(RequestLogORM).where(RequestLogORM.id == log.id)
    )
    entity = result.scalar_one()
    assert entity.request_body is None
    assert entity.response_body is None
    assert entity.request_headers is None
    assert entity.response_headers is None
    assert entity.converted_request_body is None
    assert entity.upstream_response_body is None
    assert entity.usage_details is None
    assert entity.error_info is None

    # Check detail table: large fields should be present
    detail_result = await db_session.execute(
        select(RequestLogDetailORM).where(RequestLogDetailORM.log_id == log.id)
    )
    detail = detail_result.scalar_one()
    assert detail.request_body == {"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}]}
    assert detail.response_body == '{"choices":[{"message":{"content":"hi"}}]}'
    assert detail.request_headers == {"authorization": "Bearer ***"}
    assert detail.response_headers == {"content-type": "application/json"}
    assert detail.usage_details == {"prompt_tokens": 10, "completion_tokens": 20}
    assert detail.converted_request_body == {"model": "gpt-4-turbo"}
    assert detail.upstream_response_body == '{"id":"resp-1"}'


@pytest.mark.asyncio
async def test_create_returns_full_model_with_detail(db_session):
    """Verify create() return value includes large fields from detail data."""
    repo = SQLAlchemyLogRepository(db_session)

    created = await repo.create(_make_log_data(
        request_body={"messages": [{"role": "user", "content": "hello"}]},
        response_body='{"result":"ok"}',
        error_info="some error",
    ))

    # The create() return value should include the detail fields
    assert created.request_body == {"messages": [{"role": "user", "content": "hello"}]}
    assert created.response_body == '{"result":"ok"}'
    assert created.error_info == "some error"
    assert created.request_headers == {"authorization": "Bearer ***"}


@pytest.mark.asyncio
async def test_get_by_id_returns_full_detail(db_session):
    """Verify get_by_id() joins detail and returns complete data."""
    repo = SQLAlchemyLogRepository(db_session)

    created = await repo.create(_make_log_data(
        request_body={"messages": [{"role": "user", "content": "test"}]},
        response_body='{"result":"ok"}',
        error_info="some error",
    ))

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.request_body == {"messages": [{"role": "user", "content": "test"}]}
    assert fetched.response_body == '{"result":"ok"}'
    assert fetched.error_info == "some error"


@pytest.mark.asyncio
async def test_query_returns_summary_only(db_session):
    """Verify query() returns only summary columns without large fields."""
    repo = SQLAlchemyLogRepository(db_session)

    await repo.create(_make_log_data())

    items, total = await repo.query(RequestLogQuery(page=1, page_size=20))
    assert total == 1
    assert len(items) == 1

    item = items[0]
    # Summary fields should be present
    assert item.id is not None
    assert item.requested_model == "gpt-4"
    assert item.response_status == 200
    assert item.input_tokens == 10
    assert item.output_tokens == 20

    # Summary model should NOT have large field attributes
    assert not hasattr(item, "request_body")
    assert not hasattr(item, "response_body")
    assert not hasattr(item, "request_headers")


@pytest.mark.asyncio
async def test_cleanup_deletes_both_tables(db_session):
    """Verify cleanup removes from both request_logs and request_log_details."""
    from datetime import timedelta

    repo = SQLAlchemyLogRepository(db_session)

    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    recent_time = datetime.now(timezone.utc) - timedelta(days=3)

    # Create old log
    old_log = await repo.create(_make_log_data(
        request_time=old_time, trace_id="old-trace"
    ))
    # Create recent log
    recent_log = await repo.create(_make_log_data(
        request_time=recent_time, trace_id="recent-trace"
    ))

    # Cleanup logs older than 7 days
    deleted_count = await repo.cleanup_old_logs(7)
    assert deleted_count == 1

    # Verify old detail record is also deleted
    detail_result = await db_session.execute(
        select(RequestLogDetailORM).where(RequestLogDetailORM.log_id == old_log.id)
    )
    assert detail_result.scalar_one_or_none() is None

    # Verify recent detail record still exists
    detail_result2 = await db_session.execute(
        select(RequestLogDetailORM).where(RequestLogDetailORM.log_id == recent_log.id)
    )
    assert detail_result2.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_get_by_id_fallback_for_unmigrated_records(db_session):
    """Verify get_by_id works for records with data in main table but no detail row."""
    repo = SQLAlchemyLogRepository(db_session)

    # Manually insert a record with body data in request_logs but no detail row
    # (simulates pre-migration data)
    from app.common.time import to_utc_naive
    entity = RequestLogORM(
        request_time=to_utc_naive(datetime.now(timezone.utc)),
        api_key_id=1,
        api_key_name="test-key",
        requested_model="gpt-4",
        target_model="gpt-4",
        provider_id=1,
        provider_name="OpenAI",
        retry_count=0,
        response_status=200,
        trace_id="unmigrated-trace",
        is_stream=False,
        # Old-style: large fields on main table
        request_body={"model": "gpt-4", "messages": []},
        response_body='{"old":"data"}',
        error_info="old error",
    )
    db_session.add(entity)
    await db_session.commit()
    await db_session.refresh(entity)

    # get_by_id should still return the body data from the main table
    fetched = await repo.get_by_id(entity.id)
    assert fetched is not None
    assert fetched.request_body == {"model": "gpt-4", "messages": []}
    assert fetched.response_body == '{"old":"data"}'
    assert fetched.error_info == "old error"
