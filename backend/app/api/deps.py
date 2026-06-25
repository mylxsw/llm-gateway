"""
API Dependency Injection Module

Provides dependencies required by FastAPI routers.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.admin_auth import is_admin_auth_enabled, verify_admin_token
from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.db.session import get_db as _get_db
from app.domain.api_key import ApiKeyModel
from app.repositories.sqlalchemy import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyKVStoreRepository,
    SQLAlchemyLogRepository,
    SQLAlchemyModelRepository,
    SQLAlchemyProviderRepository,
)
from app.services import (
    ApiKeyService,
    CostFirstStrategy,
    LogService,
    ModelService,
    PriorityStrategy,
    ProviderService,
    ProxyService,
    RoundRobinStrategy,
)
from app.services.protocol_hooks import ProtocolConversionHooks

# Singleton strategies
_round_robin_strategy = RoundRobinStrategy()
_cost_first_strategy = CostFirstStrategy()
_priority_strategy = PriorityStrategy()


async def get_db():
    """
    Get database session dependency

    Yields:
        AsyncSession: Async database session
    """
    async for session in _get_db():
        yield session


# Database session dependency type
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ============ Repository Dependencies ============


def get_provider_repo(db: DbSession) -> SQLAlchemyProviderRepository:
    """Get Provider Repository"""
    return SQLAlchemyProviderRepository(db)


def get_model_repo(db: DbSession) -> SQLAlchemyModelRepository:
    """Get Model Repository"""
    return SQLAlchemyModelRepository(db)


def get_api_key_repo(db: DbSession) -> SQLAlchemyApiKeyRepository:
    """Get API Key Repository"""
    return SQLAlchemyApiKeyRepository(db)


def get_log_repo(db: DbSession) -> SQLAlchemyLogRepository:
    """Get Log Repository"""
    return SQLAlchemyLogRepository(db)


# ============ Service Dependencies ============


def get_provider_service(db: DbSession) -> ProviderService:
    """Get Provider Service"""
    repo = SQLAlchemyProviderRepository(db)
    return ProviderService(repo)


def get_model_service(db: DbSession) -> ModelService:
    """Get Model Service"""
    model_repo = SQLAlchemyModelRepository(db)
    provider_repo = SQLAlchemyProviderRepository(db)
    return ModelService(model_repo, provider_repo)


def get_api_key_service(db: DbSession) -> ApiKeyService:
    """Get API Key Service"""
    repo = SQLAlchemyApiKeyRepository(db)
    return ApiKeyService(repo)


def get_log_service(db: DbSession) -> LogService:
    """Get Log Service"""
    repo = SQLAlchemyLogRepository(db)
    return LogService(repo)


def _build_protocol_hooks() -> ProtocolConversionHooks:
    """Build protocol hooks with KV access that does not pin a DB connection.

    - Redis mode: a long-lived Redis-backed repo (no DB session).
    - DB mode: a factory + session_factory so each KV op opens a short-lived
      session and releases the pooled connection immediately.
    """
    settings = get_settings()
    if settings.KV_STORE_TYPE == "redis":
        from app.db.redis import get_redis
        from app.repositories.redis import RedisKVStoreRepository

        return ProtocolConversionHooks(kv_repo=RedisKVStoreRepository(get_redis()))
    return ProtocolConversionHooks(
        kv_repo_factory=lambda s: SQLAlchemyKVStoreRepository(s),
        session_factory=AsyncSessionLocal,
    )


def get_proxy_service() -> ProxyService:
    """Get Proxy Service.

    Wired with a session factory and per-repo factories so each DB operation
    uses a short-lived session. This prevents streaming responses from holding
    a pooled connection for the entire upstream stream (see pool-exhaustion fix).
    """
    return ProxyService(
        session_factory=AsyncSessionLocal,
        model_repo_factory=lambda s: SQLAlchemyModelRepository(s),
        provider_repo_factory=lambda s: SQLAlchemyProviderRepository(s),
        log_repo_factory=lambda s: SQLAlchemyLogRepository(s),
        round_robin_strategy=_round_robin_strategy,
        cost_first_strategy=_cost_first_strategy,
        priority_strategy=_priority_strategy,
        protocol_hooks=_build_protocol_hooks(),
    )


# ============ Auth Dependencies ============


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return authorization.strip() or None


async def require_admin_auth(
    authorization: str = Header(None, description="Bearer token"),
    x_admin_token: str = Header(None, description="Admin token", alias="x-admin-token"),
) -> None:
    """
    Admin API Authentication

    Enables authentication when ADMIN_USERNAME and ADMIN_PASSWORD are set, otherwise allows access.
    """
    settings = get_settings()
    if not is_admin_auth_enabled(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD):
        return

    token = x_admin_token or _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_admin_token(
        token=token,
        admin_username=settings.ADMIN_USERNAME or "",
        admin_password=settings.ADMIN_PASSWORD or "",
    )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_api_key(
    db: DbSession,
    authorization: str = Header(None, description="Bearer token"),
    x_api_key: str = Header(
        None, description="Anthropic style API key", alias="x-api-key"
    ),
) -> ApiKeyModel:
    """
    Get current request API Key (Authentication)

    Extracts API Key from Authorization header or x-api-key header and verifies it.
    Prioritizes x-api-key.

    Args:
        db: Database session
        authorization: Authorization header
        x_api_key: x-api-key header

    Returns:
        ApiKeyModel: Verified API Key

    Raises:
        AuthenticationError: Verification failed
    """
    service = get_api_key_service(db)
    token = x_api_key or authorization
    return await service.authenticate(token or "")


# Dependency Type Aliases
ProviderServiceDep = Annotated[ProviderService, Depends(get_provider_service)]
ModelServiceDep = Annotated[ModelService, Depends(get_model_service)]
ApiKeyServiceDep = Annotated[ApiKeyService, Depends(get_api_key_service)]
LogServiceDep = Annotated[LogService, Depends(get_log_service)]
ProxyServiceDep = Annotated[ProxyService, Depends(get_proxy_service)]
CurrentApiKey = Annotated[ApiKeyModel, Depends(get_current_api_key)]
