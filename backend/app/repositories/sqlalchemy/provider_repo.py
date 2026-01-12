"""
供应商 Repository SQLAlchemy 实现

提供供应商数据的具体数据库操作实现。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceProvider, ModelMappingProvider as ModelMappingProviderORM
from app.domain.provider import Provider, ProviderCreate, ProviderUpdate
from app.repositories.provider_repo import ProviderRepository


class SQLAlchemyProviderRepository(ProviderRepository):
    """
    供应商 Repository SQLAlchemy 实现
    
    使用 SQLAlchemy ORM 实现供应商的数据库操作。
    """
    
    def __init__(self, session: AsyncSession):
        """
        初始化 Repository
        
        Args:
            session: 异步数据库会话
        """
        self.session = session
    
    def _to_domain(self, entity: ServiceProvider) -> Provider:
        """
        将 ORM 实体转换为领域模型
        
        Args:
            entity: ORM 实体
        
        Returns:
            Provider: 领域模型
        """
        return Provider(
            id=entity.id,
            name=entity.name,
            base_url=entity.base_url,
            protocol=entity.protocol,
            api_type=entity.api_type,
            api_key=entity.api_key,
            extra_headers=entity.extra_headers,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
    
    async def create(self, data: ProviderCreate) -> Provider:
        """创建供应商"""
        entity = ServiceProvider(
            name=data.name,
            base_url=data.base_url,
            protocol=data.protocol,
            api_type=data.api_type,
            api_key=data.api_key,
            extra_headers=data.extra_headers,
            is_active=data.is_active,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def get_by_id(self, id: int) -> Optional[Provider]:
        """根据 ID 获取供应商"""
        result = await self.session.execute(
            select(ServiceProvider).where(ServiceProvider.id == id)
        )
        entity = result.scalar_one_or_none()
        return self._to_domain(entity) if entity else None
    
    async def get_by_name(self, name: str) -> Optional[Provider]:
        """根据名称获取供应商"""
        result = await self.session.execute(
            select(ServiceProvider).where(ServiceProvider.name == name)
        )
        entity = result.scalar_one_or_none()
        return self._to_domain(entity) if entity else None
    
    async def get_all(
        self,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Provider], int]:
        """获取供应商列表"""
        # 构建查询条件
        query = select(ServiceProvider)
        count_query = select(func.count()).select_from(ServiceProvider)
        
        if is_active is not None:
            query = query.where(ServiceProvider.is_active == is_active)
            count_query = count_query.where(ServiceProvider.is_active == is_active)
        
        # 获取总数
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # 分页查询
        query = query.order_by(ServiceProvider.id.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.session.execute(query)
        entities = result.scalars().all()
        
        return [self._to_domain(e) for e in entities], total
    
    async def update(self, id: int, data: ProviderUpdate) -> Optional[Provider]:
        """更新供应商"""
        result = await self.session.execute(
            select(ServiceProvider).where(ServiceProvider.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return None
        
        # 更新非空字段
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(entity, key, value)
        
        entity.updated_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def delete(self, id: int) -> bool:
        """删除供应商"""
        result = await self.session.execute(
            select(ServiceProvider).where(ServiceProvider.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return False
        
        await self.session.delete(entity)
        await self.session.commit()
        return True
    
    async def has_model_mappings(self, id: int) -> bool:
        """检查供应商是否有关联的模型映射"""
        result = await self.session.execute(
            select(func.count())
            .select_from(ModelMappingProviderORM)
            .where(ModelMappingProviderORM.provider_id == id)
        )
        count = result.scalar() or 0
        return count > 0
