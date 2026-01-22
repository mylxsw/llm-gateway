"""
Provider Management API

Provides CRUD endpoints for Providers.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import ProviderServiceDep, require_admin_auth
from app.common.errors import AppError
from app.domain.provider import ProviderCreate, ProviderUpdate, ProviderResponse, ProviderExport

router = APIRouter(
    prefix="/admin/providers",
    tags=["Admin - Providers"],
    dependencies=[Depends(require_admin_auth)],
)


class PaginatedProviderResponse(BaseModel):
    """Provider Pagination Response"""
    items: list[ProviderResponse]
    total: int
    page: int
    page_size: int


class ImportProviderResponse(BaseModel):
    """Import Provider Response"""
    success: int
    skipped: int


@router.get("/export", response_model=list[ProviderExport])
async def export_providers(
    service: ProviderServiceDep,
):
    """
    Export all providers
    """
    try:
        return await service.export_data()
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.post("/import", response_model=ImportProviderResponse)
async def import_providers(
    data: list[ProviderCreate],
    service: ProviderServiceDep,
):
    """
    Import providers
    """
    try:
        result = await service.import_data(data)
        return ImportProviderResponse(**result)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("", response_model=PaginatedProviderResponse)
async def list_providers(
    service: ProviderServiceDep,
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    name: Optional[str] = Query(None, description="Filter by name"),
    protocol: Optional[str] = Query(None, description="Filter by protocol"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=1000, description="Items per page"),
):
    """
    Get Provider List
    
    Supports pagination and filtering.
    """
    try:
        items, total = await service.get_all(
            is_active=is_active, 
            page=page, 
            page_size=page_size,
            name=name,
            protocol=protocol
        )
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
    Get single Provider details
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
    Create Provider
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
    Update Provider
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
    Delete Provider
    
    Returns error if the provider is referenced by model mappings.
    """
    try:
        await service.delete(provider_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)