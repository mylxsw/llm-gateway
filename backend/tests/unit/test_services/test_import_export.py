import pytest
from unittest.mock import AsyncMock, MagicMock
from app.common.time import utc_now
from app.domain.provider import ProviderCreate, Provider
from app.domain.model import ModelExport, ModelMapping, ModelProviderExport
from app.services.provider_service import ProviderService
from app.services.model_service import ModelService

@pytest.fixture
def provider_repo():
    return AsyncMock()

@pytest.fixture
def model_repo():
    return AsyncMock()

@pytest.fixture
def provider_service(provider_repo):
    return ProviderService(provider_repo)

@pytest.fixture
def model_service(model_repo, provider_repo):
    return ModelService(model_repo, provider_repo)

@pytest.mark.asyncio
async def test_provider_import_success(provider_service, provider_repo):
    data = [
        ProviderCreate(name="p1", base_url="http://p1", protocol="openai", api_type="chat"),
        ProviderCreate(name="p2", base_url="http://p2", protocol="anthropic", api_type="chat"),
    ]
    
    # Setup mocks: p1 exists, p2 does not
    provider_repo.get_by_name.side_effect = lambda name: MagicMock() if name == "p1" else None
    
    result = await provider_service.import_data(data)
    
    assert result["success"] == 1
    assert result["skipped"] == 1
    
    # Check create call
    assert provider_repo.create.call_count == 1
    assert provider_repo.create.call_args[0][0].name == "p2"

@pytest.mark.asyncio
async def test_model_import_success(model_service, model_repo, provider_repo):
    # Prepare data
    provider_export = ModelProviderExport(
        provider_name="p1", 
        target_model_name="gpt-4",
        priority=0,
        weight=1,
        is_active=True
    )
    model_export = ModelExport(
        requested_model="model1",
        strategy="round_robin",
        disable_thinking=True,
        providers=[provider_export]
    )
    data = [model_export]
    
    # Setup mocks
    # Model does not exist
    model_repo.get_mapping.side_effect = [None, None] 
    # Provider exists
    provider_repo.get_by_name.return_value = MagicMock(id=1, name="p1")
    
    result = await model_service.import_data(data)
    
    assert result["success"] == 1
    assert result["skipped"] == 0
    assert len(result["errors"]) == 0
    
    # Check calls
    assert model_repo.create_mapping.call_count == 1
    assert model_repo.create_mapping.call_args.args[0].disable_thinking is True
    assert model_repo.add_provider_mapping.call_count == 1
    # Verify provider mapping creation uses correct provider_id
    call_args = model_repo.add_provider_mapping.call_args[0][0]
    assert call_args.provider_id == 1
    assert call_args.target_model_name == "gpt-4"

@pytest.mark.asyncio
async def test_model_import_missing_provider(model_service, model_repo, provider_repo):
    # Prepare data
    provider_export = ModelProviderExport(
        provider_name="missing_provider", 
        target_model_name="gpt-4"
    )
    model_export = ModelExport(
        requested_model="model1",
        strategy="round_robin",
        providers=[provider_export]
    )
    data = [model_export]
    
    # Setup mocks
    model_repo.get_mapping.return_value = None
    provider_repo.get_by_name.return_value = None # Provider not found
    
    result = await model_service.import_data(data)
    
    # Model created, but provider mapping skipped (error recorded)
    assert result["success"] == 1 
    assert len(result["errors"]) == 1
    assert "Provider 'missing_provider' not found" in result["errors"][0]
    
    assert model_repo.create_mapping.call_count == 1
    assert model_repo.add_provider_mapping.call_count == 0


@pytest.mark.asyncio
async def test_model_import_validates_and_normalizes_aliases(
    model_service, model_repo, provider_repo
):
    alias_export = ModelExport(
        requested_model="latest-model",
        model_type="alias",
        alias_target_model="real-model",
        strategy="cost_first",
        matching_rules={"headers": {"x-tenant": "legacy"}},
        is_active=False,
        disable_thinking=True,
        providers=[
            ModelProviderExport(
                provider_name="p1",
                target_model_name="must-not-be-imported",
            )
        ],
    )
    real_export = ModelExport(
        requested_model="real-model",
        model_type="chat",
        providers=[],
    )
    stored = {}

    async def get_mapping(name):
        return stored.get(name)

    async def create_mapping(data):
        stored[data.requested_model] = data
        return data

    model_repo.get_mapping.side_effect = get_mapping
    model_repo.create_mapping.side_effect = create_mapping
    provider_repo.get_by_name.return_value = MagicMock(id=1, name="p1")

    result = await model_service.import_data([alias_export, real_export])

    assert result == {"success": 2, "skipped": 0, "errors": []}
    assert list(stored) == ["real-model", "latest-model"]
    imported_alias = stored["latest-model"]
    assert imported_alias.strategy == "round_robin"
    assert imported_alias.matching_rules is None
    assert imported_alias.alias_target_model == "real-model"
    assert imported_alias.is_active is True
    assert imported_alias.disable_thinking is False
    model_repo.add_provider_mapping.assert_not_awaited()


@pytest.mark.asyncio
async def test_model_export_includes_disable_thinking(
    model_service, model_repo
):
    now = utc_now()
    model_repo.get_all_mappings.return_value = (
        [
            ModelMapping(
                requested_model="reasoning-model",
                disable_thinking=True,
                created_at=now,
                updated_at=now,
            )
        ],
        1,
    )
    model_repo.get_provider_mappings.return_value = []

    exported = await model_service.export_data()

    assert len(exported) == 1
    assert exported[0].disable_thinking is True
