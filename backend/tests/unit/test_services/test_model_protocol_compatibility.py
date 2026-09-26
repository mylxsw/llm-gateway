"""
Model type / provider protocol compatibility.

A Jev model may only be bound to a Jev provider and a Jev provider may only
serve Jev models, because no conversion exists between Jev and the chat
protocols. These tests cover every path that can create or invalidate such a
binding.
"""

import pytest

from app.common.errors import ValidationError
from app.common.provider_protocols import (
    is_model_type_protocol_compatible,
    model_type_protocol_mismatch_message,
)
from app.domain.model import (
    ModelExport,
    ModelMappingCreate,
    ModelMappingProviderCreate,
    ModelMappingUpdate,
)
from app.domain.provider import ProviderCreate, ProviderUpdate
from app.repositories.sqlalchemy.model_repo import SQLAlchemyModelRepository
from app.repositories.sqlalchemy.provider_repo import SQLAlchemyProviderRepository
from app.services.model_service import ModelService
from app.services.provider_service import ProviderService


async def _make_provider(provider_repo, name: str, protocol: str):
    return await provider_repo.create(
        ProviderCreate(
            name=name,
            base_url="https://example.com",
            protocol=protocol,
            api_type="chat",
        )
    )


def _binding(requested_model: str, provider_id: int, target: str = "target-model"):
    return ModelMappingProviderCreate(
        requested_model=requested_model,
        provider_id=provider_id,
        target_model_name=target,
        input_price=0.0,
        output_price=0.0,
    )


class TestCompatibilityRule:
    @pytest.mark.parametrize(
        "model_type,protocol,expected",
        [
            ("jev", "jev", True),
            ("jev", "openai", False),
            ("jev", "anthropic", False),
            ("jev", "gemini", False),
            ("chat", "jev", False),
            ("embedding", "jev", False),
            ("images", "jev", False),
            ("chat", "openai", True),
            ("embedding", "anthropic", True),
            # Aliased frontend protocols resolve to their implementation.
            ("chat", "deepseek", True),
            ("jev", "deepseek", False),
            # Case and padding are normalized.
            ("JEV", " jev ", True),
            # A missing model type defaults to chat.
            (None, "openai", True),
            (None, "jev", False),
            # An unknown protocol is never Jev.
            ("jev", "bogus", False),
            ("chat", "bogus", True),
        ],
    )
    def test_rule(self, model_type, protocol, expected):
        assert is_model_type_protocol_compatible(model_type, protocol) is expected

    def test_mismatch_message_preserves_provider_name_case(self):
        message = model_type_protocol_mismatch_message("jev", "openai", "OpenAI-Prod")
        assert "OpenAI-Prod" in message
        assert "'jev'" in message
        assert "'openai'" in message

    def test_mismatch_message_without_provider_name(self):
        message = model_type_protocol_mismatch_message("chat", "jev")
        assert "the provider" in message
        assert "'chat'" in message


class TestCreateProviderMapping:
    @pytest.mark.asyncio
    async def test_jev_model_accepts_jev_provider(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="jev-latest", model_type="jev")
        )
        provider = await _make_provider(provider_repo, "typesafe", "jev")

        created = await service.create_provider_mapping(
            _binding("jev-latest", provider.id, "jev-1.13.0")
        )
        assert created.provider_id == provider.id

    @pytest.mark.asyncio
    async def test_jev_model_rejects_openai_provider(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="jev-latest", model_type="jev")
        )
        provider = await _make_provider(provider_repo, "openai-prod", "openai")

        with pytest.raises(ValidationError) as excinfo:
            await service.create_provider_mapping(
                _binding("jev-latest", provider.id, "gpt-4o-mini")
            )
        assert excinfo.value.code == "model_protocol_mismatch"
        assert "openai-prod" in excinfo.value.message

    @pytest.mark.asyncio
    async def test_chat_model_rejects_jev_provider(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="gpt-4o-mini", model_type="chat")
        )
        provider = await _make_provider(provider_repo, "typesafe", "jev")

        with pytest.raises(ValidationError) as excinfo:
            await service.create_provider_mapping(
                _binding("gpt-4o-mini", provider.id)
            )
        assert excinfo.value.code == "model_protocol_mismatch"

    @pytest.mark.asyncio
    async def test_chat_model_still_accepts_chat_provider(self, db_session):
        """The new rule must not constrain any pre-existing combination."""
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="gpt-4o-mini", model_type="chat")
        )
        for name, protocol in [
            ("p-openai", "openai"),
            ("p-anthropic", "anthropic"),
            ("p-gemini", "gemini"),
            ("p-deepseek", "deepseek"),
        ]:
            provider = await _make_provider(provider_repo, name, protocol)
            created = await service.create_provider_mapping(
                _binding("gpt-4o-mini", provider.id)
            )
            assert created.provider_id == provider.id


class TestModelTypeChange:
    @pytest.mark.asyncio
    async def test_cannot_switch_to_jev_while_openai_provider_bound(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="m1", model_type="chat")
        )
        provider = await _make_provider(provider_repo, "openai-prod", "openai")
        await service.create_provider_mapping(_binding("m1", provider.id))

        with pytest.raises(ValidationError) as excinfo:
            await service.update_mapping("m1", ModelMappingUpdate(model_type="jev"))
        assert excinfo.value.code == "model_protocol_mismatch"
        assert "openai-prod" in excinfo.value.message

    @pytest.mark.asyncio
    async def test_cannot_switch_away_from_jev_while_jev_provider_bound(
        self, db_session
    ):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="jev-latest", model_type="jev")
        )
        provider = await _make_provider(provider_repo, "typesafe", "jev")
        await service.create_provider_mapping(_binding("jev-latest", provider.id))

        with pytest.raises(ValidationError) as excinfo:
            await service.update_mapping(
                "jev-latest", ModelMappingUpdate(model_type="chat")
            )
        assert excinfo.value.code == "model_protocol_mismatch"

    @pytest.mark.asyncio
    async def test_switch_is_allowed_without_bound_providers(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="m2", model_type="chat")
        )
        updated = await service.update_mapping(
            "m2", ModelMappingUpdate(model_type="jev")
        )
        assert updated.model_type == "jev"

    @pytest.mark.asyncio
    async def test_unrelated_update_is_untouched(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="m3", model_type="chat")
        )
        provider = await _make_provider(provider_repo, "openai-prod", "openai")
        await service.create_provider_mapping(_binding("m3", provider.id))

        updated = await service.update_mapping(
            "m3", ModelMappingUpdate(is_active=False)
        )
        assert updated.is_active is False


class TestProviderProtocolChange:
    @pytest.mark.asyncio
    async def test_cannot_change_protocol_while_jev_model_bound(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        model_service = ModelService(model_repo, provider_repo)
        provider_service = ProviderService(provider_repo, model_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="jev-latest", model_type="jev")
        )
        provider = await _make_provider(provider_repo, "typesafe", "jev")
        await model_service.create_provider_mapping(
            _binding("jev-latest", provider.id)
        )

        with pytest.raises(ValidationError) as excinfo:
            await provider_service.update(
                provider.id, ProviderUpdate(protocol="openai")
            )
        assert excinfo.value.code == "model_protocol_mismatch"
        assert "jev-latest" in excinfo.value.message

    @pytest.mark.asyncio
    async def test_cannot_switch_provider_into_jev_while_chat_model_bound(
        self, db_session
    ):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        model_service = ModelService(model_repo, provider_repo)
        provider_service = ProviderService(provider_repo, model_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="gpt-4o-mini", model_type="chat")
        )
        provider = await _make_provider(provider_repo, "openai-prod", "openai")
        await model_service.create_provider_mapping(
            _binding("gpt-4o-mini", provider.id)
        )

        with pytest.raises(ValidationError) as excinfo:
            await provider_service.update(provider.id, ProviderUpdate(protocol="jev"))
        assert excinfo.value.code == "model_protocol_mismatch"

    @pytest.mark.asyncio
    async def test_protocol_change_allowed_without_bindings(self, db_session):
        provider_repo = SQLAlchemyProviderRepository(db_session)
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_service = ProviderService(provider_repo, model_repo)

        provider = await _make_provider(provider_repo, "typesafe", "jev")
        updated = await provider_service.update(
            provider.id, ProviderUpdate(protocol="openai")
        )
        assert updated.protocol == "openai"

    @pytest.mark.asyncio
    async def test_compatible_protocol_change_still_allowed(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        model_service = ModelService(model_repo, provider_repo)
        provider_service = ProviderService(provider_repo, model_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="m4", model_type="chat")
        )
        provider = await _make_provider(provider_repo, "p", "openai")
        await model_service.create_provider_mapping(_binding("m4", provider.id))

        updated = await provider_service.update(
            provider.id, ProviderUpdate(protocol="anthropic")
        )
        assert updated.protocol == "anthropic"

    @pytest.mark.asyncio
    async def test_check_is_skipped_without_model_repo(self, db_session):
        """Back-compat: the service still works when constructed with one repo."""
        provider_repo = SQLAlchemyProviderRepository(db_session)
        model_repo = SQLAlchemyModelRepository(db_session)
        model_service = ModelService(model_repo, provider_repo)

        await model_repo.create_mapping(
            ModelMappingCreate(requested_model="jev-latest", model_type="jev")
        )
        provider = await _make_provider(provider_repo, "typesafe", "jev")
        await model_service.create_provider_mapping(
            _binding("jev-latest", provider.id)
        )

        legacy_service = ProviderService(provider_repo)
        updated = await legacy_service.update(
            provider.id, ProviderUpdate(protocol="openai")
        )
        assert updated.protocol == "openai"


class TestImport:
    @pytest.mark.asyncio
    async def test_incompatible_binding_is_skipped_with_an_error(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await _make_provider(provider_repo, "openai-prod", "openai")

        result = await service.import_data(
            [
                ModelExport(
                    requested_model="jev-latest",
                    model_type="jev",
                    providers=[
                        {
                            "provider_name": "openai-prod",
                            "target_model_name": "gpt-4o-mini",
                            "input_price": 0.0,
                            "output_price": 0.0,
                        }
                    ],
                )
            ]
        )

        assert result["success"] == 1
        assert len(result["errors"]) == 1
        assert "openai-prod" in result["errors"][0]
        # The model itself is imported, but the bad binding is not.
        mappings = await service.get_provider_mappings(requested_model="jev-latest")
        assert mappings == []

    @pytest.mark.asyncio
    async def test_compatible_binding_imports(self, db_session):
        model_repo = SQLAlchemyModelRepository(db_session)
        provider_repo = SQLAlchemyProviderRepository(db_session)
        service = ModelService(model_repo, provider_repo)

        await _make_provider(provider_repo, "typesafe", "jev")

        result = await service.import_data(
            [
                ModelExport(
                    requested_model="jev-latest",
                    model_type="jev",
                    providers=[
                        {
                            "provider_name": "typesafe",
                            "target_model_name": "jev-1.13.0",
                            "input_price": 0.042,
                            "output_price": 0.0,
                        }
                    ],
                )
            ]
        )

        assert result["errors"] == []
        mappings = await service.get_provider_mappings(requested_model="jev-latest")
        assert len(mappings) == 1
        assert mappings[0].target_model_name == "jev-1.13.0"
