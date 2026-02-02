"""
Key-Value Store Repository Interface

Defines the data access interface for KV Store.
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.kv_store import KeyValueModel


class KVStoreRepository(ABC):
    """Key-Value Store Repository Interface"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[KeyValueModel]:
        """
        Get value by key
        
        Returns None if key doesn't exist or is expired.
        
        Args:
            key: The key to look up
            
        Returns:
            KeyValueModel if found and not expired, None otherwise
        """
        pass
    
    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> KeyValueModel:
        """
        Set a key-value pair
        
        If the key already exists, it will be updated.
        
        Args:
            key: The key to set
            value: The value to store
            ttl_seconds: Time to live in seconds (None means never expires)
            
        Returns:
            KeyValueModel: The created/updated KV model
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete a key
        
        Args:
            key: The key to delete
            
        Returns:
            True if deleted, False if key didn't exist
        """
        pass
    
    @abstractmethod
    async def cleanup_expired(self) -> int:
        """
        Delete all expired keys
        
        Returns:
            Number of deleted keys
        """
        pass
