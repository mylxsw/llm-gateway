"""Startup recovery for request rows orphaned by a previous process."""

from datetime import datetime

from sqlalchemy import create_engine, select

from app.db.models import Base, RequestLog, RequestLogDetail
from app.db.session import _run_migrations


def test_startup_marks_orphaned_in_progress_logs_failed():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        result = connection.execute(
            RequestLog.__table__.insert().values(
                request_time=datetime(2026, 1, 1),
                requested_model="test-model",
                is_completed=False,
                is_stream=False,
                retry_count=0,
            )
        )
        log_id = result.inserted_primary_key[0]
        _run_migrations(connection)

        row = connection.execute(
            select(
                RequestLog.is_completed,
                RequestLog.response_status,
            ).where(RequestLog.id == log_id)
        ).one()
        error_info = connection.execute(
            select(RequestLogDetail.error_info).where(
                RequestLogDetail.log_id == log_id
            )
        ).scalar_one()

    engine.dispose()
    assert row.is_completed is True
    assert row.response_status == 500
    assert error_info == "Request interrupted by server restart"
