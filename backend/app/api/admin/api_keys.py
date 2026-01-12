"""
API Key 管理 API

提供 API Key 的 CRUD 接口。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import ApiKeyServiceDep, require_admin_auth
from app.common.errors import AppError
from app.domain.api_key import ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse, ApiKeyCreateResponse

router = APIRouter(
    prefix="/admin/api-keys",
    tags=["Admin - API Keys"],
    dependencies=[Depends(require_admin_auth)],
)


class PaginatedApiKeyResponse(BaseModel):
    """API Key 分页响应"""
    items: list[ApiKeyResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedApiKeyResponse)
async def list_api_keys(
    service: ApiKeyServiceDep,
    is_active: Optional[bool] = Query(None, description="过滤激活状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """
    获取 API Key 列表
    
    key_value 将脱敏显示。
    """
    try:
        items, total = await service.get_all(is_active, page, page_size)
        return PaginatedApiKeyResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: int,
    service: ApiKeyServiceDep,
):
    """
    获取单个 API Key 详情
    
    key_value 将脱敏显示。
    """
    try:
        return await service.get_by_id(key_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: ApiKeyCreate,
    service: ApiKeyServiceDep,
):
    """
    创建 API Key
    
    key_value 由系统自动生成，仅在创建时完整返回。
    请妥善保存 key_value，之后将无法再次查看完整值。
    """
    try:
        return await service.create(data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.put("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: int,
    data: ApiKeyUpdate,
    service: ApiKeyServiceDep,
):
    """
    更新 API Key
    
    可更新名称和激活状态。
    """
    try:
        return await service.update(key_id, data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    service: ApiKeyServiceDep,
):
    """
    删除 API Key
    """
    try:
        await service.delete(key_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
