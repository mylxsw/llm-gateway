"""
Tests for create_mapping in SQLAlchemyModelRepository.

Verifies that all pricing fields (billing_mode, tiered_pricing,
per_request_price, per_image_price, cache_billing_enabled,
cached_input_price, cached_output_price) are correctly persisted
when creating a model mapping.
"""

import pytest
import pytest_asyncio

from app.domain.model import ModelMappingCreate, TokenTierPrice
from app.repositories.sqlalchemy.model_repo import SQLAlchemyModelRepository


@pytest_asyncio.fixture
async def model_repo(db_session):
    return SQLAlchemyModelRepository(db_session)


@pytest.mark.asyncio
class TestCreateMappingPersistsPricingFields:
    """Regression tests for the create_mapping bug fix."""

    async def test_create_mapping_persists_token_flat(self, model_repo):
        data = ModelMappingCreate(
            requested_model="test-flat",
            billing_mode="token_flat",
            input_price=5.0,
            output_price=15.0,
        )
        result = await model_repo.create_mapping(data)
        assert result.billing_mode == "token_flat"
        assert result.input_price == 5.0
        assert result.output_price == 15.0

    async def test_create_mapping_persists_token_tiered(self, model_repo):
        data = ModelMappingCreate(
            requested_model="test-tiered",
            billing_mode="token_tiered",
            tiered_pricing=[
                TokenTierPrice(
                    max_input_tokens=32768,
                    input_price=1.0,
                    output_price=2.0,
                ),
                TokenTierPrice(
                    max_input_tokens=None,
                    input_price=3.0,
                    output_price=4.0,
                    cached_input_price=0.5,
                ),
            ],
        )
        result = await model_repo.create_mapping(data)
        assert result.billing_mode == "token_tiered"
        assert result.tiered_pricing is not None
        assert len(result.tiered_pricing) == 2
        # Tiered pricing is stored as dicts
        tier0 = result.tiered_pricing[0]
        tier1 = result.tiered_pricing[1]
        if isinstance(tier0, dict):
            assert tier0["max_input_tokens"] == 32768
            assert tier0["input_price"] == 1.0
            assert tier0["output_price"] == 2.0
            assert tier1["max_input_tokens"] is None
            assert tier1["input_price"] == 3.0
            assert tier1["output_price"] == 4.0
            assert tier1["cached_input_price"] == 0.5
        else:
            assert tier0.max_input_tokens == 32768
            assert tier0.input_price == 1.0
            assert tier1.input_price == 3.0

    async def test_create_mapping_persists_per_request(self, model_repo):
        data = ModelMappingCreate(
            requested_model="test-per-request",
            billing_mode="per_request",
            per_request_price=0.05,
        )
        result = await model_repo.create_mapping(data)
        assert result.billing_mode == "per_request"
        assert result.per_request_price == 0.05

    async def test_create_mapping_persists_per_image(self, model_repo):
        data = ModelMappingCreate(
            requested_model="test-per-image",
            model_type="images",
            billing_mode="per_image",
            per_image_price=0.04,
        )
        result = await model_repo.create_mapping(data)
        assert result.billing_mode == "per_image"
        assert result.per_image_price == 0.04

    async def test_create_mapping_persists_cache_billing(self, model_repo):
        data = ModelMappingCreate(
            requested_model="test-cache",
            billing_mode="token_flat",
            input_price=5.0,
            output_price=15.0,
            cache_billing_enabled=True,
            cached_input_price=1.0,
            cached_output_price=3.0,
        )
        result = await model_repo.create_mapping(data)
        assert result.billing_mode == "token_flat"
        assert result.cache_billing_enabled is True
        assert result.cached_input_price == 1.0
        assert result.cached_output_price == 3.0

    async def test_create_mapping_roundtrip_get(self, model_repo):
        """Create and then get the mapping to verify persistence."""
        data = ModelMappingCreate(
            requested_model="test-roundtrip",
            billing_mode="token_tiered",
            tiered_pricing=[
                TokenTierPrice(
                    max_input_tokens=32768,
                    input_price=1.0,
                    output_price=2.0,
                ),
            ],
            cache_billing_enabled=True,
            cached_input_price=0.5,
        )
        await model_repo.create_mapping(data)

        fetched = await model_repo.get_mapping("test-roundtrip")
        assert fetched is not None
        assert fetched.billing_mode == "token_tiered"
        assert fetched.tiered_pricing is not None
        assert len(fetched.tiered_pricing) == 1
        assert fetched.cache_billing_enabled is True
        assert fetched.cached_input_price == 0.5

    async def test_create_mapping_no_billing_mode(self, model_repo):
        """When no billing_mode is set, fields should be None."""
        data = ModelMappingCreate(
            requested_model="test-no-billing",
        )
        result = await model_repo.create_mapping(data)
        assert result.billing_mode is None
        assert result.tiered_pricing is None
        assert result.per_request_price is None
        assert result.per_image_price is None
