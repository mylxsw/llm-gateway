"""
Provider protocol configuration and mapping helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.common.errors import ServiceError

OPENAI_PROTOCOL = "openai"
OPENAI_RESPONSES_PROTOCOL = "openai_responses"
ANTHROPIC_PROTOCOL = "anthropic"
GEMINI_PROTOCOL = "gemini"


@dataclass(frozen=True)
class ProtocolConfig:
    frontend: str
    implementation: str
    base_url: str
    label: str


FRONTEND_PROTOCOL_CONFIGS: dict[str, ProtocolConfig] = {
    "openai": ProtocolConfig(
        frontend="openai",
        implementation=OPENAI_PROTOCOL,
        base_url="https://api.openai.com/v1",
        label="OpenAI",
    ),
    "openai_responses": ProtocolConfig(
        frontend="openai_responses",
        implementation=OPENAI_RESPONSES_PROTOCOL,
        base_url="https://api.openai.com/v1",
        label="OpenAI Responses",
    ),
    "anthropic": ProtocolConfig(
        frontend="anthropic",
        implementation=ANTHROPIC_PROTOCOL,
        base_url="https://api.anthropic.com/v1",
        label="Anthropic",
    ),
    "gemini": ProtocolConfig(
        frontend="gemini",
        implementation=GEMINI_PROTOCOL,
        base_url="https://generativelanguage.googleapis.com",
        label="Google Gemini",
    ),
    "zhipu": ProtocolConfig(
        frontend="zhipu",
        implementation=OPENAI_PROTOCOL,
        base_url="https://open.bigmodel.cn/api/paas/v4",
        label="Zhipu (OpenAI)",
    ),
    "aliyun": ProtocolConfig(
        frontend="aliyun",
        implementation=OPENAI_PROTOCOL,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        label="Aliyun (OpenAI)",
    ),
    "moonshot": ProtocolConfig(
        frontend="moonshot",
        implementation=OPENAI_PROTOCOL,
        base_url="https://api.moonshot.cn/v1",
        label="Moonshot (OpenAI)",
    ),
}

FRONTEND_PROTOCOLS = tuple(FRONTEND_PROTOCOL_CONFIGS.keys())
FRONTEND_PROTOCOL_PATTERN = "^(" + "|".join(FRONTEND_PROTOCOLS) + ")$"
IMPLEMENTATION_PROTOCOLS = (
    OPENAI_PROTOCOL,
    OPENAI_RESPONSES_PROTOCOL,
    ANTHROPIC_PROTOCOL,
    GEMINI_PROTOCOL,
)


def normalize_frontend_protocol(protocol: str | None) -> str:
    return (protocol or OPENAI_PROTOCOL).lower().strip()


def get_frontend_protocol_config(protocol: str | None) -> ProtocolConfig:
    normalized = normalize_frontend_protocol(protocol)
    config = FRONTEND_PROTOCOL_CONFIGS.get(normalized)
    if not config:
        raise ServiceError(
            message=f"Unsupported protocol '{protocol}'",
            code="unsupported_protocol",
        )
    return config


def resolve_implementation_protocol(protocol: str | None) -> str:
    return get_frontend_protocol_config(protocol).implementation


def list_frontend_protocol_configs() -> list[ProtocolConfig]:
    return list(FRONTEND_PROTOCOL_CONFIGS.values())
