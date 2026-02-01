"""
Key-Value Store Repository SQLAlchemy Implementation

Provides concrete database operation implementation for KV Store.
"""

from datetime import timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time import ensure_utc, utc_now_naive
from app.db.models import KeyValueStore as KeyValueStoreORM
from app.domain.kv_store import KeyValueModel
from app.repositories.kv_store_repo import KVStoreRepository


class SQLAlchemyKVStoreRepository(KVStoreRepository):
    """
    Key-Value Store Repository SQLAlchemy Implementation
    
    Uses SQLAlchemy ORM to implement database operations for KV Store.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize Repository
        
        Args:
            session: Async database session
        """
        self.session = session
    
    def _to_domain(self, entity: KeyValueStoreORM) -> KeyValueModel:
        """Convert ORM entity to domain model"""
        return KeyValueModel(
            key=entity.key,
            value=entity.value,
            expires_at=ensure_utc(entity.expires_at) if entity.expires_at else None,
            created_at=ensure_utc(entity.created_at),
            updated_at=ensure_utc(entity.updated_at),
        )
    
    async def get(self, key: str) -> Optional[KeyValueModel]:
        """Get value by key, returns None if not found or expired"""
        result = await self.session.execute(
            select(KeyValueStoreORM).where(KeyValueStoreORM.key == key)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return None
        
        # Check if expired
        if entity.expires_at is not None:
            now = utc_now_naive()
            if entity.expires_at <= now:
                # Key is expired, delete it and return None
                await self.session.delete(entity)
                await self.session.commit()
                return None
        
        return self._to_domain(entity)
    
    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> KeyValueModel:
        """Set a key-value pair with optional TTL"""
        # Calculate expiration time
        expires_at = None
        if ttl_seconds is not None and ttl_seconds > 0:
            expires_at = utc_now_naive() + timedelta(seconds=ttl_seconds)
        
        # Check if key exists
        result = await self.session.execute(
            select(KeyValueStoreORM).where(KeyValueStoreORM.key == key)
        )
        entity = result.scalar_one_or_none()
        
        if entity:
            # Update existing
            entity.value = value
            entity.expires_at = expires_at
        else:
            # Create new
            entity = KeyValueStoreORM(
                key=key,
                value=value,
                expires_at=expires_at,
            )
            self.session.add(entity)
        
        await self.session.commit()
        await self.session.refresh(entity)
        return self._to_domain(entity)
    
    async def delete(self, key: str) -> bool:
        """Delete a key"""
        result = await self.session.execute(
            select(KeyValueStoreORM).where(KeyValueStoreORM.key == key)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            return False
        
        await self.session.delete(entity)
        await self.session.commit()
        return True
    
    async def cleanup_expired(self) -> int:
        """Delete all expired keys"""
        now = utc_now_naive()
        
        result = await self.session.execute(
            delete(KeyValueStoreORM).where(
                KeyValueStoreORM.expires_at.isnot(None),
                KeyValueStoreORM.expires_at <= now
            )
        )
        
        await self.session.commit()
        return result.rowcount
