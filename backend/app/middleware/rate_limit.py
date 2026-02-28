"""
Rate Limit Middleware Module

Implements API rate limiting based on IP address or API key.
Supports configurable rate limits for different endpoint types.
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings

logger = logging.getLogger(__name__)

# Rate limit configurations
DEFAULT_RATE_LIMIT = "100/minute"
ADMIN_RATE_LIMIT = "20/minute"
PROXY_RATE_LIMIT = "200/minute"


def parse_rate_limit(limit: str) -> tuple[int, int]:
    """
    Parse rate limit string to requests count and window seconds.

    Args:
        limit: Rate limit string like "100/minute", "20/hour", etc.

    Returns:
        Tuple of (requests_count, window_seconds)

    Raises:
        ValueError: If rate limit format is invalid
    """
    parts = limit.lower().split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid rate limit format: {limit}")

    try:
        count = int(parts[0])
    except ValueError as exc:
        raise ValueError(f"Invalid request count in rate limit: {limit}") from exc

    unit = parts[1]
    unit_multipliers = {
        "second": 1,
        "seconds": 1,
        "minute": 60,
        "minutes": 60,
        "hour": 3600,
        "hours": 3600,
        "day": 86400,
        "days": 86400,
    }

    if unit not in unit_multipliers:
        raise ValueError(f"Unknown time unit in rate limit: {unit}")

    return count, unit_multipliers[unit]


class InMemoryRateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.

    For production with multiple workers, consider using Redis-backed limiter.
    """

    def __init__(self) -> None:
        # Structure: {key: [(timestamp, count), ...]}
        self._requests: dict[str, list[tuple[float, int]]] = {}

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Unique identifier (IP or API key)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        current_time = time.time()
        window_start = current_time - window_seconds

        # Get existing requests for this key
        if key not in self._requests:
            self._requests[key] = []

        # Clean up old entries outside the window
        self._requests[key] = [
            (ts, count) for ts, count in self._requests[key]
            if ts > window_start
        ]

        # Calculate total requests in current window
        total_requests = sum(count for _, count in self._requests[key])

        if total_requests >= max_requests:
            # Calculate retry after
            oldest = min(ts for ts, _ in self._requests[key]) if self._requests[key] else current_time
            retry_after = int(oldest + window_seconds - current_time) + 1
            return False, 0, max(1, retry_after)

        # Record this request
        self._requests[key].append((current_time, 1))
        remaining = max_requests - total_requests - 1

        return True, remaining, 0

    def cleanup_expired(self, max_age_seconds: int = 3600) -> None:
        """Remove entries older than max_age_seconds."""
        cutoff = time.time() - max_age_seconds
        self._requests = {
            k: v for k, v in self._requests.items()
            if v and max(ts for ts, _ in v) > cutoff
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate Limit Middleware

    Enforces rate limits based on:
    1. API Key (if authenticated) - higher priority
    2. Client IP address - fallback

    Different limits apply to different endpoint types:
    - Proxy endpoints (/v1/*): PROXY_RATE_LIMIT
    - Admin endpoints (/api/*): ADMIN_RATE_LIMIT
    - Other endpoints: DEFAULT_RATE_LIMIT
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        settings = get_settings()
        self.enabled = settings.RATE_LIMIT_ENABLED
        self.default_limit = settings.RATE_LIMIT_DEFAULT
        self.admin_limit = settings.RATE_LIMIT_ADMIN
        self.proxy_limit = settings.RATE_LIMIT_PROXY

        self._limiter = InMemoryRateLimiter()

        # Parse rate limits
        self._default_max, self._default_window = parse_rate_limit(self.default_limit)
        self._admin_max, self._admin_window = parse_rate_limit(self.admin_limit)
        self._proxy_max, self._proxy_window = parse_rate_limit(self.proxy_limit)

        logger.info(
            f"Rate limit middleware initialized: enabled={self.enabled}, "
            f"default={self.default_limit}, admin={self.admin_limit}, proxy={self.proxy_limit}"
        )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check X-Forwarded-For header (for reverse proxy setups)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        # Fallback to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _get_rate_limit_key(self, request: Request) -> tuple[str, str]:
        """
        Get rate limit key and type.

        Returns:
            Tuple of (key, key_type) where key_type is 'api_key' or 'ip'
        """
        # Try to get API key from headers
        api_key = request.headers.get("x-api-key")
        if not api_key:
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                api_key = auth[7:].strip()

        if api_key:
            # Use hashed key for privacy (first 8 chars as identifier)
            return f"apikey:{api_key[:8]}", "api_key"

        # Fallback to IP-based limiting
        ip = self._get_client_ip(request)
        return f"ip:{ip}", "ip"

    def _get_endpoint_limits(self, path: str) -> tuple[int, int]:
        """
        Get rate limits for the endpoint.

        Args:
            path: Request path

        Returns:
            Tuple of (max_requests, window_seconds)
        """
        # Proxy endpoints (OpenAI/Anthropic compatible)
        if path.startswith("/v1/"):
            return self._proxy_max, self._proxy_window

        # Admin API endpoints
        if path.startswith("/api/"):
            return self._admin_max, self._admin_window

        # Default for other endpoints
        return self._default_max, self._default_window

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path should be excluded from rate limiting."""
        excluded_prefixes = [
            "/health",
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico",
        ]
        return any(path == prefix or path.startswith(prefix) for prefix in excluded_prefixes)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiter."""
        # Skip if rate limiting is disabled
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        # Skip excluded paths
        if self._is_excluded_path(path):
            return await call_next(request)

        # Skip static files
        if path.startswith("/_next/") or any(
            path.endswith(ext) for ext in [".js", ".css", ".png", ".jpg", ".ico", ".svg", ".woff", ".woff2"]
        ):
            return await call_next(request)

        # Get rate limit key
        key, key_type = self._get_rate_limit_key(request)

        # Get endpoint-specific limits
        max_requests, window_seconds = self._get_endpoint_limits(path)

        # Check rate limit
        is_allowed, remaining, retry_after = self._limiter.is_allowed(
            key, max_requests, window_seconds
        )

        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded: key={key}, type={key_type}, path={path}, "
                f"limit={max_requests}/{window_seconds}s"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": "Rate limit exceeded. Please try again later.",
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded",
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(retry_after),
                    "Retry-After": str(retry_after),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(window_seconds)

        return response

    def cleanup(self) -> None:
        """Clean up expired rate limit entries."""
        self._limiter.cleanup_expired()
        logger.debug("Rate limit cleanup completed")
