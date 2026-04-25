from datetime import datetime, timezone

import pytest

from app.domain.log import RequestLogCreate
from app.domain.provider import ProviderCreate
from app.repositories.sqlalchemy.log_repo import SQLAlchemyLogRepository
from app.repositories.sqlalchemy.provider_repo import SQLAlchemyProviderRepository


@pytest.mark.asyncio
async def test_delete_provider_keeps_request_log_snapshot_fields(db_session):
    provider_repo = SQLAlchemyProviderRepository(db_session)
    log_repo = SQLAlchemyLogRepository(db_session)

    provider = await provider_repo.create(
        ProviderCreate(
            name="provider-delete-test",
            base_url="https://example.com",
            protocol="openai",
            api_type="chat",
            is_active=True,
        )
    )

    created_log = await log_repo.create(
        RequestLogCreate(
            request_time=datetime.now(timezone.utc),
            requested_model="gpt-4o",
            target_model="gpt-4o",
            provider_id=provider.id,
            provider_name=provider.name,
            response_status=200,
        )
    )

    deleted = await provider_repo.delete(provider.id)

    assert deleted is True
    assert await provider_repo.get_by_id(provider.id) is None

    fetched_log = await log_repo.get_by_id(created_log.id)
    assert fetched_log is not None
    assert fetched_log.provider_id == provider.id
    assert fetched_log.provider_name == provider.name
