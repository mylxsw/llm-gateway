"""
日志查询 API

提供请求日志的查询接口。
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import LogServiceDep
from app.common.errors import AppError
from app.domain.log import RequestLogQuery, RequestLogResponse, RequestLogModel

router = APIRouter(prefix="/admin/logs", tags=["Admin - Logs"])


class PaginatedLogResponse(BaseModel):
    """日志分页响应"""
    items: list[RequestLogResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedLogResponse)
async def list_logs(
    service: LogServiceDep,
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    requested_model: Optional[str] = Query(None, description="请求模型（模糊匹配）"),
    target_model: Optional[str] = Query(None, description="目标模型（模糊匹配）"),
    provider_id: Optional[int] = Query(None, description="供应商 ID"),
    status_min: Optional[int] = Query(None, description="最小状态码"),
    status_max: Optional[int] = Query(None, description="最大状态码"),
    has_error: Optional[bool] = Query(None, description="是否有错误"),
    api_key_id: Optional[int] = Query(None, description="API Key ID"),
    api_key_name: Optional[str] = Query(None, description="API Key 名称"),
    retry_count_min: Optional[int] = Query(None, description="最小重试次数"),
    retry_count_max: Optional[int] = Query(None, description="最大重试次数"),
    input_tokens_min: Optional[int] = Query(None, description="最小输入 Token"),
    input_tokens_max: Optional[int] = Query(None, description="最大输入 Token"),
    total_time_min: Optional[int] = Query(None, description="最小耗时（毫秒）"),
    total_time_max: Optional[int] = Query(None, description="最大耗时（毫秒）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sort_by: str = Query("request_time", description="排序字段"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="排序方向"),
):
    """
    查询请求日志列表
    
    支持多条件过滤、分页和排序。
    """
    try:
        query = RequestLogQuery(
            start_time=start_time,
            end_time=end_time,
            requested_model=requested_model,
            target_model=target_model,
            provider_id=provider_id,
            status_min=status_min,
            status_max=status_max,
            has_error=has_error,
            api_key_id=api_key_id,
            api_key_name=api_key_name,
            retry_count_min=retry_count_min,
            retry_count_max=retry_count_max,
            input_tokens_min=input_tokens_min,
            input_tokens_max=input_tokens_max,
            total_time_min=total_time_min,
            total_time_max=total_time_max,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        
        items, total = await service.query(query)
        return PaginatedLogResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)


@router.get("/{log_id}", response_model=RequestLogModel)
async def get_log(
    log_id: int,
    service: LogServiceDep,
):
    """
    获取日志详情
    
    包含完整的请求/响应信息（authorization 已脱敏）。
    """
    try:
        return await service.get_by_id(log_id)
    except AppError as e:
        return JSONResponse(content=e.to_dict(), status_code=e.status_code)
