"""
Test Key-Value Store Repository
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.repositories.sqlalchemy.kv_store_repo import SQLAlchemyKVStoreRepository


@pytest.mark.asyncio
async def test_set_and_get(db_session):
    """Test setting and getting a key-value pair"""
    repo = SQLAlchemyKVStoreRepository(db_session)
    
    # Set a key
    result = await repo.set("test_key", "test_value")
    
    assert result.key == "test_key"
    assert result.value == "test_value"
    assert result.expires_at is None
    
    # Get the key
    retrieved = await repo.get("test_key")
    
    assert retrieved is not None
    assert retrieved.key == "test_key"
    assert retrieved.value == "test_value"


@pytest.mark.asyncio
async def test_set_with_ttl(db_session):
    """Test setting a key with TTL"""
    repo = SQLAlchemyKVStoreRepository(db_session)
    
    # Set a key with 3600 seconds TTL
    result = await repo.set("ttl_key", "ttl_value", ttl_seconds=3600)
    
    assert result.key == "ttl_key"
    assert result.value == "ttl_value"
    assert result.expires_at is not None
    
    # Get the key (should still be valid)
    retrieved = await repo.get("ttl_key")
    
    assert retrieved is not None
    assert retrieved.value == "ttl_value"


@pytest.mark.asyncio
async def test_get_nonexistent_key(db_session):
    """Test getting a non-existent key"""
    repo = SQLAlchemyKVStoreRepository(db_session)
    
    result = await repo.get("nonexistent_key")
    
    assert result is None


@pytest.mark.asyncio
async def test_update_existing_key(db_session):
    """Test updating an existing key"""
    repo = SQLAlchemyKVStoreRepository(db_session)
    
    # Set initial value
    await repo.set("update_key", "initial_value")
    
    # Update value
    result = await repo.set("update_key", "updated_value")
    
    assert result.value == "updated_value"
    
    # Verify update
    retrieved = await repo.get("update_key")
    
    assert retrieved is not None
    assert retrieved.value == "updated_value"


@pytest.mark.asyncio
async def test_delete_key(db_session):
    """Test deleting a key"""
    repo = SQLAlchemyKVStoreRepository(db_session)
    
    # Set a key
    await repo.set("delete_key", "delete_value")
    
    # Delete the key
    deleted = await repo.delete("delete_key")
    
    assert deleted is True
    
    # Verify deletion
    retrieved = await repo.get("delete_key")
    
    assert retrieved is None


@pytest.mark.asyncio
async def test_delete_nonexistent_key(db_session):
    """Test deleting a non-existent key"""
    repo = SQLAlchemyKVStoreRepository(db_session)
    
    deleted = await repo.delete("nonexistent_key")
    
    assert deleted is False


@pytest.mark.asyncio
async def test_cleanup_expired(db_session):
    """Test cleaning up expired keys"""
    repo = SQLAlchemyKVStoreRepository(db_session)
    
    # Set a key that will expire immediately (0 second TTL won't work, so we set and then manually adjust)
    await repo.set("expired_key_1", "value1", ttl_seconds=1)
    await repo.set("expired_key_2", "value2", ttl_seconds=1)
    await repo.set("valid_key", "value3", ttl_seconds=3600)
    await repo.set("no_expiry_key", "value4")
    
    # Manually set expires_at to the past for expired keys
    from app.db.models import KeyValueStore
    from sqlalchemy import select, update
    from app.common.time import utc_now_naive
    
    past_time = utc_now_naive() - timedelta(hours=1)
    await db_session.execute(
        update(KeyValueStore)
        .where(KeyValueStore.key.in_(["expired_key_1", "expired_key_2"]))
        .values(expires_at=past_time)
    )
    await db_session.commit()
    
    # Cleanup expired keys
    deleted_count = await repo.cleanup_expired()
    
    assert deleted_count == 2
    
    # Verify expired keys are gone
    assert await repo.get("expired_key_1") is None
    assert await repo.get("expired_key_2") is None
    
    # Verify valid keys still exist
    assert await repo.get("valid_key") is not None
    assert await repo.get("no_expiry_key") is not None


@pytest.mark.asyncio
async def test_get_expired_key_returns_none_and_deletes(db_session):
    """Test that getting an expired key returns None and deletes it"""
    repo = SQLAlchemyKVStoreRepository(db_session)
    
    # Set a key with TTL
    await repo.set("auto_delete_key", "value", ttl_seconds=1)
    
    # Manually set expires_at to the past
    from app.db.models import KeyValueStore
    from sqlalchemy import update
    from app.common.time import utc_now_naive
    
    past_time = utc_now_naive() - timedelta(hours=1)
    await db_session.execute(
        update(KeyValueStore)
        .where(KeyValueStore.key == "auto_delete_key")
        .values(expires_at=past_time)
    )
    await db_session.commit()
    
    # Get should return None for expired key
    result = await repo.get("auto_delete_key")
    
    assert result is None
