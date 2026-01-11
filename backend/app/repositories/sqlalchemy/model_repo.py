"""
模型 Repository SQLAlchemy 实现

提供模型映射和模型-供应商映射的具体数据库操作实现。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    ModelMapping as ModelMappingORM,
    ModelMappingProvider as ModelMappingProviderORM,
    ServiceProvider,
)
from app.domain.model import (
    ModelMapping,
    ModelMappingCreate,
    ModelMappingUpdate,
    ModelMappingProvider,
    ModelMappingProviderCreate,
    ModelMappingProviderUpdate,
    ModelMappingProviderResponse,
)
from app.repositories.model_repo import ModelRepository


class SQLAlchemyModelRepository(ModelRepository):
    """
    模型 Repository SQLAlchemy 实现
    
    使用 SQLAlchemy ORM 实现模型映射的数据库操作。
    """
    
    def __init__(self, session: AsyncSession):
        """
        初始化 Repository
        
        Args:
            session: 异步数据库会话
        """
        self.session = session
    
    def _mapping_to_domain(self, entity: ModelMappingORM) -> ModelMapping:
        """将模型映射 ORM 实体转换为领域模型"""
        return ModelMapping(
            requested_model=entity.requested_model,
            strategy=entity.strategy,
            matching_rules=entity.matching_rules,
            capabilities=entity.capabilities,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
    
    def _provider_mapping_to_domain(
        self,
        entity: ModelMappingProviderORM,
        provider_name: str = "",
        provider_protocol: str | None = None,
    ) -> ModelMappingProviderResponse:
        """将模型-供应商映射 ORM 实体转换为领域模型"""
        return ModelMappingProviderResponse(
            id=entity.id,
            requested_model=entity.requested_model,
            provider_id=entity.provider_id,
            provider_name=provider_name,
            provider_protocol=provider_protocol,
            target_model_name=entity.target_model_name,
            provider_rules=entity.provider_rules,
            priority=entity.priority,
            weight=entity.weight,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
    
    # ============ 模型映射操作 ============
    
    async def create_mapping(self, data: ModelMappingCreate) -> ModelMapping:
        """创建模型映射"""
        entity = ModelMappingORM(
            requested_model=data.requested_model,
            strategy=data.strategy,
            matching_rules=data.matching_rules,
            capabilities=data.capabilities,
            is_active=data.is_active,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self._mapping_to_domain(entity)
    
    async def get_mapping(self, requested_model: str) -> Optional[ModelMapping]:
        """根据请求模型名获取模型映射"""
        result = await self.session.execute(
            select(ModelMappingORM).where(
                ModelMappingORM.requested_model == requested_model
            )
        )
        entity = result.scalar_one_or_none()
        return self._mapping_to_domain(entity) if entity else None
    
    async def get_all_mappings(
        self,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ModelMapping], int]:
        """获取模型映射列表"""
        query = select(ModelMappingORM)
        count_query = select(func.count()).select_from(ModelMappingORM)
        
        if is_active is not None:
            query = query.where(ModelMappingORM.is_active == is_active)
            count_query = count_query.where(ModelMappingORM.is_active == is_active)
        
        # 获取总数
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页查询
        query = query.order_by(ModelMappingORM.requested_model)
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.session.execute(query)
        entities = result.scalars().all()
        
        return [self._mapping_to_domain(e) for e in entities], total
    
    async def update_mapping(
        self, requested_model: str, data: ModelMappingUpdate
    ) -> Optional[ModelMapping]:
        """更新模型映射"""
        result = await self.session.execute(
            select(ModelMappingORM).where(
                ModelMappingORM.requested_model == requested_model
            )
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(entity, key, value)
        
        entity.updated_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(entity)
        return self._mapping_to_domain(entity)
    
    async def delete_mapping(self, requested_model: str) -> bool:
        """删除模型映射（级联删除关联的供应商映射）"""
        result = await self.session.execute(
            select(ModelMappingORM).where(
                ModelMappingORM.requested_model == requested_model
            )
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return False
        
        await self.session.delete(entity)
        await self.session.commit()
        return True
    
    # ============ 模型-供应商映射操作 ============
    
    async def create_provider_mapping(
        self, data: ModelMappingProviderCreate
    ) -> ModelMappingProvider:
        """创建模型-供应商映射"""
        entity = ModelMappingProviderORM(
            requested_model=data.requested_model,
            provider_id=data.provider_id,
            target_model_name=data.target_model_name,
            provider_rules=data.provider_rules,
            priority=data.priority,
            weight=data.weight,
            is_active=data.is_active,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        
        # 获取供应商名称
        provider_result = await self.session.execute(
            select(ServiceProvider).where(ServiceProvider.id == entity.provider_id)
        )
        provider = provider_result.scalar_one_or_none()
        provider_name = provider.name if provider else ""
        provider_protocol = provider.protocol if provider else None
        
        return self._provider_mapping_to_domain(entity, provider_name, provider_protocol)
    
    async def get_provider_mapping(self, id: int) -> Optional[ModelMappingProvider]:
        """根据 ID 获取模型-供应商映射"""
        result = await self.session.execute(
            select(ModelMappingProviderORM)
            .options(selectinload(ModelMappingProviderORM.provider))
            .where(ModelMappingProviderORM.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return None
        
        provider_name = entity.provider.name if entity.provider else ""
        provider_protocol = entity.provider.protocol if entity.provider else None
        return self._provider_mapping_to_domain(entity, provider_name, provider_protocol)
    
    async def get_provider_mappings(
        self,
        requested_model: Optional[str] = None,
        provider_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> list[ModelMappingProvider]:
        """获取模型-供应商映射列表"""
        query = select(ModelMappingProviderORM).options(
            selectinload(ModelMappingProviderORM.provider)
        )
        
        if requested_model is not None:
            query = query.where(
                ModelMappingProviderORM.requested_model == requested_model
            )
        if provider_id is not None:
            query = query.where(ModelMappingProviderORM.provider_id == provider_id)
        if is_active is not None:
            query = query.where(ModelMappingProviderORM.is_active == is_active)
        
        # 按优先级排序
        query = query.order_by(
            ModelMappingProviderORM.priority,
            ModelMappingProviderORM.id,
        )
        
        result = await self.session.execute(query)
        entities = result.scalars().all()
        
        return [
            self._provider_mapping_to_domain(
                e,
                e.provider.name if e.provider else "",
                e.provider.protocol if e.provider else None,
            )
            for e in entities
        ]
    
    async def update_provider_mapping(
        self, id: int, data: ModelMappingProviderUpdate
    ) -> Optional[ModelMappingProvider]:
        """更新模型-供应商映射"""
        result = await self.session.execute(
            select(ModelMappingProviderORM)
            .options(selectinload(ModelMappingProviderORM.provider))
            .where(ModelMappingProviderORM.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(entity, key, value)
        
        entity.updated_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(entity)
        
        provider_name = entity.provider.name if entity.provider else ""
        provider_protocol = entity.provider.protocol if entity.provider else None
        return self._provider_mapping_to_domain(entity, provider_name, provider_protocol)
    
    async def delete_provider_mapping(self, id: int) -> bool:
        """删除模型-供应商映射"""
        result = await self.session.execute(
            select(ModelMappingProviderORM).where(ModelMappingProviderORM.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return False
        
        await self.session.delete(entity)
        await self.session.commit()
        return True
    
    async def get_provider_count(self, requested_model: str) -> int:
        """获取模型关联的供应商数量"""
        result = await self.session.execute(
            select(func.count())
            .select_from(ModelMappingProviderORM)
            .where(ModelMappingProviderORM.requested_model == requested_model)
        )
        return result.scalar() or 0
