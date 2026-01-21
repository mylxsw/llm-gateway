"""
Model Management API

Provides CRUD endpoints for Model Mappings and Model-Provider Mappings.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import LogServiceDep, ModelServiceDep, require_admin_auth
from app.common.errors import AppError
from app.domain.model import (
    ModelMappingCreate,
    ModelMappingUpdate,
    ModelMappingResponse,
    ModelMappingProviderCreate,
    ModelMappingProviderUpdate,
    ModelMappingProviderResponse,
    ModelExport,
)
from app.domain.log import ModelStats, ModelProviderStats

router = APIRouter(
    prefix="/admin",
    tags=["Admin - Models"],
    dependencies=[Depends(require_admin_auth)],
)


class PaginatedModelResponse(BaseModel):
    """Model Mapping Pagination Response"""
    items: list[ModelMappingResponse]
    total: int
    page: int
    page_size: int


class ModelProviderListResponse(BaseModel):
    """Model-Provider Mapping List Response"""
    items: list[ModelMappingProviderResponse]
    total: int


class ImportModelResponse(BaseModel):
    """Import Model Response"""
    success: int
    skipped: int
    errors: list[str]


# ============ Model Mapping Endpoints ============

@router.get("/models/export", response_model=list[ModelExport])
async def export_models(
    service: ModelServiceDep,
):
    """
    Export all models
    """
    try:
        return await service.export_data()
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post("/models/import", response_model=ImportModelResponse)
async def import_models(
    data: list[ModelExport],
    service: ModelServiceDep,
):
    """
    Import models
    """
    try:
        result = await service.import_data(data)
        return ImportModelResponse(**result)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models", response_model=PaginatedModelResponse)
async def list_models(
    service: ModelServiceDep,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    requested_model: Optional[str] = Query(None, description="Filter by model name"),
    model_type: Optional[str] = Query(None, description="Filter by model type"),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Get Model Mapping List
    """
    try:
        items, total = await service.get_all_mappings(
            is_active=is_active, 
            page=page, 
            page_size=page_size,
            requested_model=requested_model,
            model_type=model_type,
            strategy=strategy
        )
        return PaginatedModelResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models/stats", response_model=list[ModelStats])
async def list_model_stats(
    service: LogServiceDep,
    requested_model: Optional[str] = Query(None, description="Filter by model name"),
):
    """
    Get model stats based on logs for the last 7 days
    """
    try:
        return await service.get_model_stats(requested_model=requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models/provider-stats", response_model=list[ModelProviderStats])
async def list_model_provider_stats(
    service: LogServiceDep,
    requested_model: Optional[str] = Query(None, description="Filter by model name"),
):
    """
    Get model-provider stats based on logs for the last 7 days
    """
    try:
        return await service.get_model_provider_stats(requested_model=requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/models/{requested_model:path}", response_model=ModelMappingResponse)
async def get_model(
    requested_model: str,
    service: ModelServiceDep,
):
    """
    Get single Model Mapping details (including provider configuration)
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
    Create Model Mapping
    """
    try:
        return await service.create_mapping(data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.put("/models/{requested_model:path}", response_model=ModelMappingResponse)
async def update_model(
    requested_model: str,
    data: ModelMappingUpdate,
    service: ModelServiceDep,
):
    """
    Update Model Mapping
    """
    try:
        return await service.update_mapping(requested_model, data)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.delete("/models/{requested_model:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    requested_model: str,
    service: ModelServiceDep,
):
    """
    Delete Model Mapping (Simultaneously deletes associated provider configurations)
    """
    try:
        await service.delete_mapping(requested_model)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


# ============ Model-Provider Mapping Endpoints ============

@router.get("/model-providers", response_model=ModelProviderListResponse)
async def list_model_providers(
    service: ModelServiceDep,
    requested_model: Optional[str] = Query(None, description="Filter by model"),
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """
    Get Model-Provider Mapping List
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
    Create Model-Provider Mapping
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
    Update Model-Provider Mapping
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
    Delete Model-Provider Mapping
    """
    try:
        await service.delete_provider_mapping(mapping_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
