"""
Model Repository SQLAlchemy Implementation

Provides concrete database operation implementation for Model Mappings and Model-Provider Mappings.
"""

from typing import Optional

from sqlalchemy import func, select, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.time import ensure_utc, to_utc_naive, utc_now
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
    Model Repository SQLAlchemy Implementation
    
    Uses SQLAlchemy ORM to implement database operations for Model Mappings.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Repository
        
        Args:
            session: Async database session
        """
        self.session = session
    
    def _mapping_to_domain(self, entity: ModelMappingORM) -> ModelMapping:
        """Convert Model Mapping ORM entity to domain model"""
        return ModelMapping(
            requested_model=entity.requested_model,
            strategy=entity.strategy,
            model_type=entity.model_type or "chat",
            matching_rules=entity.matching_rules,
            capabilities=entity.capabilities,
            is_active=entity.is_active,
            input_price=float(entity.input_price) if entity.input_price is not None else None,
            output_price=float(entity.output_price) if entity.output_price is not None else None,
            billing_mode=entity.billing_mode,
            per_request_price=float(entity.per_request_price) if entity.per_request_price is not None else None,
            per_image_price=float(entity.per_image_price) if entity.per_image_price is not None else None,
            tiered_pricing=entity.tiered_pricing,
            cache_billing_enabled=entity.cache_billing_enabled,
            cached_input_price=float(entity.cached_input_price) if entity.cached_input_price is not None else None,
            cached_output_price=float(entity.cached_output_price) if entity.cached_output_price is not None else None,
            created_at=ensure_utc(entity.created_at),
            updated_at=ensure_utc(entity.updated_at),
        )

    def _provider_mapping_to_domain(
        self,
        entity: ModelMappingProviderORM,
        provider_name: str = "",
        provider_protocol: str | None = None,
        provider_is_active: bool | None = None,
    ) -> ModelMappingProviderResponse:
        """Convert Model-Provider Mapping ORM entity to domain model"""
        return ModelMappingProviderResponse(
            id=entity.id,
            requested_model=entity.requested_model,
            provider_id=entity.provider_id,
            provider_name=provider_name,
            provider_protocol=provider_protocol,
            provider_is_active=provider_is_active,
            target_model_name=entity.target_model_name,
            provider_rules=entity.provider_rules,
            input_price=float(entity.input_price) if entity.input_price is not None else None,
            output_price=float(entity.output_price) if entity.output_price is not None else None,
            billing_mode=entity.billing_mode,
            per_request_price=float(entity.per_request_price)
            if entity.per_request_price is not None
            else None,
            per_image_price=float(entity.per_image_price)
            if entity.per_image_price is not None
            else None,
            tiered_pricing=entity.tiered_pricing,
            cache_billing_enabled=entity.cache_billing_enabled,
            cached_input_price=float(entity.cached_input_price) if entity.cached_input_price is not None else None,
            cached_output_price=float(entity.cached_output_price) if entity.cached_output_price is not None else None,
            priority=entity.priority,
            weight=entity.weight,
            is_active=entity.is_active,
            created_at=ensure_utc(entity.created_at),
            updated_at=ensure_utc(entity.updated_at),
        )

    # ============ Model Mapping Operations ============
    
    async def create_mapping(self, data: ModelMappingCreate) -> ModelMapping:
        """Create Model Mapping"""
        entity = ModelMappingORM(
            requested_model=data.requested_model,
            strategy=data.strategy,
            model_type=data.model_type,
            matching_rules=data.matching_rules,
            capabilities=data.capabilities,
            is_active=data.is_active,
            input_price=data.input_price,
            output_price=data.output_price,
            billing_mode=data.billing_mode,
            per_request_price=data.per_request_price,
            per_image_price=data.per_image_price,
            tiered_pricing=[
                t.model_dump() for t in (data.tiered_pricing or [])
            ]
            if data.tiered_pricing is not None
            else None,
            cache_billing_enabled=data.cache_billing_enabled or False,
            cached_input_price=data.cached_input_price,
            cached_output_price=data.cached_output_price,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return self._mapping_to_domain(entity)
    
    async def get_mapping(self, requested_model: str) -> Optional[ModelMapping]:
        """Get Model Mapping by requested model name"""
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
        requested_model: Optional[str] = None,
        target_model_name: Optional[str] = None,
        model_type: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> tuple[list[ModelMapping], int]:
        """Get Model Mapping list"""
        query = select(ModelMappingORM)
        count_query = select(func.count()).select_from(ModelMappingORM)
        
        conditions = []
        
        if is_active is not None:
            conditions.append(ModelMappingORM.is_active == is_active)
            
        if requested_model:
            conditions.append(ModelMappingORM.requested_model.ilike(f"%{requested_model}%"))
            
        if model_type:
            if model_type == 'chat':
                conditions.append(or_(ModelMappingORM.model_type == model_type, ModelMappingORM.model_type.is_(None)))
            else:
                conditions.append(ModelMappingORM.model_type == model_type)
            
        if strategy:
            conditions.append(ModelMappingORM.strategy == strategy)
            
        if target_model_name:
            # Use EXISTS clause to avoid join duplication and distinct equality issues on JSON columns
            conditions.append(
                ModelMappingORM.providers.any(
                    ModelMappingProviderORM.target_model_name.ilike(f"%{target_model_name}%")
                )
            )

        # Apply conditions
        if conditions:
            query = query.where(*conditions)
            count_query = count_query.where(*conditions)

        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # Pagination
        query = query.order_by(ModelMappingORM.requested_model)
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.session.execute(query)
        entities = result.scalars().all()
        
        return [self._mapping_to_domain(e) for e in entities], total
    
    async def update_mapping(
        self, requested_model: str, data: ModelMappingUpdate
    ) -> Optional[ModelMapping]:
        """Update Model Mapping"""
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
        
        entity.updated_at = to_utc_naive(utc_now())
        
        await self.session.commit()
        await self.session.refresh(entity)
        return self._mapping_to_domain(entity)
    
    async def delete_mapping(self, requested_model: str) -> bool:
        """Delete Model Mapping (Cascades delete associated provider mappings)"""
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
    
    # ============ Model-Provider Mapping Operations ============
    
    async def add_provider_mapping(
        self, data: ModelMappingProviderCreate
    ) -> ModelMappingProviderResponse:
        """Create Model-Provider Mapping"""
        entity = ModelMappingProviderORM(
            requested_model=data.requested_model,
            provider_id=data.provider_id,
            target_model_name=data.target_model_name,
            provider_rules=data.provider_rules,
            input_price=data.input_price,
            output_price=data.output_price,
            billing_mode=data.billing_mode,
            per_request_price=data.per_request_price,
            per_image_price=data.per_image_price,
            tiered_pricing=[
                t.model_dump() for t in (data.tiered_pricing or [])
            ]
            if data.tiered_pricing is not None
            else None,
            cache_billing_enabled=(
                data.cache_billing_enabled
                if data.cache_billing_enabled is not None
                else False
            ),
            cached_input_price=data.cached_input_price,
            cached_output_price=data.cached_output_price,
            priority=data.priority,
            weight=data.weight,
            is_active=data.is_active,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        
        # Get provider name
        provider_result = await self.session.execute(
            select(ServiceProvider).where(ServiceProvider.id == entity.provider_id)
        )
        provider = provider_result.scalar_one_or_none()
        provider_name = provider.name if provider else ""
        provider_protocol = provider.protocol if provider else None
        provider_is_active = provider.is_active if provider else None

        return self._provider_mapping_to_domain(
            entity, provider_name, provider_protocol, provider_is_active
        )
    
    async def get_provider_mapping(self, id: int) -> Optional[ModelMappingProvider]:
        """Get Model-Provider Mapping by ID"""
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
        provider_is_active = entity.provider.is_active if entity.provider else None
        return self._provider_mapping_to_domain(
            entity, provider_name, provider_protocol, provider_is_active
        )
    
    async def get_provider_mappings(
        self,
        requested_model: str,
        is_active: Optional[bool] = None,
    ) -> list[ModelMappingProviderResponse]:
        """Get all provider mappings under a requested model"""
        return await self.get_all_provider_mappings(
            requested_model=requested_model, is_active=is_active
        )

    async def get_all_provider_mappings(
        self,
        requested_model: Optional[str] = None,
        provider_id: Optional[int] = None,
        target_model_name: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[ModelMappingProviderResponse]:
        """Get Model-Provider Mapping list"""
        query = select(ModelMappingProviderORM).options(
            selectinload(ModelMappingProviderORM.provider)
        )
        
        if requested_model is not None:
            query = query.where(
                ModelMappingProviderORM.requested_model == requested_model
            )
        if provider_id is not None:
            query = query.where(ModelMappingProviderORM.provider_id == provider_id)
        if target_model_name is not None:
            normalized_target = target_model_name.strip()
            query = query.where(
                ModelMappingProviderORM.target_model_name.ilike(f"%{normalized_target}%")
            )
        if is_active is not None:
            query = query.where(ModelMappingProviderORM.is_active == is_active)
        
        # Sort by priority
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
                e.provider.is_active if e.provider else None,
            )
            for e in entities
        ]
    
    async def update_provider_mapping(
        self, id: int, data: ModelMappingProviderUpdate
    ) -> Optional[ModelMappingProvider]:
        """Update Model-Provider Mapping"""
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
        
        entity.updated_at = to_utc_naive(utc_now())
        
        await self.session.commit()
        await self.session.refresh(entity)
        
        provider_name = entity.provider.name if entity.provider else ""
        provider_protocol = entity.provider.protocol if entity.provider else None
        return self._provider_mapping_to_domain(entity, provider_name, provider_protocol)

    async def bulk_update_provider_mappings(
        self,
        provider_id: int,
        current_target_model_name: str,
        data: ModelMappingProviderUpdate,
    ) -> int:
        """Bulk update mappings by provider and exact target model name (case-insensitive)."""
        normalized_target = current_target_model_name.strip().lower()
        result = await self.session.execute(
            select(ModelMappingProviderORM)
            .where(ModelMappingProviderORM.provider_id == provider_id)
            .where(
                func.lower(func.trim(ModelMappingProviderORM.target_model_name))
                == normalized_target
            )
        )
        entities = result.scalars().all()
        if not entities:
            return 0

        update_data = data.model_dump(exclude_unset=True)
        now = to_utc_naive(utc_now())
        for entity in entities:
            for key, value in update_data.items():
                setattr(entity, key, value)
            entity.updated_at = now

        await self.session.commit()
        return len(entities)
    
    async def delete_provider_mapping(self, id: int) -> bool:
        """Delete Model-Provider Mapping"""
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
        """Get the count of providers associated with the model"""
        result = await self.session.execute(
            select(func.count())
            .select_from(ModelMappingProviderORM)
            .where(ModelMappingProviderORM.requested_model == requested_model)
        )
        return result.scalar() or 0

    async def get_active_provider_count(self, requested_model: str) -> int:
        """Get the count of active providers associated with the model.
        
        Active means both the mapping is_active AND the provider is_active.
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(ModelMappingProviderORM)
            .join(
                ServiceProvider,
                ModelMappingProviderORM.provider_id == ServiceProvider.id
            )
            .where(ModelMappingProviderORM.requested_model == requested_model)
            .where(ModelMappingProviderORM.is_active.is_(True))
            .where(ServiceProvider.is_active.is_(True))
        )
        return result.scalar() or 0
