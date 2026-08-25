"""Shared model-alias resolution for management and proxy paths."""

from app.common.errors import ServiceError
from app.domain.model import ModelMapping
from app.repositories.model_repo import ModelRepository


async def resolve_alias_target(
    model_repo: ModelRepository,
    requested_model: str,
    mapping: ModelMapping,
) -> tuple[str, ModelMapping]:
    """Return the concrete routing name and mapping for a requested model."""
    if mapping.model_type != "alias":
        return requested_model, mapping

    alias_target = mapping.alias_target_model
    if not alias_target:
        raise ServiceError(
            message=f"Alias model '{requested_model}' has an invalid target",
            code="invalid_alias_target",
        )

    target_mapping = await model_repo.get_mapping(alias_target)
    if not target_mapping or target_mapping.model_type == "alias":
        raise ServiceError(
            message=f"Alias model '{requested_model}' has an invalid target",
            code="invalid_alias_target",
        )
    if not target_mapping.is_active:
        raise ServiceError(
            message=f"Model '{alias_target}' is disabled",
            code="model_disabled",
        )
    return alias_target, target_mapping
