from datetime import datetime, timezone

import pytest

from app.domain.log import RequestLogCreate, RequestLogQuery
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository


@pytest.mark.asyncio
async def test_query_has_error_filter_includes_non_200_status(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    now = datetime.now(timezone.utc)

    ok_log = await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="model-ok",
            target_model="target-ok",
            response_status=200,
            error_info=None,
            api_key_id=1,
            provider_id=1,
            is_stream=False,
        )
    )
    non_200_log = await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="model-non-200",
            target_model="target-non-200",
            response_status=500,
            error_info=None,
            api_key_id=1,
            provider_id=1,
            is_stream=False,
        )
    )
    error_info_log = await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="model-error-info",
            target_model="target-error-info",
            response_status=200,
            error_info="upstream failed",
            api_key_id=1,
            provider_id=1,
            is_stream=False,
        )
    )

    has_error_items, has_error_total = await repo.query(
        RequestLogQuery(has_error=True, page=1, page_size=20)
    )
    has_error_ids = {item.id for item in has_error_items}

    assert has_error_total == 2
    assert non_200_log.id in has_error_ids
    assert error_info_log.id in has_error_ids
    assert ok_log.id not in has_error_ids

    no_error_items, no_error_total = await repo.query(
        RequestLogQuery(has_error=False, page=1, page_size=20)
    )
    no_error_ids = {item.id for item in no_error_items}

    assert no_error_total == 1
    assert ok_log.id in no_error_ids
    assert non_200_log.id not in no_error_ids
    assert error_info_log.id not in no_error_ids


@pytest.mark.asyncio
async def test_query_user_id_filter(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    now = datetime.now(timezone.utc)

    matching_log = await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="model-a",
            target_model="target-a",
            response_status=200,
            api_key_id=1,
            provider_id=1,
            user_id="tenant-user-123",
            is_stream=False,
        )
    )
    other_log = await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="model-b",
            target_model="target-b",
            response_status=200,
            api_key_id=1,
            provider_id=1,
            user_id="another-user",
            is_stream=False,
        )
    )

    items, total = await repo.query(
        RequestLogQuery(user_id="user-123", page=1, page_size=20)
    )
    ids = {item.id for item in items}

    assert total == 1
    assert matching_log.id in ids
    assert other_log.id not in ids
    assert items[0].user_id == "tenant-user-123"


@pytest.mark.asyncio
async def test_query_groups_retry_attempts_before_pagination(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    now = datetime.now(timezone.utc)

    root = await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="grouped-model",
            provider_name="final-provider",
            response_status=200,
            retry_count=2,
            trace_id="trace-with-retries",
        )
    )
    attempts = []
    for index in range(2):
        attempts.append(
            await repo.create(
                RequestLogCreate(
                    request_time=now,
                    requested_model="grouped-model",
                    provider_name=f"failed-provider-{index}",
                    response_status=500,
                    retry_count=index + 1,
                    trace_id="trace-with-retries",
                )
            )
        )

    standalone = await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="standalone-model",
            response_status=200,
            trace_id=None,
        )
    )

    page_one, total = await repo.query(
        RequestLogQuery(page=1, page_size=1, sort_by="id", sort_order="asc")
    )
    page_two, _ = await repo.query(
        RequestLogQuery(page=2, page_size=1, sort_by="id", sort_order="asc")
    )

    assert total == 2
    assert [item.id for item in page_one] == [root.id]
    assert page_one[0].retry_attempt_count == 2
    assert [item.id for item in page_one[0].retry_attempts] == [
        attempt.id for attempt in attempts
    ]
    assert [item.id for item in page_two] == [standalone.id]


@pytest.mark.asyncio
async def test_query_filters_group_by_final_result(db_session):
    repo = SQLAlchemyLogRepository(db_session)
    now = datetime.now(timezone.utc)

    root = await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="recovered-model",
            response_status=200,
            retry_count=1,
            trace_id="recovered-trace",
        )
    )
    await repo.create(
        RequestLogCreate(
            request_time=now,
            requested_model="recovered-model",
            response_status=503,
            retry_count=1,
            trace_id="recovered-trace",
        )
    )

    success_items, success_total = await repo.query(
        RequestLogQuery(status_min=200, status_max=299)
    )
    error_items, error_total = await repo.query(
        RequestLogQuery(status_min=500, status_max=599)
    )

    assert success_total == 1
    assert [item.id for item in success_items] == [root.id]
    assert success_items[0].retry_attempt_count == 1
    assert error_total == 0
    assert error_items == []
