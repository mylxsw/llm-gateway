"""
Redis Connection Management Module

Provides Redis client lifecycle management for the KV store backend.
Only used when KV_STORE_TYPE is set to "redis".
"""

import logging
import warnings
from typing import Any, Optional
from urllib.parse import urlparse

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - depends on runtime deps
    Redis = None  # type: ignore[assignment]

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global Redis client instance
_redis_client: Optional[Any] = None


def _check_redis_security(redis_url: str) -> None:
    """
    Check Redis connection security.

    Warns if Redis URL has no password and is not a localhost connection.
    """
    parsed = urlparse(redis_url)

    # Check if password is present in URL
    has_password = bool(parsed.password)

    # Check if connecting to localhost
    is_localhost = parsed.hostname in ("localhost", "127.0.0.1", "::1")

    if not has_password and not is_localhost:
        warnings.warn(
            "SECURITY WARNING: Redis connection has no password and is not connecting to localhost. "
            "This is insecure for production environments. "
            "Please set a password in REDIS_URL using the format: redis://:password@host:port/db",
            UserWarning,
            stacklevel=3,
        )
        logger.warning(
            "Redis connection without password to non-localhost host detected. "
            "Consider adding password authentication for production."
        )


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

    # Security check for Redis connection
    _check_redis_security(settings.REDIS_URL)

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
