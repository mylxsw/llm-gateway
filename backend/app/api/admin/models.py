"""
模型管理 API

提供模型映射和模型-供应商映射的 CRUD 接口。
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import ModelServiceDep, require_admin_auth
from app.common.errors import AppError
from app.domain.model import (
    ModelMappingCreate,
    ModelMappingUpdate,
    ModelMappingResponse,
    ModelMappingProviderCreate,
    ModelMappingProviderUpdate,
    ModelMappingProviderResponse,
)

router = APIRouter(
    prefix="/admin",
    tags=["Admin - Models"],
    dependencies=[Depends(require_admin_auth)],
)


class PaginatedModelResponse(BaseModel):
    """模型映射分页响应"""
    items: list[ModelMappingResponse]
    total: int
    page: int
    page_size: int


class ModelProviderListResponse(BaseModel):
    """模型-供应商映射列表响应"""
    items: list[ModelMappingProviderResponse]
    total: int


# ============ 模型映射接口 ============

@router.get("/models", response_model=PaginatedModelResponse)
async def list_models(
    service: ModelServiceDep,
    is_active: Optional[bool] = Query(None, description="过滤激活状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """
    获取模型映射列表
    """
    try:
        items, total = await service.get_all_mappings(is_active, page, page_size)
        return PaginatedModelResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models/{requested_model}", response_model=ModelMappingResponse)
async def get_model(
    requested_model: str,
    service: ModelServiceDep,
):
    """
    获取单个模型映射详情（含供应商配置）
    """
    try:
        return await service.get_mapping(requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post("/models", response_model=ModelMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    data: ModelMappingCreate,
    service: ModelServiceDep,
):
    """
    创建模型映射
    """
    try:
        return await service.create_mapping(data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.put("/models/{requested_model}", response_model=ModelMappingResponse)
async def update_model(
    requested_model: str,
    data: ModelMappingUpdate,
    service: ModelServiceDep,
):
    """
    更新模型映射
    """
    try:
        return await service.update_mapping(requested_model, data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.delete("/models/{requested_model}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    requested_model: str,
    service: ModelServiceDep,
):
    """
    删除模型映射（同时删除关联的供应商配置）
    """
    try:
        await service.delete_mapping(requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


# ============ 模型-供应商映射接口 ============

@router.get("/model-providers", response_model=ModelProviderListResponse)
async def list_model_providers(
    service: ModelServiceDep,
    requested_model: Optional[str] = Query(None, description="按模型过滤"),
    provider_id: Optional[int] = Query(None, description="按供应商过滤"),
    is_active: Optional[bool] = Query(None, description="过滤激活状态"),
):
    """
    获取模型-供应商映射列表
    """
    try:
        items = await service.get_provider_mappings(
            requested_model, provider_id, is_active
        )
        return ModelProviderListResponse(
            items=items,
            total=len(items),
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post(
    "/model-providers",
    response_model=ModelMappingProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_model_provider(
    data: ModelMappingProviderCreate,
    service: ModelServiceDep,
):
    """
    创建模型-供应商映射
    """
    try:
        return await service.create_provider_mapping(data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.put("/model-providers/{mapping_id}", response_model=ModelMappingProviderResponse)
async def update_model_provider(
    mapping_id: int,
    data: ModelMappingProviderUpdate,
    service: ModelServiceDep,
):
    """
    更新模型-供应商映射
    """
    try:
        return await service.update_provider_mapping(mapping_id, data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.delete("/model-providers/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_provider(
    mapping_id: int,
    service: ModelServiceDep,
):
    """
    删除模型-供应商映射
    """
    try:
        await service.delete_provider_mapping(mapping_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
