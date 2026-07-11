"""
Configuration Management Module

Configures application parameters via environment variables or .env file.
Supports SQLite (default) and PostgreSQL databases.
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Configuration Class

    All configuration items can be overridden by environment variables, with names matching fields (uppercase).
    """

    # Application Config
    APP_NAME: str = "LLM Gateway"
    DEBUG: bool = False

    # Database Config
    # Supports "sqlite" or "postgresql"
    DATABASE_TYPE: Literal["sqlite", "postgresql"] = "sqlite"
    # SQLite default database path, PostgreSQL requires full connection string
    DATABASE_URL: str = "sqlite+aiosqlite:///./llm_gateway.db"

    # Retry Config
    # Max retries on same provider (triggered when status code >= 500)
    RETRY_MAX_ATTEMPTS: int = 3
    # Retry interval (ms)
    RETRY_DELAY_MS: int = 1000

    # Provider Health / Soft Circuit Breaker Config
    # Degraded providers remain available but are tried after healthy providers.
    PROVIDER_HEALTH_ENABLED: bool = True
    # Sliding-window duration in seconds (default: 10 minutes)
    PROVIDER_HEALTH_WINDOW_SECONDS: int = 600
    # Minimum logical provider calls required before degradation
    PROVIDER_HEALTH_MIN_SAMPLES: int = 6
    # Failure rate at or above which a provider/model mapping is degraded
    PROVIDER_HEALTH_FAILURE_RATE_THRESHOLD: float = 0.5

    # HTTP Client Config
    # Request timeout (seconds)
    HTTP_TIMEOUT: int = 1800
    # Whether provider base URLs may use private/internal IP addresses
    ALLOW_PRIVATE_IP_PROVIDER: bool = False

    # API Key Config
    # Generated API Key prefix
    API_KEY_PREFIX: str = "lgw-"
    # API Key length (excluding prefix)
    API_KEY_LENGTH: int = 32

    # Admin Login Authentication
    # Enables login authentication when both ADMIN_USERNAME and ADMIN_PASSWORD are set; otherwise, login is not required.
    ADMIN_USERNAME: str | None = None
    ADMIN_PASSWORD: str | None = None
    # Admin login token TTL (seconds)
    ADMIN_TOKEN_TTL_SECONDS: int = 86400

    # KV Store Config
    # KV store backend: "database" uses the SQL database, "redis" uses Redis
    KV_STORE_TYPE: Literal["database", "redis"] = "database"
    # Redis connection URL (only used when KV_STORE_TYPE is "redis")
    REDIS_URL: str = "redis://localhost:6379/0"

    # Log Cleanup Config
    # Log retention days (default 90 days)
    LOG_RETENTION_DAYS: int = 90
    # Log detail retention days (default 7 days, must not exceed LOG_RETENTION_DAYS)
    LOG_DETAIL_RETENTION_DAYS: int = 7
    # Log cleanup interval in hours (default 24 hours)
    LOG_CLEANUP_INTERVAL_HOURS: int = 24

    # CORS Config
    # Comma-separated list of allowed origins for CORS
    # Example: "http://localhost:3000,https://example.com"
    # Default: empty list (no CORS allowed in production)
    ALLOWED_ORIGINS: str = ""

    # Encryption Config
    # Encryption key for sensitive data (e.g., API keys)
    # Generate with: python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
    # WARNING: Changing this key will make previously encrypted data unreadable
    ENCRYPTION_KEY: str | None = None
    # Whether API keys can be viewed/copied again in admin API Key list
    ENABLE_VIEW_API_KEYS: bool = False

    # Rate Limit Config
    # Enable/disable rate limiting (useful for development)
    RATE_LIMIT_ENABLED: bool = False
    # Default rate limit for general endpoints
    RATE_LIMIT_DEFAULT: str = "100/minute"
    # Rate limit for admin API endpoints
    RATE_LIMIT_ADMIN: str = "20/minute"
    # Rate limit for proxy endpoints (/v1/*)
    RATE_LIMIT_PROXY: str = "200/minute"

    # MCP (Model Context Protocol) Config
    # Enable the MCP management interface mounted at /mcp. Requests must
    # authenticate with an API key that has is_mcp_admin=True.
    MCP_ENABLED: bool = False
    # Allow MCP write/management tools (create/update/delete providers, models,
    # API keys, retry/cancel requests). When False, only read-only tools are
    # exposed. Grant/revoke of MCP admin is NEVER available via MCP.
    MCP_ALLOW_WRITE: bool = False
    # DNS-rebinding protection for the MCP transport. Disabled by default since
    # the gateway is typically deployed behind varying hostnames and MCP access
    # is already gated by API-key auth. Enable and set MCP_ALLOWED_HOSTS /
    # MCP_ALLOWED_ORIGINS for hardened deployments.
    MCP_DNS_REBINDING_PROTECTION: bool = False
    # Comma-separated allowed Host header values (used when protection enabled).
    MCP_ALLOWED_HOSTS: str = ""
    # Comma-separated allowed Origin header values (used when protection enabled).
    MCP_ALLOWED_ORIGINS: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @model_validator(mode="after")
    def validate_log_retention(self) -> "Settings":
        if self.LOG_RETENTION_DAYS < 1:
            raise ValueError("LOG_RETENTION_DAYS must be >= 1")
        if self.LOG_DETAIL_RETENTION_DAYS < 1:
            raise ValueError("LOG_DETAIL_RETENTION_DAYS must be >= 1")
        if self.LOG_DETAIL_RETENTION_DAYS > self.LOG_RETENTION_DAYS:
            raise ValueError(
                "LOG_DETAIL_RETENTION_DAYS must be less than or equal to LOG_RETENTION_DAYS"
            )
        if self.PROVIDER_HEALTH_WINDOW_SECONDS < 1:
            raise ValueError("PROVIDER_HEALTH_WINDOW_SECONDS must be >= 1")
        if self.PROVIDER_HEALTH_MIN_SAMPLES < 1:
            raise ValueError("PROVIDER_HEALTH_MIN_SAMPLES must be >= 1")
        if not 0 < self.PROVIDER_HEALTH_FAILURE_RATE_THRESHOLD <= 1:
            raise ValueError(
                "PROVIDER_HEALTH_FAILURE_RATE_THRESHOLD must be in (0, 1]"
            )
        return self


@lru_cache()
def get_settings() -> Settings:
    """
    Get application configuration (Singleton)

    Uses lru_cache to ensure configuration is loaded only once, improving performance.

    Returns:
        Settings: Application configuration instance
    """
    return Settings()
