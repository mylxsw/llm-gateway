"""
ModelService provider mapping unit tests
"""

import pytest

from app.common.errors import ConflictError
from app.domain.model import ModelMappingCreate, ModelMappingProviderCreate
from app.domain.provider import ProviderCreate
from app.repositories.sqlalchemy.model_repo import SQLAlchemyModelRepository
from app.repositories.sqlalchemy.provider_repo import SQLAlchemyProviderRepository
from app.services.model_service import ModelService


@pytest.mark.asyncio
async def test_create_provider_mapping_rejects_duplicates(db_session):
    model_repo = SQLAlchemyModelRepository(db_session)
    provider_repo = SQLAlchemyProviderRepository(db_session)
    service = ModelService(model_repo, provider_repo)

    await model_repo.create_mapping(ModelMappingCreate(requested_model="gpt-4o-mini"))
    provider = await provider_repo.create(
        ProviderCreate(
            name="p1",
            base_url="https://example.com",
            protocol="openai",
            api_type="chat",
        )
    )

    created = await service.create_provider_mapping(
        ModelMappingProviderCreate(
            requested_model="gpt-4o-mini",
            provider_id=provider.id,
            target_model_name="gpt-4o-mini",
            input_price=0.0,
            output_price=0.0,
        )
    )
    assert created.requested_model == "gpt-4o-mini"
    assert created.provider_id == provider.id
    assert created.provider_name == "p1"

    with pytest.raises(ConflictError) as exc:
        await service.create_provider_mapping(
            ModelMappingProviderCreate(
                requested_model="gpt-4o-mini",
                provider_id=provider.id,
                target_model_name="gpt-4o-mini",
                input_price=0.0,
                output_price=0.0,
            )
        )
    assert exc.value.code == "duplicate_mapping"
