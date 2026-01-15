"""
ApiKeyService.authenticate unit tests
"""

from datetime import timezone

import pytest

from app.common.time import utc_now
from app.domain.api_key import ApiKeyCreate
from app.repositories.sqlalchemy.api_key_repo import SQLAlchemyApiKeyRepository
from app.services.api_key_service import ApiKeyService


@pytest.mark.asyncio
async def test_authenticate_updates_last_used_at(db_session):
    repo = SQLAlchemyApiKeyRepository(db_session)
    service = ApiKeyService(repo)

    created = await repo.create(ApiKeyCreate(key_name="test-key"), key_value="sk-test")
    assert created.last_used_at is None

    before = utc_now()
    await service.authenticate("Bearer sk-test")
    after = utc_now()

    updated = await repo.get_by_id(created.id)
    assert updated is not None
    assert updated.last_used_at is not None
    assert updated.last_used_at.tzinfo == timezone.utc
    assert before <= updated.last_used_at <= after
