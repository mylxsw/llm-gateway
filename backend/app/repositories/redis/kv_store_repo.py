"""
Key-Value Store Repository Redis Implementation

Provides concrete Redis operation implementation for KV Store.
Uses Redis native TTL for automatic key expiration.
"""

import json
from typing import Optional

from redis.asyncio import Redis

from app.common.time import utc_now
from app.domain.kv_store import KeyValueModel
from app.repositories.kv_store_repo import KVStoreRepository


class RedisKVStoreRepository(KVStoreRepository):
    """
    Key-Value Store Repository Redis Implementation

    Uses Redis to implement KV Store operations.
    Leverages Redis native TTL for automatic key expiration,
    eliminating the need for scheduled cleanup tasks.
    """

    def __init__(self, client: Redis):
        """
        Initialize Repository

        Args:
            client: Async Redis client instance
        """
        self.client = client

    def _serialize(self, value: str, created_at: str, updated_at: str) -> str:
        """Serialize value with metadata to JSON string"""
        return json.dumps(
            {
                "value": value,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

    def _deserialize(self, key: str, raw: str) -> KeyValueModel:
        """Deserialize JSON string to domain model"""
        data = json.loads(raw)
        return KeyValueModel(
            key=key,
            value=data["value"],
            expires_at=None,  # Redis manages TTL natively, not tracked in data
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    async def get(self, key: str) -> Optional[KeyValueModel]:
        """Get value by key, returns None if not found or expired"""
        raw = await self.client.get(key)
        if raw is None:
            return None
        return self._deserialize(key, raw)

    async def set(
        self, key: str, value: str, ttl_seconds: Optional[int] = None
    ) -> KeyValueModel:
        """Set a key-value pair with optional TTL"""
        now = utc_now()
        now_iso = now.isoformat()

        # Preserve original created_at if key already exists
        existing = await self.client.get(key)
        if existing is not None:
            existing_data = json.loads(existing)
            created_at = existing_data["created_at"]
        else:
            created_at = now_iso

        data = self._serialize(value, created_at, now_iso)

        if ttl_seconds is not None and ttl_seconds > 0:
            await self.client.set(key, data, ex=ttl_seconds)
        else:
            await self.client.set(key, data)

        return KeyValueModel(
            key=key,
            value=value,
            expires_at=None,
            created_at=created_at,
            updated_at=now_iso,
        )

    async def delete(self, key: str) -> bool:
        """Delete a key"""
        deleted_count = await self.client.delete(key)
        return deleted_count > 0

    async def cleanup_expired(self) -> int:
        """
        No-op for Redis backend.

        Redis manages key expiration natively via TTL,
        so no manual cleanup is needed.
        """
        return 0
