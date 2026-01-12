"""
登录鉴权 API

当同时设置 ADMIN_USERNAME 和 ADMIN_PASSWORD 时启用后台登录鉴权：
- POST /auth/login：用户名密码换取 token
- GET /auth/status：查看是否启用与是否已登录
"""

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.common.admin_auth import create_admin_token, is_admin_auth_enabled, verify_admin_token
from app.config import get_settings


router = APIRouter(prefix="/auth", tags=["Auth"])


class AuthStatusResponse(BaseModel):
    enabled: bool
    authenticated: bool


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return authorization.strip() or None


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    authorization: str = Header(None, description="Bearer token"),
    x_admin_token: str = Header(None, description="Admin token", alias="x-admin-token"),
):
    settings = get_settings()
    enabled = is_admin_auth_enabled(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
    if not enabled:
        return AuthStatusResponse(enabled=False, authenticated=True)

    token = x_admin_token or _extract_bearer_token(authorization)
    authenticated = bool(
        token
        and verify_admin_token(
            token=token,
            admin_username=settings.ADMIN_USERNAME or "",
            admin_password=settings.ADMIN_PASSWORD or "",
        )
    )
    return AuthStatusResponse(enabled=True, authenticated=authenticated)


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest):
    settings = get_settings()
    if not is_admin_auth_enabled(settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin authentication is not enabled",
        )

    if data.username != settings.ADMIN_USERNAME or data.password != settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_admin_token(
        admin_username=settings.ADMIN_USERNAME or "",
        admin_password=settings.ADMIN_PASSWORD or "",
        ttl_seconds=settings.ADMIN_TOKEN_TTL_SECONDS,
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.ADMIN_TOKEN_TTL_SECONDS,
    )


@router.post("/logout")
async def logout():
    return {"ok": True}

