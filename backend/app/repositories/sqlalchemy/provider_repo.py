"""
Provider Repository SQLAlchemy Implementation

Provides concrete database operation implementation for Provider data.
"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import ensure_utc, to_utc_naive, utc_now
from app.db.models import ServiceProvider, ModelMappingProvider as ModelMappingProviderORM
from app.domain.provider import Provider, ProviderCreate, ProviderUpdate
from app.repositories.provider_repo import ProviderRepository


class SQLAlchemyProviderRepository(ProviderRepository):
    """
    Provider Repository SQLAlchemy Implementation
    
    Uses SQLAlchemy ORM to implement database operations for Providers.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Repository
        
        Args:
            session: Async database session
        """
        self.session = session
    
    def _to_domain(self, entity: ServiceProvider) -> Provider:
        """
        Convert ORM entity to domain model
        
        Args:
            entity: ORM entity
        
        Returns:
            Provider: Domain model
        """
        return Provider(
            id=entity.id,
            name=entity.name,
            base_url=entity.base_url,
            protocol=entity.protocol,
            api_type=entity.api_type,
            api_key=entity.api_key,
            extra_headers=entity.extra_headers,
            proxy_enabled=entity.proxy_enabled,
            proxy_url=entity.proxy_url,
            is_active=entity.is_active,
            created_at=ensure_utc(entity.created_at),
            updated_at=ensure_utc(entity.updated_at),
        )
    
    async def create(self, data: ProviderCreate) -> Provider:
        """Create Provider"""
        entity = ServiceProvider(
            name=data.name,
            base_url=data.base_url,
            protocol=data.protocol,
            api_type=data.api_type,
            api_key=data.api_key,
            extra_headers=data.extra_headers,
            proxy_enabled=data.proxy_enabled,
            proxy_url=data.proxy_url,
            is_active=data.is_active,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def get_by_id(self, id: int) -> Optional[Provider]:
        """Get Provider by ID"""
        result = await self.session.execute(
            select(ServiceProvider).where(ServiceProvider.id == id)
        )
        entity = result.scalar_one_or_none()
        return self._to_domain(entity) if entity else None
    
    async def get_by_name(self, name: str) -> Optional[Provider]:
        """Get Provider by Name"""
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
        name: Optional[str] = None,
        protocol: Optional[str] = None,
    ) -> tuple[list[Provider], int]:
        """Get Provider List"""
        # Build query
        query = select(ServiceProvider)
        count_query = select(func.count()).select_from(ServiceProvider)
        
        if is_active is not None:
            query = query.where(ServiceProvider.is_active == is_active)
            count_query = count_query.where(ServiceProvider.is_active == is_active)
            
        if name:
            query = query.where(ServiceProvider.name.ilike(f"%{name}%"))
            count_query = count_query.where(ServiceProvider.name.ilike(f"%{name}%"))
            
        if protocol:
            query = query.where(ServiceProvider.protocol == protocol)
            count_query = count_query.where(ServiceProvider.protocol == protocol)
        
        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Pagination
        query = query.order_by(ServiceProvider.id.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.session.execute(query)
        entities = result.scalars().all()
        
        return [self._to_domain(e) for e in entities], total
    
    async def update(self, id: int, data: ProviderUpdate) -> Optional[Provider]:
        """Update Provider"""
        result = await self.session.execute(
            select(ServiceProvider).where(ServiceProvider.id == id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return None
        
        # Update non-null fields
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(entity, key, value)
        
        entity.updated_at = to_utc_naive(utc_now())
        
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def delete(self, id: int) -> bool:
        """Delete Provider"""
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
        """Check if provider has associated model mappings"""
        result = await self.session.execute(
            select(func.count())
            .select_from(ModelMappingProviderORM)
            .where(ModelMappingProviderORM.provider_id == id)
        )
        count = result.scalar() or 0
        return count > 0
