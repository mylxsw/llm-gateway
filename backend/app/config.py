"""
配置管理模块

通过环境变量或 .env 文件配置应用参数。
支持 SQLite（默认）和 PostgreSQL 两种数据库。
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用配置类
    
    所有配置项均可通过环境变量覆盖，环境变量名与字段名一致（大写）。
    """
    
    # 应用配置
    APP_NAME: str = "LLM Gateway"
    DEBUG: bool = False
    
    # 数据库配置
    # 支持 "sqlite" 或 "postgresql"
    DATABASE_TYPE: Literal["sqlite", "postgresql"] = "sqlite"
    # SQLite 默认数据库路径，PostgreSQL 需要完整连接字符串
    DATABASE_URL: str = "sqlite+aiosqlite:///./llm_gateway.db"
    
    # 重试配置
    # 同供应商最大重试次数（状态码 >= 500 时触发）
    RETRY_MAX_ATTEMPTS: int = 3
    # 重试间隔（毫秒）
    RETRY_DELAY_MS: int = 1000
    
    # HTTP 客户端配置
    # 请求超时时间（秒）
    HTTP_TIMEOUT: int = 60
    
    # API Key 配置
    # 生成的 API Key 前缀
    API_KEY_PREFIX: str = "lgw-"
    # API Key 长度（不含前缀）
    API_KEY_LENGTH: int = 32

    # 管理后台登录鉴权
    # 当同时设置 ADMIN_USERNAME 和 ADMIN_PASSWORD 时启用登录鉴权；否则不需要登录。
    ADMIN_USERNAME: str | None = None
    ADMIN_PASSWORD: str | None = None
    # 管理后台登录令牌有效期（秒）
    ADMIN_TOKEN_TTL_SECONDS: int = 86400

    # 日志清理配置
    # 日志保留天数（默认 7 天）
    LOG_RETENTION_DAYS: int = 7
    # 日志清理执行时间（小时，0-23，默认 4 点即凌晨）
    LOG_CLEANUP_HOUR: int = 4

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache()
def get_settings() -> Settings:
    """
    获取应用配置（单例模式）
    
    使用 lru_cache 确保配置只加载一次，提高性能。
    
    Returns:
        Settings: 应用配置实例
    """
    return Settings()
