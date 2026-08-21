from app.common.time import utc_now
from unittest.mock import AsyncMock, patch

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


class MultiModelRepo:
    def __init__(
        self,
        mappings: dict[str, ModelMapping],
        provider_mappings: dict[str, list[ModelMappingProviderResponse]],
    ):
        self._mappings = mappings
        self._provider_mappings = provider_mappings

    async def get_mapping(self, requested_model: str):
        return self._mappings.get(requested_model)

    async def get_provider_mappings(self, requested_model: str, is_active: bool = True):
        return self._provider_mappings.get(requested_model, [])


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


@pytest.mark.asyncio
async def test_resolve_candidates_rewrites_alias_to_real_model():
    now = utc_now()
    alias = ModelMapping(
        requested_model="gpt-latest",
        model_type="alias",
        alias_target_model="gpt-4o",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    real = ModelMapping(
        requested_model="gpt-4o",
        model_type="chat",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    provider_mapping = ModelMappingProviderResponse(
        id=1,
        requested_model="gpt-4o",
        provider_id=1,
        provider_name="openai",
        target_model_name="gpt-4o-2024-08-06",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    provider = Provider(
        id=1,
        name="openai",
        base_url="https://example.com",
        protocol="openai",
        api_type="chat",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    body = {"model": "gpt-latest", "messages": [{"role": "user", "content": "hi"}]}
    service = ProxyService(
        model_repo=MultiModelRepo(
            {"gpt-latest": alias, "gpt-4o": real},
            {"gpt-4o": [provider_mapping]},
        ),
        provider_repo=FakeProviderRepo({1: provider}),
        log_repo=AsyncMock(),
    )

    with patch("app.services.proxy_service.logger.info") as log_info:
        mapping, candidates, _, _, _ = await service._resolve_candidates(
            requested_model="gpt-latest",
            request_protocol="openai",
            headers={},
            body=body,
            trace_id="trace-alias-test",
        )

    assert mapping.requested_model == "gpt-4o"
    assert body["model"] == "gpt-4o"
    assert [candidate.target_model for candidate in candidates] == ["gpt-4o-2024-08-06"]
    log_info.assert_called_once_with(
        "Model alias resolved: alias=%s target=%s trace_id=%s",
        "gpt-latest",
        "gpt-4o",
        "trace-alias-test",
    )


@pytest.mark.asyncio
async def test_resolve_candidates_filters_inactive_providers():
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
            provider_name="p-active",
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
            provider_name="p-inactive",
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
            name="p-active",
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
            name="p-inactive",
            base_url="https://example.com",
            protocol="anthropic",
            api_type="chat",
            api_key="sk-anthropic",
            is_active=False,
            created_at=now,
            updated_at=now,
        ),
    }

    service = ProxyService(
        model_repo=FakeModelRepo(model_mapping, provider_mappings),
        provider_repo=FakeProviderRepo(providers),
        log_repo=AsyncMock(),
    )

    _, candidates, _, _, _ = await service._resolve_candidates(
        requested_model="test-model",
        request_protocol="openai",
        headers={},
        body={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert [c.provider_id for c in candidates] == [1]


@pytest.mark.asyncio
async def test_resolve_candidates_raises_when_all_providers_inactive():
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
            provider_name="p-inactive",
            target_model_name="gpt-4o-mini",
            provider_rules=None,
            priority=0,
            weight=1,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    ]

    providers = {
        1: Provider(
            id=1,
            name="p-inactive",
            base_url="https://example.com",
            protocol="openai",
            api_type="chat",
            api_key="sk-openai",
            is_active=False,
            created_at=now,
            updated_at=now,
        )
    }

    service = ProxyService(
        model_repo=FakeModelRepo(model_mapping, provider_mappings),
        provider_repo=FakeProviderRepo(providers),
        log_repo=AsyncMock(),
    )

    with pytest.raises(ServiceError) as exc_info:
        await service._resolve_candidates(
            requested_model="test-model",
            request_protocol="openai",
            headers={},
            body={"model": "test-model", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert exc_info.value.code == "no_available_provider"
