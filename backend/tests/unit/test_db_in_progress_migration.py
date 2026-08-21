"""Startup recovery for request rows orphaned by a previous process."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.db.models import Base, ModelMapping, RequestLog, RequestLogDetail
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


def test_alias_target_foreign_key_has_stable_restrict_name():
    foreign_keys = list(ModelMapping.__table__.foreign_key_constraints)
    alias_fk = next(
        fk for fk in foreign_keys if "alias_target_model" in fk.column_keys
    )

    assert alias_fk.name == "fk_model_mappings_alias_target"
    assert alias_fk.ondelete == "RESTRICT"


def test_startup_adds_alias_target_model_to_existing_model_table():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE model_mappings ("
                "requested_model VARCHAR(100) PRIMARY KEY, "
                "model_type VARCHAR(50)"
                ")"
            )
        )

        _run_migrations(connection)

        columns = {column["name"] for column in inspect(connection).get_columns("model_mappings")}

    engine.dispose()
    assert "alias_target_model" in columns


def test_startup_enforces_alias_target_integrity_on_existing_sqlite_table():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE model_mappings ("
                "requested_model VARCHAR(100) PRIMARY KEY, "
                "model_type VARCHAR(50), "
                "alias_target_model VARCHAR(100)"
                ")"
            )
        )
        _run_migrations(connection)
        connection.execute(
            text(
                "INSERT INTO model_mappings(requested_model, model_type) "
                "VALUES ('real', 'chat')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO model_mappings(requested_model, model_type) "
                "VALUES ('legacy-real', NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO model_mappings(requested_model, model_type, alias_target_model) "
                "VALUES ('legacy-alias', 'alias', 'legacy-real')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO model_mappings(requested_model, model_type, alias_target_model) "
                "VALUES ('latest', 'alias', 'real')"
            )
        )

        with pytest.raises(IntegrityError, match="model_referenced_by_alias"):
            connection.execute(
                text("DELETE FROM model_mappings WHERE requested_model = 'real'")
            )

        with pytest.raises(IntegrityError, match="model_referenced_by_alias"):
            connection.execute(
                text(
                    "UPDATE model_mappings SET model_type = 'alias', "
                    "alias_target_model = 'other' WHERE requested_model = 'real'"
                )
            )

        with pytest.raises(IntegrityError, match="invalid_alias_target"):
            connection.execute(
                text(
                    "INSERT INTO model_mappings(requested_model, model_type, alias_target_model) "
                    "VALUES ('broken', 'alias', 'missing')"
                )
            )

    engine.dispose()
