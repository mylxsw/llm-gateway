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
