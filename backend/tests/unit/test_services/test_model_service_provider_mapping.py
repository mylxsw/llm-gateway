"""
ModelService provider mapping unit tests
"""

import pytest
from app.domain.model import ModelMappingCreate, ModelMappingProviderCreate
from app.domain.provider import ProviderCreate
from app.repositories.sqlalchemy.model_repo import SQLAlchemyModelRepository
from app.repositories.sqlalchemy.provider_repo import SQLAlchemyProviderRepository
from app.services.model_service import ModelService


@pytest.mark.asyncio
async def test_create_provider_mapping_allows_duplicates(db_session):
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

    created_second = await service.create_provider_mapping(
        ModelMappingProviderCreate(
            requested_model="gpt-4o-mini",
            provider_id=provider.id,
            target_model_name="gpt-4o-mini",
            input_price=0.0,
            output_price=0.0,
        )
    )
    assert created_second.requested_model == "gpt-4o-mini"
    assert created_second.provider_id == provider.id
    assert created_second.provider_name == "p1"


@pytest.mark.asyncio
async def test_get_mapping_includes_provider_active_status(db_session):
    model_repo = SQLAlchemyModelRepository(db_session)
    provider_repo = SQLAlchemyProviderRepository(db_session)
    service = ModelService(model_repo, provider_repo)

    await model_repo.create_mapping(ModelMappingCreate(requested_model="gpt-4o-mini"))
    provider = await provider_repo.create(
        ProviderCreate(
            name="p-inactive",
            base_url="https://example.com",
            protocol="openai",
            api_type="chat",
            is_active=False,
        )
    )

    await service.create_provider_mapping(
        ModelMappingProviderCreate(
            requested_model="gpt-4o-mini",
            provider_id=provider.id,
            target_model_name="gpt-4o-mini",
            input_price=0.0,
            output_price=0.0,
            is_active=True,
        )
    )

    mapping = await service.get_mapping("gpt-4o-mini")
    assert mapping.providers is not None
    assert len(mapping.providers) == 1
    assert mapping.providers[0].provider_is_active is False
