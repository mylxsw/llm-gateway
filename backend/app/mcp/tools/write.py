"""
MCP write tools (management operations)

Guarded by MCP_ALLOW_WRITE. These reuse the existing service layer so business
logic is never duplicated.

SECURITY: These tools deliberately do NOT expose grant/revoke of MCP admin
capability. `update_api_key` strips any `is_mcp_admin` field from its input so a
key can never escalate or spread MCP admin privilege — that action is available
only through the Web admin UI.
"""

from __future__ import annotations

from typing import Any

from app.domain.api_key import ApiKeyCreate, ApiKeyUpdate
from app.domain.model import (
    ModelMappingCreate,
    ModelMappingProviderCreate,
    ModelMappingProviderUpdate,
    ModelMappingUpdate,
)
from app.domain.provider import ProviderCreate, ProviderUpdate
from app.mcp.redaction import serialize_model
from app.mcp.tools import audit, db_session, ensure_writes_enabled
from app.repositories.sqlalchemy import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyLogRepository,
    SQLAlchemyModelRepository,
    SQLAlchemyProviderRepository,
)
from app.services import ApiKeyService, LogService, ModelService, ProviderService


def _err(exc: Exception) -> dict[str, Any]:
    message = getattr(exc, "message", None) or str(exc)
    return {"error": message}


# ----------------------------- Providers -----------------------------


async def create_provider(data: dict[str, Any]) -> dict[str, Any]:
    """Create a service provider. `data` matches ProviderCreate fields."""
    ensure_writes_enabled()
    audit("create_provider", name=data.get("name"))
    async with db_session() as session:
        service = ProviderService(SQLAlchemyProviderRepository(session))
        try:
            result = await service.create(ProviderCreate(**data))
        except Exception as exc:  # noqa: BLE001 - surface as tool error
            return _err(exc)
    return serialize_model(result)


async def update_provider(provider_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Update a service provider. `data` matches ProviderUpdate fields."""
    ensure_writes_enabled()
    audit("update_provider", provider_id=provider_id)
    async with db_session() as session:
        service = ProviderService(SQLAlchemyProviderRepository(session))
        try:
            result = await service.update(provider_id, ProviderUpdate(**data))
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return serialize_model(result)


async def delete_provider(provider_id: int) -> dict[str, Any]:
    """Delete a service provider by id."""
    ensure_writes_enabled()
    audit("delete_provider", provider_id=provider_id)
    async with db_session() as session:
        service = ProviderService(SQLAlchemyProviderRepository(session))
        try:
            await service.delete(provider_id)
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return {"ok": True, "provider_id": provider_id}


# ----------------------------- Models -----------------------------


def _model_service(session) -> ModelService:
    return ModelService(
        SQLAlchemyModelRepository(session),
        SQLAlchemyProviderRepository(session),
    )


async def create_model(data: dict[str, Any]) -> dict[str, Any]:
    """Create a model mapping. `data` matches ModelMappingCreate fields."""
    ensure_writes_enabled()
    audit("create_model", requested_model=data.get("requested_model"))
    async with db_session() as session:
        try:
            result = await _model_service(session).create_mapping(
                ModelMappingCreate(**data)
            )
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return serialize_model(result)


async def update_model(requested_model: str, data: dict[str, Any]) -> dict[str, Any]:
    """Update a model mapping. `data` matches ModelMappingUpdate fields."""
    ensure_writes_enabled()
    audit("update_model", requested_model=requested_model)
    async with db_session() as session:
        try:
            result = await _model_service(session).update_mapping(
                requested_model, ModelMappingUpdate(**data)
            )
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return serialize_model(result)


async def delete_model(requested_model: str) -> dict[str, Any]:
    """Delete a model mapping by requested model name."""
    ensure_writes_enabled()
    audit("delete_model", requested_model=requested_model)
    async with db_session() as session:
        try:
            await _model_service(session).delete_mapping(requested_model)
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return {"ok": True, "requested_model": requested_model}


async def create_model_provider(data: dict[str, Any]) -> dict[str, Any]:
    """Create a model-provider mapping. Matches ModelMappingProviderCreate."""
    ensure_writes_enabled()
    audit("create_model_provider", requested_model=data.get("requested_model"))
    async with db_session() as session:
        try:
            result = await _model_service(session).create_provider_mapping(
                ModelMappingProviderCreate(**data)
            )
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return serialize_model(result)


async def update_model_provider(mapping_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Update a model-provider mapping. Matches ModelMappingProviderUpdate."""
    ensure_writes_enabled()
    audit("update_model_provider", mapping_id=mapping_id)
    async with db_session() as session:
        try:
            result = await _model_service(session).update_provider_mapping(
                mapping_id, ModelMappingProviderUpdate(**data)
            )
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return serialize_model(result)


async def delete_model_provider(mapping_id: int) -> dict[str, Any]:
    """Delete a model-provider mapping by id."""
    ensure_writes_enabled()
    audit("delete_model_provider", mapping_id=mapping_id)
    async with db_session() as session:
        try:
            await _model_service(session).delete_provider_mapping(mapping_id)
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return {"ok": True, "mapping_id": mapping_id}


# ----------------------------- API Keys -----------------------------


async def create_api_key(key_name: str, record_details: bool = True) -> dict[str, Any]:
    """Create an API key. Returns the full key_value ONCE.

    Note: newly created keys are NOT granted MCP admin — that must be done in the
    Web admin UI.
    """
    ensure_writes_enabled()
    audit("create_api_key", key_name=key_name)
    async with db_session() as session:
        service = ApiKeyService(SQLAlchemyApiKeyRepository(session))
        try:
            result = await service.create(
                ApiKeyCreate(key_name=key_name, record_details=record_details)
            )
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    # key_value is intentionally returned in full here (creation-only), so bypass
    # redaction for this one field while still returning the rest normally.
    return {
        "id": result.id,
        "key_name": result.key_name,
        "key_value": result.key_value,
        "is_active": result.is_active,
        "record_details": result.record_details,
        "is_mcp_admin": result.is_mcp_admin,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }


async def update_api_key(key_id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Update an API key (name / active / record_details only).

    SECURITY: any `is_mcp_admin` field in `data` is stripped and ignored — MCP
    admin grant/revoke is Web-admin-only.
    """
    ensure_writes_enabled()
    stripped = {k: v for k, v in data.items() if k != "is_mcp_admin"}
    rejected = "is_mcp_admin" in data
    audit("update_api_key", key_id=key_id, rejected_mcp_admin_change=rejected)
    async with db_session() as session:
        service = ApiKeyService(SQLAlchemyApiKeyRepository(session))
        try:
            result = await service.update(key_id, ApiKeyUpdate(**stripped))
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    out = serialize_model(result)
    if rejected:
        out["_warning"] = (
            "is_mcp_admin cannot be changed via MCP; use the Web admin UI. "
            "The field was ignored."
        )
    return out


async def delete_api_key(key_id: int) -> dict[str, Any]:
    """Delete an API key by id."""
    ensure_writes_enabled()
    audit("delete_api_key", key_id=key_id)
    async with db_session() as session:
        service = ApiKeyService(SQLAlchemyApiKeyRepository(session))
        try:
            await service.delete(key_id)
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return {"ok": True, "key_id": key_id}


# ----------------------------- Requests -----------------------------


async def cancel_request(log_id: int) -> dict[str, Any]:
    """Cancel an in-progress request by its log id."""
    ensure_writes_enabled()
    audit("cancel_request", log_id=log_id)
    async with db_session() as session:
        service = LogService(SQLAlchemyLogRepository(session))
        try:
            await service.cancel(log_id)
        except Exception as exc:  # noqa: BLE001
            return _err(exc)
    return {"ok": True, "log_id": log_id}
