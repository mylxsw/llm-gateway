"""
API 依赖注入模块

提供 FastAPI 路由所需的依赖项。
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.common.admin_auth import is_admin_auth_enabled, verify_admin_token
from app.db.session import get_db as _get_db
from app.domain.api_key import ApiKeyModel
from app.repositories.sqlalchemy import (
    SQLAlchemyProviderRepository,
    SQLAlchemyModelRepository,
    SQLAlchemyApiKeyRepository,
    SQLAlchemyLogRepository,
)
from app.services import (
    ProviderService,
    ModelService,
    ApiKeyService,
    LogService,
    ProxyService,
    RoundRobinStrategy,
)


async def get_db():
    """
    获取数据库会话依赖
    
    Yields:
        AsyncSession: 异步数据库会话
    """
    async for session in _get_db():
        yield session


# 数据库会话依赖类型
DbSession = Annotated[AsyncSession, Depends(get_db)]


# ============ 全局单例 ============

# 全局策略实例，确保轮询状态跨请求保持
_global_strategy = RoundRobinStrategy()


# ============ Repository 依赖 ============

def get_provider_repo(db: DbSession) -> SQLAlchemyProviderRepository:
    """获取供应商 Repository"""
    return SQLAlchemyProviderRepository(db)


def get_model_repo(db: DbSession) -> SQLAlchemyModelRepository:
    """获取模型 Repository"""
    return SQLAlchemyModelRepository(db)


def get_api_key_repo(db: DbSession) -> SQLAlchemyApiKeyRepository:
    """获取 API Key Repository"""
    return SQLAlchemyApiKeyRepository(db)


def get_log_repo(db: DbSession) -> SQLAlchemyLogRepository:
    """获取日志 Repository"""
    return SQLAlchemyLogRepository(db)


# ============ Service 依赖 ============

def get_provider_service(db: DbSession) -> ProviderService:
    """获取供应商服务"""
    repo = SQLAlchemyProviderRepository(db)
    return ProviderService(repo)


def get_model_service(db: DbSession) -> ModelService:
    """获取模型服务"""
    model_repo = SQLAlchemyModelRepository(db)
    provider_repo = SQLAlchemyProviderRepository(db)
    return ModelService(model_repo, provider_repo)


def get_api_key_service(db: DbSession) -> ApiKeyService:
    """获取 API Key 服务"""
    repo = SQLAlchemyApiKeyRepository(db)
    return ApiKeyService(repo)


def get_log_service(db: DbSession) -> LogService:
    """获取日志服务"""
    repo = SQLAlchemyLogRepository(db)
    return LogService(repo)


def get_proxy_service(db: DbSession) -> ProxyService:
    """获取代理服务"""
    model_repo = SQLAlchemyModelRepository(db)
    provider_repo = SQLAlchemyProviderRepository(db)
    log_repo = SQLAlchemyLogRepository(db)
    return ProxyService(model_repo, provider_repo, log_repo, strategy=_global_strategy)


# ============ 鉴权依赖 ============

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
    后台管理接口登录鉴权

    当设置了 ADMIN_USERNAME 与 ADMIN_PASSWORD 时启用鉴权，否则直接放行。
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
    x_api_key: str = Header(None, description="Anthropic style API key", alias="x-api-key"),
) -> ApiKeyModel:
    """
    获取当前请求的 API Key（鉴权）
    
    从 Authorization 头或 x-api-key 头中提取 API Key 并验证。
    优先使用 x-api-key。
    
    Args:
        db: 数据库会话
        authorization: Authorization 头
        x_api_key: x-api-key 头
    
    Returns:
        ApiKeyModel: 验证通过的 API Key
    
    Raises:
        AuthenticationError: 验证失败
    """
    service = get_api_key_service(db)
    token = x_api_key or authorization
    return await service.authenticate(token or "")


# 依赖类型别名
ProviderServiceDep = Annotated[ProviderService, Depends(get_provider_service)]
ModelServiceDep = Annotated[ModelService, Depends(get_model_service)]
ApiKeyServiceDep = Annotated[ApiKeyService, Depends(get_api_key_service)]
LogServiceDep = Annotated[LogService, Depends(get_log_service)]
ProxyServiceDep = Annotated[ProxyService, Depends(get_proxy_service)]
CurrentApiKey = Annotated[ApiKeyModel, Depends(get_current_api_key)]
