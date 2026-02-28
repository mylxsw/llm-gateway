"""
Rate Limit Middleware Unit Tests

Tests for the rate limiting functionality.
"""

import pytest
from unittest.mock import MagicMock, patch
import time

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.middleware.rate_limit import (
    RateLimitMiddleware,
    InMemoryRateLimiter,
    parse_rate_limit,
)


class TestParseRateLimit:
    """Tests for parse_rate_limit function."""

    def test_parse_per_minute(self):
        """Parse '100/minute' format."""
        count, window = parse_rate_limit("100/minute")
        assert count == 100
        assert window == 60

    def test_parse_per_second(self):
        """Parse '10/second' format."""
        count, window = parse_rate_limit("10/second")
        assert count == 10
        assert window == 1

    def test_parse_per_hour(self):
        """Parse '1000/hour' format."""
        count, window = parse_rate_limit("1000/hour")
        assert count == 1000
        assert window == 3600

    def test_parse_per_day(self):
        """Parse '10000/day' format."""
        count, window = parse_rate_limit("10000/day")
        assert count == 10000
        assert window == 86400

    def test_parse_plural_units(self):
        """Parse plural time units."""
        count, window = parse_rate_limit("50/minutes")
        assert count == 50
        assert window == 60

        count, window = parse_rate_limit("5/seconds")
        assert count == 5
        assert window == 1

    def test_parse_case_insensitive(self):
        """Parse is case insensitive."""
        count, window = parse_rate_limit("100/MINUTE")
        assert count == 100
        assert window == 60

        count, window = parse_rate_limit("100/Minute")
        assert count == 100
        assert window == 60

    def test_parse_invalid_format(self):
        """Invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid rate limit format"):
            parse_rate_limit("100")

        with pytest.raises(ValueError, match="Invalid rate limit format"):
            parse_rate_limit("100/per/minute")

    def test_parse_invalid_count(self):
        """Invalid count raises ValueError."""
        with pytest.raises(ValueError, match="Invalid request count"):
            parse_rate_limit("abc/minute")

    def test_parse_unknown_unit(self):
        """Unknown time unit raises ValueError."""
        with pytest.raises(ValueError, match="Unknown time unit"):
            parse_rate_limit("100/week")


class TestInMemoryRateLimiter:
    """Tests for InMemoryRateLimiter class."""

    def test_allows_request_under_limit(self):
        """Request is allowed when under limit."""
        limiter = InMemoryRateLimiter()
        is_allowed, remaining, retry_after = limiter.is_allowed(
            "test_key", max_requests=10, window_seconds=60
        )
        assert is_allowed is True
        assert remaining == 9
        assert retry_after == 0

    def test_tracks_multiple_requests(self):
        """Multiple requests are tracked correctly."""
        limiter = InMemoryRateLimiter()

        for i in range(5):
            is_allowed, remaining, _ = limiter.is_allowed(
                "test_key", max_requests=10, window_seconds=60
            )
            assert is_allowed is True
            assert remaining == 9 - i

    def test_blocks_request_over_limit(self):
        """Request is blocked when over limit."""
        limiter = InMemoryRateLimiter()

        # Use up all requests
        for _ in range(10):
            limiter.is_allowed("test_key", max_requests=10, window_seconds=60)

        # Next request should be blocked
        is_allowed, remaining, retry_after = limiter.is_allowed(
            "test_key", max_requests=10, window_seconds=60
        )
        assert is_allowed is False
        assert remaining == 0
        assert retry_after > 0

    def test_different_keys_independent(self):
        """Different keys have independent limits."""
        limiter = InMemoryRateLimiter()

        # Use up limit for key1
        for _ in range(10):
            limiter.is_allowed("key1", max_requests=10, window_seconds=60)

        # key1 should be blocked
        is_allowed, _, _ = limiter.is_allowed("key1", max_requests=10, window_seconds=60)
        assert is_allowed is False

        # key2 should still be allowed
        is_allowed, remaining, _ = limiter.is_allowed("key2", max_requests=10, window_seconds=60)
        assert is_allowed is True
        assert remaining == 9

    def test_window_expires(self):
        """Rate limit window expires after specified time."""
        limiter = InMemoryRateLimiter()

        # Use up all requests with a 1-second window
        for _ in range(5):
            limiter.is_allowed("test_key", max_requests=5, window_seconds=1)

        # Should be blocked
        is_allowed, _, _ = limiter.is_allowed("test_key", max_requests=5, window_seconds=1)
        assert is_allowed is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        is_allowed, remaining, _ = limiter.is_allowed("test_key", max_requests=5, window_seconds=1)
        assert is_allowed is True
        assert remaining == 4

    def test_cleanup_expired(self):
        """Cleanup removes old entries."""
        limiter = InMemoryRateLimiter()

        # Add some requests
        limiter.is_allowed("key1", max_requests=10, window_seconds=1)
        limiter.is_allowed("key2", max_requests=10, window_seconds=1)

        # Wait for expiration
        time.sleep(1.1)

        # Cleanup with max age of 0 (should remove all)
        limiter.cleanup_expired(max_age_seconds=0)

        # Both keys should have been cleaned
        assert "key1" not in limiter._requests or len(limiter._requests["key1"]) == 0
        assert "key2" not in limiter._requests or len(limiter._requests["key2"]) == 0


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.RATE_LIMIT_ENABLED = True
        settings.RATE_LIMIT_DEFAULT = "100/minute"
        settings.RATE_LIMIT_ADMIN = "20/minute"
        settings.RATE_LIMIT_PROXY = "200/minute"
        return settings

    @pytest.fixture
    def app(self, mock_settings):
        """Create test FastAPI app with rate limit middleware."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        @app.get("/v1/chat/completions")
        async def proxy_endpoint():
            return {"message": "proxy success"}

        @app.get("/api/admin/users")
        async def admin_endpoint():
            return {"message": "admin success"}

        @app.get("/health")
        async def health_endpoint():
            return {"status": "healthy"}

        return app

    def test_middleware_allows_request(self, app, mock_settings):
        """Middleware allows requests under limit."""
        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            response = client.get("/test")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers

    def test_middleware_excluded_paths(self, app, mock_settings):
        """Health endpoint is excluded from rate limiting."""
        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            # Health endpoint should not have rate limit headers
            response = client.get("/health")
            assert response.status_code == 200
            # Rate limit headers should not be present for excluded paths
            # Note: The middleware still adds them, but let's verify the path is excluded
            # by making many requests
            for _ in range(150):  # More than the default limit
                response = client.get("/health")
                assert response.status_code == 200

    def test_middleware_returns_429_when_exceeded(self, app, mock_settings):
        """Middleware returns 429 when rate limit exceeded."""
        # Set a very low limit for testing
        mock_settings.RATE_LIMIT_DEFAULT = "3/minute"

        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            # Make requests up to the limit
            for i in range(3):
                response = client.get("/test")
                assert response.status_code == 200, f"Request {i+1} should succeed"

            # Next request should be rate limited
            response = client.get("/test")
            assert response.status_code == 429
            assert response.json()["error"]["code"] == "rate_limit_exceeded"
            assert "Retry-After" in response.headers

    def test_middleware_different_endpoint_limits(self, app, mock_settings):
        """Different endpoints have different rate limits."""
        mock_settings.RATE_LIMIT_DEFAULT = "2/minute"
        mock_settings.RATE_LIMIT_ADMIN = "1/minute"
        mock_settings.RATE_LIMIT_PROXY = "5/minute"

        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            # Test default endpoint limit
            for _ in range(2):
                response = client.get("/test")
                assert response.status_code == 200
            response = client.get("/test")
            assert response.status_code == 429

            # Test proxy endpoint limit (higher)
            # Note: In-memory limiter uses different keys, so proxy endpoint
            # should still work
            for _ in range(5):
                response = client.get("/v1/chat/completions")
                assert response.status_code == 200

    def test_middleware_disabled(self, app, mock_settings):
        """Middleware can be disabled via config."""
        mock_settings.RATE_LIMIT_ENABLED = False

        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            # Even with low limit, should not be rate limited when disabled
            mock_settings.RATE_LIMIT_DEFAULT = "1/minute"
            for _ in range(10):
                response = client.get("/test")
                assert response.status_code == 200

    def test_middleware_uses_api_key(self, app, mock_settings):
        """Middleware uses API key for rate limiting when present."""
        mock_settings.RATE_LIMIT_DEFAULT = "2/minute"

        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            # Make requests with API key
            for _ in range(2):
                response = client.get("/test", headers={"x-api-key": "test-api-key-123"})
                assert response.status_code == 200

            # Should be rate limited with this API key
            response = client.get("/test", headers={"x-api-key": "test-api-key-123"})
            assert response.status_code == 429

            # Different API key should still work
            response = client.get("/test", headers={"x-api-key": "another-api-key-456"})
            assert response.status_code == 200

    def test_middleware_uses_bearer_token(self, app, mock_settings):
        """Middleware uses Bearer token for rate limiting."""
        mock_settings.RATE_LIMIT_DEFAULT = "2/minute"

        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            # Make requests with Bearer token
            for _ in range(2):
                response = client.get("/test", headers={"Authorization": "Bearer my-token-123"})
                assert response.status_code == 200

            # Should be rate limited
            response = client.get("/test", headers={"Authorization": "Bearer my-token-123"})
            assert response.status_code == 429

            # Different token should work
            response = client.get("/test", headers={"Authorization": "Bearer another-token"})
            assert response.status_code == 200

    def test_middleware_x_forwarded_for(self, app, mock_settings):
        """Middleware respects X-Forwarded-For header for IP detection."""
        mock_settings.RATE_LIMIT_DEFAULT = "2/minute"

        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            # Make requests from different "clients" via X-Forwarded-For
            for _ in range(2):
                response = client.get("/test", headers={"X-Forwarded-For": "192.168.1.1"})
                assert response.status_code == 200

            # Should be rate limited for this IP
            response = client.get("/test", headers={"X-Forwarded-For": "192.168.1.1"})
            assert response.status_code == 429

            # Different IP should work
            response = client.get("/test", headers={"X-Forwarded-For": "192.168.1.2"})
            assert response.status_code == 200

    def test_middleware_rate_limit_headers(self, app, mock_settings):
        """Middleware adds correct rate limit headers."""
        mock_settings.RATE_LIMIT_DEFAULT = "10/minute"

        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            response = client.get("/test")
            assert response.status_code == 200

            # Check headers
            assert response.headers["X-RateLimit-Limit"] == "10"
            assert response.headers["X-RateLimit-Remaining"] == "9"
            assert "X-RateLimit-Reset" in response.headers

    def test_middleware_static_files_excluded(self, app, mock_settings):
        """Static file requests are excluded from rate limiting."""
        mock_settings.RATE_LIMIT_DEFAULT = "1/minute"

        with patch("app.middleware.rate_limit.get_settings", return_value=mock_settings):
            app.add_middleware(RateLimitMiddleware)
            client = TestClient(app)

            # Static file extensions should be excluded
            # Note: These will return 404 since files don't exist,
            # but they shouldn't be rate limited
            for _ in range(5):
                response = client.get("/static/app.js")
                # 404 is fine, we just want to ensure no 429
                assert response.status_code in [200, 404, 405]
