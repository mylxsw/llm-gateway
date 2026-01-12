"""
Configuration Management Module

Configures application parameters via environment variables or .env file.
Supports SQLite (default) and PostgreSQL databases.
"""

from functools import lru_cache
from typing import Literal

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
    
    # HTTP Client Config
    # Request timeout (seconds)
    HTTP_TIMEOUT: int = 60
    
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

    # Log Cleanup Config
    # Log retention days (default 7 days)
    LOG_RETENTION_DAYS: int = 7
    # Log cleanup execution hour (0-23, default 4 AM)
    LOG_CLEANUP_HOUR: int = 4

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get application configuration (Singleton)
    
    Uses lru_cache to ensure configuration is loaded only once, improving performance.
    
    Returns:
        Settings: Application configuration instance
    """
    return Settings()