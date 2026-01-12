"""
Test Log Cleanup Functionality
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.domain.log import RequestLogCreate
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository
from app.services.log_service import LogService


@pytest.mark.asyncio
async def test_delete_older_than_days(db_session):
    """Test deleting logs older than specified days"""
    repo = SQLAlchemyLogRepository(db_session)

    # Create test data: 3 old logs (10 days ago) and 2 new logs (3 days ago)
    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    recent_time = datetime.now(timezone.utc) - timedelta(days=3)

    # Create old logs
    for i in range(3):
        await repo.create(
            RequestLogCreate(
                request_time=old_time,
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
                trace_id=f"old-trace-{i}",
                is_stream=False,
            )
        )

    # Create new logs
    for i in range(2):
        await repo.create(
            RequestLogCreate(
                request_time=recent_time,
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
                trace_id=f"recent-trace-{i}",
                is_stream=False,
            )
        )

    # Delete logs older than 7 days
    deleted_count = await repo.delete_older_than_days(7)

    # Verify 3 old logs deleted
    assert deleted_count == 3


@pytest.mark.asyncio
async def test_delete_older_than_days_no_matching_logs(db_session):
    """Test when no matching logs found"""
    repo = SQLAlchemyLogRepository(db_session)

    # Create a recent log
    recent_time = datetime.now(timezone.utc) - timedelta(days=2)
    await repo.create(
        RequestLogCreate(
            request_time=recent_time,
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
        )
    )

    # Delete logs older than 7 days (should be none)
    deleted_count = await repo.delete_older_than_days(7)

    # Verify no logs deleted
    assert deleted_count == 0


@pytest.mark.asyncio
async def test_cleanup_old_logs_service(db_session):
    """Test log cleanup in service layer"""
    repo = SQLAlchemyLogRepository(db_session)
    service = LogService(repo)

    # Create old log
    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    await repo.create(
        RequestLogCreate(
            request_time=old_time,
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
            trace_id="old-trace",
            is_stream=False,
        )
    )

    # Create new log
    recent_time = datetime.now(timezone.utc) - timedelta(days=3)
    await repo.create(
        RequestLogCreate(
            request_time=recent_time,
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
            trace_id="recent-trace",
            is_stream=False,
        )
    )

    # Cleanup logs older than 7 days
    deleted_count = await service.cleanup_old_logs(7)

    # Verify only old log deleted
    assert deleted_count == 1