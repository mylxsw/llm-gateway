"""
SQLAlchemy ORM 模型定义

定义系统的所有数据库表结构，包括：
- service_providers: 服务商表
- model_mappings: 模型映射表
- model_mapping_providers: 模型-供应商映射表
- api_keys: API Key 表
- request_logs: 请求日志表
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类"""
    pass


class ServiceProvider(Base):
    """
    服务商表
    
    存储上游 LLM 供应商的配置信息，包括接口地址、协议类型等。
    """
    __tablename__ = "service_providers"
    
    # 主键 ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 供应商名称，唯一
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # 接口基础地址，如 https://api.openai.com
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # 协议类型：openai 或 anthropic
    protocol: Mapped[str] = mapped_column(String(50), nullable=False)
    # API 类型：chat / completion / embedding
    api_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 供应商的 API Key（加密存储建议）
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 是否激活
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # 关联关系：供应商下的模型映射
    model_mappings: Mapped[list["ModelMappingProvider"]] = relationship(
        "ModelMappingProvider", back_populates="provider"
    )


class ModelMapping(Base):
    """
    模型映射表
    
    以 requested_model（客户端请求的模型名）为主键，
    定义模型的选择策略和匹配规则。
    """
    __tablename__ = "model_mappings"
    
    # 请求模型名作为主键
    requested_model: Mapped[str] = mapped_column(
        String(100), primary_key=True, nullable=False
    )
    # 选择策略，当前仅支持 round_robin（轮询）
    strategy: Mapped[str] = mapped_column(String(50), default="round_robin")
    # 模型级匹配规则（JSON 格式）
    matching_rules: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # 模型能力描述（JSON 格式）
    capabilities: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # 是否激活
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # 关联关系：模型下的供应商映射
    providers: Mapped[list["ModelMappingProvider"]] = relationship(
        "ModelMappingProvider", back_populates="model_mapping"
    )


class ModelMappingProvider(Base):
    """
    模型-供应商映射表
    
    定义同一个 requested_model 在不同供应商下的目标模型名。
    这是系统的核心表，支持同一请求模型映射到不同供应商的不同实际模型。
    """
    __tablename__ = "model_mapping_providers"
    
    # 主键 ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 请求模型名（外键）
    requested_model: Mapped[str] = mapped_column(
        String(100), 
        ForeignKey("model_mappings.requested_model", ondelete="CASCADE"),
        nullable=False
    )
    # 供应商 ID（外键）
    provider_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("service_providers.id", ondelete="CASCADE"),
        nullable=False
    )
    # 该供应商对应的目标模型名（实际转发时使用的模型名）
    target_model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 供应商级匹配规则（JSON 格式）
    provider_rules: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # 优先级（数值越小优先级越高）
    priority: Mapped[int] = mapped_column(Integer, default=0)
    # 权重（用于加权轮询，当前未使用）
    weight: Mapped[int] = mapped_column(Integer, default=1)
    # 是否激活
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # 更新时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    
    # 唯一约束：同一模型下同一供应商只能有一条映射
    __table_args__ = (
        UniqueConstraint("requested_model", "provider_id", name="uq_model_provider"),
    )
    
    # 关联关系
    provider: Mapped["ServiceProvider"] = relationship(
        "ServiceProvider", back_populates="model_mappings"
    )
    model_mapping: Mapped["ModelMapping"] = relationship(
        "ModelMapping", back_populates="providers"
    )


class ApiKey(Base):
    """
    API Key 表
    
    用于客户端鉴权的 API Key 实体。
    """
    __tablename__ = "api_keys"
    
    # 主键 ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Key 名称，唯一，用于标识用途
    key_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Key 值（随机生成的 token），唯一
    key_value: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # 是否激活
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # 最后使用时间
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 关联关系：该 Key 的请求日志
    logs: Mapped[list["RequestLog"]] = relationship("RequestLog", back_populates="api_key")


class RequestLog(Base):
    """
    请求日志表
    
    记录所有代理请求的详细信息，包括时间、模型、供应商、Token 使用等。
    """
    __tablename__ = "request_logs"
    
    # 主键 ID
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 请求时间
    request_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # API Key ID（外键）
    api_key_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("api_keys.id"), nullable=True
    )
    # API Key 名称（冗余字段，便于查询）
    api_key_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 请求模型名
    requested_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 目标模型名（实际转发的模型）
    target_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 供应商 ID
    provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("service_providers.id"), nullable=True
    )
    # 供应商名称（冗余字段）
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 重试次数
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    # 匹配到的供应商数量
    matched_provider_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 首字节延迟（毫秒）
    first_byte_delay_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 总耗时（毫秒）
    total_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 输入 Token 数
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 输出 Token 数
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 请求头（JSON 格式，已脱敏）
    request_headers: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # 请求体（JSON 格式）
    request_body: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)
    # 响应状态码
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 响应体
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 错误信息
    error_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 追踪 ID
    trace_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 是否为流式请求
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # 索引定义，优化查询性能
    __table_args__ = (
        Index("idx_request_logs_time", "request_time"),
        Index("idx_request_logs_api_key", "api_key_id"),
        Index("idx_request_logs_model", "requested_model"),
        Index("idx_request_logs_provider", "provider_id"),
        Index("idx_request_logs_status", "response_status"),
    )
    
    # 关联关系
    api_key: Mapped[Optional["ApiKey"]] = relationship("ApiKey", back_populates="logs")
