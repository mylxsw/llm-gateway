"""Regression tests for two-phase request log persistence."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.common.errors import NotFoundError
from app.common.time import utc_now
from app.domain.log import LogCostStatsQuery, RequestLogCreate
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository


def _log_data(**overrides) -> RequestLogCreate:
    values = {
        "request_time": datetime.now(timezone.utc),
        "requested_model": "test-model",
        "target_model": "target-model",
        "provider_id": 1,
        "provider_name": "provider",
        "response_status": 200,
        "request_body": {"model": "test-model"},
        "response_body": '{"ok":true}',
        "error_info": None,
    }
    values.update(overrides)
    return RequestLogCreate(**values)


@pytest.mark.asyncio
async def test_cancel_wins_over_late_completion(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    log_id = await repo.create_initial(_log_data(is_completed=False))

    await repo.cancel(log_id)
    await repo.update(log_id, _log_data(response_status=200, error_info=None))

    log = await repo.get_by_id(log_id)
    assert log is not None
    assert log.is_completed is True
    assert log.response_status == 499
    assert log.error_info == "Request cancelled by admin"
    assert log.response_body is None


@pytest.mark.asyncio
async def test_cancel_completed_log_does_not_mutate_details(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    completed = await repo.create(_log_data(error_info="original error"))

    with pytest.raises(NotFoundError):
        await repo.cancel(completed.id)

    log = await repo.get_by_id(completed.id)
    assert log is not None
    assert log.response_status == 200
    assert log.error_info == "original error"
    assert log.response_body == '{"ok":true}'


@pytest.mark.asyncio
async def test_cost_stats_exclude_in_progress_logs(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    await repo.create(_log_data(total_cost=1, input_tokens=10, output_tokens=20))
    await repo.create_initial(
        _log_data(
            requested_model="still-running",
            is_completed=False,
            response_status=None,
        )
    )

    stats = await repo.get_cost_stats(
        LogCostStatsQuery(start_time=datetime(2000, 1, 1, tzinfo=timezone.utc))
    )

    assert stats.summary.request_count == 1
    assert len(stats.trend) == 1
    assert stats.trend[0].request_count == 1
    assert stats.trend[0].success_count == 1
    assert [item.requested_model for item in stats.by_model] == ["test-model"]


async def test_expiry_only_closes_overdue_requests_and_accepts_late_results(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    now = utc_now()
    overdue_id = await repo.create_initial(_log_data(completion_deadline=now - timedelta(minutes=1)))
    active_id = await repo.create_initial(_log_data(completion_deadline=now + timedelta(minutes=1)))
    legacy_id = await repo.create_initial(_log_data(request_time=now - timedelta(days=1)))

    assert await repo.expire_overdue(now) == 1
    assert await repo.expire_overdue(now) == 0
    overdue = await repo.get_by_id(overdue_id)
    assert overdue.is_completed is True
    assert overdue.response_status is None
    assert "did not record" in overdue.error_info
    assert (await repo.get_by_id(active_id)).is_completed is False
    assert (await repo.get_by_id(legacy_id)).is_completed is False

    completed = await repo.update(overdue_id, _log_data(response_status=400, error_info="Upstream error"))
    assert completed.is_completed is True
    assert completed.response_status == 400
    assert completed.error_info == "Upstream error"


async def test_completion_survives_detail_insert_failure(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    log_id = await repo.create_initial(_log_data())
    await db_session.execute(text("""
        CREATE TRIGGER reject_log_details BEFORE INSERT ON request_log_details
        BEGIN SELECT RAISE(ABORT, 'temporary detail storage failure'); END
    """))
    await db_session.commit()

    result = await repo.update(log_id, _log_data(response_status=400, error_info="Upstream error"))

    assert result.is_completed is True
    assert result.response_status == 400
    assert result.error_info == "Upstream error"
