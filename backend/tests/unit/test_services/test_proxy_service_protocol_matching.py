from app.common.time import utc_now
from unittest.mock import AsyncMock

import pytest

from app.common.errors import ServiceError
from app.domain.model import ModelMapping, ModelMappingProviderResponse
from app.domain.provider import Provider
from app.services.proxy_service import ProxyService


class FakeModelRepo:
    def __init__(self, mapping: ModelMapping, provider_mappings: list[ModelMappingProviderResponse]):
        self._mapping = mapping
        self._provider_mappings = provider_mappings

    async def get_mapping(self, requested_model: str):
        return self._mapping if requested_model == self._mapping.requested_model else None

    async def get_provider_mappings(self, requested_model: str, is_active: bool = True):
        if requested_model != self._mapping.requested_model:
            return []
        return self._provider_mappings


class FakeProviderRepo:
    def __init__(self, providers: dict[int, Provider]):
        self._providers = providers

    async def get_by_id(self, provider_id: int):
        return self._providers.get(provider_id)


@pytest.mark.asyncio
async def test_resolve_candidates_does_not_filter_by_request_protocol_anymore():
    now = utc_now()
    model_mapping = ModelMapping(
        requested_model="test-model",
        strategy="round_robin",
        matching_rules=None,
        capabilities=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    provider_mappings = [
        ModelMappingProviderResponse(
            id=1,
            requested_model="test-model",
            provider_id=1,
            provider_name="p-openai",
            target_model_name="gpt-4o-mini",
            provider_rules=None,
            priority=0,
            weight=1,
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        ModelMappingProviderResponse(
            id=2,
            requested_model="test-model",
            provider_id=2,
            provider_name="p-anthropic",
            target_model_name="claude-3-5-sonnet",
            provider_rules=None,
            priority=0,
            weight=1,
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
    ]

    providers = {
        1: Provider(
            id=1,
            name="p-openai",
            base_url="https://example.com",
            protocol="openai",
            api_type="chat",
            api_key="sk-openai",
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        2: Provider(
            id=2,
            name="p-anthropic",
            base_url="https://example.com",
            protocol="anthropic",
            api_type="chat",
            api_key="sk-anthropic",
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
    }

    service = ProxyService(
        model_repo=FakeModelRepo(model_mapping, provider_mappings),
        provider_repo=FakeProviderRepo(providers),
        log_repo=AsyncMock(),
    )

    _, openai_candidates, _, openai_protocol, _ = await service._resolve_candidates(
        requested_model="test-model",
        request_protocol="openai",
        headers={},
        body={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert openai_protocol == "openai"
    assert {c.provider_id for c in openai_candidates} == {1, 2}
    assert {c.protocol for c in openai_candidates} == {"openai", "anthropic"}

    _, anthropic_candidates, _, anthropic_protocol, _ = await service._resolve_candidates(
        requested_model="test-model",
        request_protocol="anthropic",
        headers={},
        body={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert anthropic_protocol == "anthropic"
    assert {c.provider_id for c in anthropic_candidates} == {1, 2}
    assert {c.protocol for c in anthropic_candidates} == {"openai", "anthropic"}
