"""
供应商管理 API

提供供应商的 CRUD 接口。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import ProviderServiceDep, require_admin_auth
from app.common.errors import AppError
from app.domain.provider import ProviderCreate, ProviderUpdate, ProviderResponse

router = APIRouter(
    prefix="/admin/providers",
    tags=["Admin - Providers"],
    dependencies=[Depends(require_admin_auth)],
)


class PaginatedProviderResponse(BaseModel):
    """供应商分页响应"""
    items: list[ProviderResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedProviderResponse)
async def list_providers(
    service: ProviderServiceDep,
    is_active: Optional[bool] = Query(None, description="过滤激活状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """
    获取供应商列表
    
    支持分页和激活状态过滤。
    """
    try:
        items, total = await service.get_all(is_active, page, page_size)
        return PaginatedProviderResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: int,
    service: ProviderServiceDep,
):
    """
    获取单个供应商详情
    """
    try:
        return await service.get_by_id(provider_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: ProviderCreate,
    service: ProviderServiceDep,
):
    """
    创建供应商
    """
    try:
        return await service.create(data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: int,
    data: ProviderUpdate,
    service: ProviderServiceDep,
):
    """
    更新供应商
    """
    try:
        return await service.update(provider_id, data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: int,
    service: ProviderServiceDep,
):
    """
    删除供应商
    
    如果供应商被模型映射引用，将返回错误。
    """
    try:
        await service.delete(provider_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
