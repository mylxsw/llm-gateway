"""Persist inherited pricing without violating the cache flag's NOT NULL constraint."""

import pytest

from app.domain.model import (
    ModelMappingCreate,
    ModelMappingProviderCreate,
    ModelMappingProviderUpdate,
)
from app.domain.provider import ProviderCreate
from app.repositories.sqlalchemy.model_repo import SQLAlchemyModelRepository
from app.repositories.sqlalchemy.provider_repo import SQLAlchemyProviderRepository
from app.services.model_service import ModelService


@pytest.mark.asyncio
@pytest.mark.parametrize("bulk", [False, True], ids=["single", "bulk"])
@pytest.mark.parametrize(
    "initial,patch,expected",
    [
        (True, {"cache_billing_enabled": None}, False),
        (True, {}, True),
        (False, {}, False),
        (False, {"cache_billing_enabled": True}, True),
        (True, {"cache_billing_enabled": False}, False),
    ],
    ids=["null", "omitted-true", "omitted-false", "enable", "disable"],
)
async def test_provider_billing_update_preserves_patch_semantics(
    db_session, bulk, initial, patch, expected
):
    repo = SQLAlchemyModelRepository(db_session)
    provider_repo = SQLAlchemyProviderRepository(db_session)
    service = ModelService(repo, provider_repo)
    await repo.create_mapping(
        ModelMappingCreate(
            requested_model="billing-model",
            billing_mode="token_flat",
            input_price=2.0,
            output_price=3.0,
            cache_billing_enabled=True,
            cached_input_price=0.5,
        )
    )
    provider = await provider_repo.create(
        ProviderCreate(
            name="billing-provider", base_url="https://example.com", protocol="openai"
        )
    )
    mappings = []
    for target in ("upstream", "upstream", "unmatched"):
        mappings.append(await repo.add_provider_mapping(
            ModelMappingProviderCreate(
                requested_model="billing-model",
                provider_id=provider.id,
                target_model_name=target,
                billing_mode="token_flat",
                input_price=10.0,
                output_price=20.0,
                cache_billing_enabled=initial,
                cached_input_price=5.0,
            )
        ))

    # Match the legacy frontend's inheritance payload, including nullable prices.
    update = ModelMappingProviderUpdate(
        billing_mode="inherit_model_default",
        input_price=None,
        output_price=None,
        cached_input_price=None,
        **patch,
    )
    if bulk:
        assert await repo.bulk_update_provider_mappings(
            provider.id, "upstream", update
        ) == 2
    else:
        await service.update_provider_mapping(mappings[0].id, update)

    # Reload committed rows instead of relying on previously returned objects.
    db_session.expire_all()
    for index, original in enumerate(mappings):
        saved = await repo.get_provider_mapping(original.id)
        assert saved is not None
        changed = index < (2 if bulk else 1)
        assert saved.cache_billing_enabled is (expected if changed else initial)
        assert saved.billing_mode == ("inherit_model_default" if changed else "token_flat")
        assert saved.input_price == (None if changed else 10.0)
        assert saved.output_price == (None if changed else 20.0)
        assert saved.cached_input_price == (None if changed else 5.0)

    history = await service.get_provider_pricing_history("upstream")
    assert len(history) == 1
    assert history[0].resolved_cache_billing_enabled is True
    assert history[0].resolved_cached_input_price == 0.5
    assert history[0].resolved_input_price == 2.0
    assert history[0].resolved_output_price == 3.0
