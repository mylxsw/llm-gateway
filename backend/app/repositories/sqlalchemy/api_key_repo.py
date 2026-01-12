"""
API Key Repository SQLAlchemy Implementation

Provides concrete database operation implementation for API Keys.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApiKey as ApiKeyORM
from app.domain.api_key import ApiKeyModel, ApiKeyCreate, ApiKeyUpdate
from app.repositories.api_key_repo import ApiKeyRepository


class SQLAlchemyApiKeyRepository(ApiKeyRepository):
    """
    API Key Repository SQLAlchemy Implementation
    
    Uses SQLAlchemy ORM to implement database operations for API Keys.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Repository
        
        Args:
            session: Async database session
        """
        self.session = session
    
    def _to_domain(self, entity: ApiKeyORM) -> ApiKeyModel:
        """Convert ORM entity to domain model"""
        return ApiKeyModel(
            id=entity.id,
            key_name=entity.key_name,
            key_value=entity.key_value,
            is_active=entity.is_active,
            created_at=entity.created_at,
            last_used_at=entity.last_used_at,
        )
    
    async def create(self, data: ApiKeyCreate, key_value: str) -> ApiKeyModel:
        """Create API Key"""
        entity = ApiKeyORM(
            key_name=data.key_name,
            key_value=key_value,
            is_active=True,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def get_by_id(self, id: int) -> Optional[ApiKeyModel]:
        """Get API Key by ID"""
        result = await self.session.execute(
            select(ApiKeyORM).where(ApiKeyORM.id == id)
        )
        entity = result.scalar_one_or_none()
        return self._to_domain(entity) if entity else None
    
    async def get_by_key_value(self, key_value: str) -> Optional[ApiKeyModel]:
        """Get API Key by key value (for authentication)"""
        result = await self.session.execute(
            select(ApiKeyORM).where(ApiKeyORM.key_value == key_value)
        )
        entity = result.scalar_one_or_none()
        return self._to_domain(entity) if entity else None
    
    async def get_by_name(self, key_name: str) -> Optional[ApiKeyModel]:
        """Get API Key by name"""
        result = await self.session.execute(
            select(ApiKeyORM).where(ApiKeyORM.key_name == key_name)
        )
        entity = result.scalar_one_or_none()
        return self._to_domain(entity) if entity else None
    
    async def get_all(
        self,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ApiKeyModel], int]:
        """Get API Key list"""
        query = select(ApiKeyORM)
        count_query = select(func.count()).select_from(ApiKeyORM)
        
        if is_active is not None:
            query = query.where(ApiKeyORM.is_active == is_active)
            count_query = count_query.where(ApiKeyORM.is_active == is_active)
        
        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Pagination
        query = query.order_by(ApiKeyORM.id.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.session.execute(query)
        entities = result.scalars().all()
        
        return [self._to_domain(e) for e in entities], total
    
    async def update(self, id: int, data: ApiKeyUpdate) -> Optional[ApiKeyModel]:
        """Update API Key"""
        result = await self.session.execute(
            select(ApiKeyORM).where(ApiKeyORM.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(entity, key, value)
        
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def update_last_used(self, id: int, last_used_at: datetime) -> None:
        """Update API Key's last used time"""
        result = await self.session.execute(
            select(ApiKeyORM).where(ApiKeyORM.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if entity:
            entity.last_used_at = last_used_at
            await self.session.commit()
    
    async def delete(self, id: int) -> bool:
        """Delete API Key"""
        result = await self.session.execute(
            select(ApiKeyORM).where(ApiKeyORM.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return False
        
        await self.session.delete(entity)
        await self.session.commit()
        return True