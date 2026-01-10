"""
日志 Repository SQLAlchemy 实现

提供请求日志的具体数据库操作实现。
"""

from typing import Optional

from sqlalchemy import func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RequestLog as RequestLogORM
from app.domain.log import RequestLogModel, RequestLogCreate, RequestLogQuery
from app.repositories.log_repo import LogRepository


class SQLAlchemyLogRepository(LogRepository):
    """
    日志 Repository SQLAlchemy 实现
    
    使用 SQLAlchemy ORM 实现请求日志的数据库操作。
    """
    
    def __init__(self, session: AsyncSession):
        """
        初始化 Repository
        
        Args:
            session: 异步数据库会话
        """
        self.session = session
    
    def _to_domain(self, entity: RequestLogORM) -> RequestLogModel:
        """将 ORM 实体转换为领域模型"""
        return RequestLogModel(
            id=entity.id,
            request_time=entity.request_time,
            api_key_id=entity.api_key_id,
            api_key_name=entity.api_key_name,
            requested_model=entity.requested_model,
            target_model=entity.target_model,
            provider_id=entity.provider_id,
            provider_name=entity.provider_name,
            retry_count=entity.retry_count,
            first_byte_delay_ms=entity.first_byte_delay_ms,
            total_time_ms=entity.total_time_ms,
            input_tokens=entity.input_tokens,
            output_tokens=entity.output_tokens,
            request_headers=entity.request_headers,
            request_body=entity.request_body,
            response_status=entity.response_status,
            response_body=entity.response_body,
            error_info=entity.error_info,
            matched_provider_count=entity.matched_provider_count,
            trace_id=entity.trace_id,
        )
    
    async def create(self, data: RequestLogCreate) -> RequestLogModel:
        """创建请求日志"""
        entity = RequestLogORM(
            request_time=data.request_time,
            api_key_id=data.api_key_id,
            api_key_name=data.api_key_name,
            requested_model=data.requested_model,
            target_model=data.target_model,
            provider_id=data.provider_id,
            provider_name=data.provider_name,
            retry_count=data.retry_count,
            matched_provider_count=data.matched_provider_count,
            first_byte_delay_ms=data.first_byte_delay_ms,
            total_time_ms=data.total_time_ms,
            input_tokens=data.input_tokens,
            output_tokens=data.output_tokens,
            request_headers=data.request_headers,
            request_body=data.request_body,
            response_status=data.response_status,
            response_body=data.response_body,
            error_info=data.error_info,
            trace_id=data.trace_id,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def get_by_id(self, id: int) -> Optional[RequestLogModel]:
        """根据 ID 获取日志"""
        result = await self.session.execute(
            select(RequestLogORM).where(RequestLogORM.id == id)
        )
        entity = result.scalar_one_or_none()
        return self._to_domain(entity) if entity else None
    
    async def query(self, query: RequestLogQuery) -> tuple[list[RequestLogModel], int]:
        """
        查询日志列表
        
        支持多条件过滤、分页和排序。
        """
        # 构建基础查询
        stmt = select(RequestLogORM)
        count_stmt = select(func.count()).select_from(RequestLogORM)
        
        # 构建过滤条件列表
        conditions = []
        
        # 时间范围过滤
        if query.start_time:
            conditions.append(RequestLogORM.request_time >= query.start_time)
        if query.end_time:
            conditions.append(RequestLogORM.request_time <= query.end_time)
        
        # 模型过滤（模糊匹配）
        if query.requested_model:
            conditions.append(
                RequestLogORM.requested_model.ilike(f"%{query.requested_model}%")
            )
        if query.target_model:
            conditions.append(
                RequestLogORM.target_model.ilike(f"%{query.target_model}%")
            )
        
        # 供应商过滤
        if query.provider_id:
            conditions.append(RequestLogORM.provider_id == query.provider_id)
        
        # 状态码过滤
        if query.status_min is not None:
            conditions.append(RequestLogORM.response_status >= query.status_min)
        if query.status_max is not None:
            conditions.append(RequestLogORM.response_status <= query.status_max)
        
        # 是否有错误
        if query.has_error is not None:
            if query.has_error:
                conditions.append(
                    or_(
                        RequestLogORM.error_info.isnot(None),
                        RequestLogORM.error_info != "",
                    )
                )
            else:
                conditions.append(
                    or_(
                        RequestLogORM.error_info.is_(None),
                        RequestLogORM.error_info == "",
                    )
                )
        
        # API Key 过滤
        if query.api_key_id:
            conditions.append(RequestLogORM.api_key_id == query.api_key_id)
        if query.api_key_name:
            conditions.append(
                RequestLogORM.api_key_name.ilike(f"%{query.api_key_name}%")
            )
        
        # 重试次数过滤
        if query.retry_count_min is not None:
            conditions.append(RequestLogORM.retry_count >= query.retry_count_min)
        if query.retry_count_max is not None:
            conditions.append(RequestLogORM.retry_count <= query.retry_count_max)
        
        # Token 过滤
        if query.input_tokens_min is not None:
            conditions.append(RequestLogORM.input_tokens >= query.input_tokens_min)
        if query.input_tokens_max is not None:
            conditions.append(RequestLogORM.input_tokens <= query.input_tokens_max)
        
        # 耗时过滤
        if query.total_time_min is not None:
            conditions.append(RequestLogORM.total_time_ms >= query.total_time_min)
        if query.total_time_max is not None:
            conditions.append(RequestLogORM.total_time_ms <= query.total_time_max)
        
        # 应用过滤条件
        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))
        
        # 获取总数
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0
        
        # 排序
        sort_column = getattr(RequestLogORM, query.sort_by, RequestLogORM.request_time)
        if query.sort_order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())
        
        # 分页
        stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)
        
        # 执行查询
        result = await self.session.execute(stmt)
        entities = result.scalars().all()
        
        return [self._to_domain(e) for e in entities], total
