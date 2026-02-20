"""
Redis Connection Management Module

Provides Redis client lifecycle management for the KV store backend.
Only used when KV_STORE_TYPE is set to "redis".
"""

import logging
from typing import Any, Optional

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - depends on runtime deps
    Redis = None  # type: ignore[assignment]

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[Any] = None


async def init_redis() -> None:
    """
    Initialize Redis Connection

    Creates an async Redis client from the configured REDIS_URL.
    Should be called during application startup when KV_STORE_TYPE is "redis".
    """
    global _redis_client

    if _redis_client is not None:
        logger.warning("Redis client already initialized")
        return

    if Redis is None:
        raise RuntimeError(
            "Redis backend requested but 'redis' package is not installed. "
            "Install backend dependencies (pip install -r requirements.txt)."
        )

    settings = get_settings()
    _redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    # Verify connectivity
    await _redis_client.ping()
    logger.info(f"Redis connection established: {settings.REDIS_URL}")


async def close_redis() -> None:
    """
    Close Redis Connection

    Gracefully closes the Redis client connection.
    Should be called during application shutdown.
    """
    global _redis_client

    if _redis_client is None:
        return

    await _redis_client.aclose()
    _redis_client = None
    logger.info("Redis connection closed")


def get_redis() -> Any:
    """
    Get Redis Client Instance

    Returns:
        Redis: The async Redis client

    Raises:
        RuntimeError: If Redis has not been initialized
    """
    if _redis_client is None:
        raise RuntimeError(
            "Redis client not initialized. "
            "Ensure KV_STORE_TYPE is set to 'redis' and init_redis() has been called."
        )
    return _redis_client
