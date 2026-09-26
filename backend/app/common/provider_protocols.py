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
JEV_PROTOCOL = "jev"
DEEPSEEK_PROTOCOL = "deepseek"
ZHIPU_PROTOCOL = "zhipu"
MOONSHOT_PROTOCOL = "moonshot"
ALIYUN_PROTOCOL = "aliyun"
ARK_PROTOCOL = "ark"
DEEPSEEK_COMPATIBLE_THINKING_PROTOCOLS = (
    DEEPSEEK_PROTOCOL,
    ZHIPU_PROTOCOL,
    MOONSHOT_PROTOCOL,
    ARK_PROTOCOL,
)
DASHSCOPE_THINKING_PROTOCOLS = (ALIYUN_PROTOCOL,)


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
    JEV_PROTOCOL: ProtocolConfig(
        frontend=JEV_PROTOCOL,
        implementation=JEV_PROTOCOL,
        base_url="https://api.typesafe.ai/v1",
        label="TypeSafe Jev",
    ),
    "deepseek": ProtocolConfig(
        frontend="deepseek",
        implementation=OPENAI_PROTOCOL,
        base_url="https://api.deepseek.com",
        label="DeepSeek (OpenAI)",
    ),
    ZHIPU_PROTOCOL: ProtocolConfig(
        frontend=ZHIPU_PROTOCOL,
        implementation=OPENAI_PROTOCOL,
        base_url="https://open.bigmodel.cn/api/paas/v4",
        label="GLM (OpenAI)",
    ),
    ALIYUN_PROTOCOL: ProtocolConfig(
        frontend=ALIYUN_PROTOCOL,
        implementation=OPENAI_PROTOCOL,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        label="Dashscope (OpenAI)",
    ),
    MOONSHOT_PROTOCOL: ProtocolConfig(
        frontend=MOONSHOT_PROTOCOL,
        implementation=OPENAI_PROTOCOL,
        base_url="https://api.moonshot.cn/v1",
        label="Kimi (OpenAI)",
    ),
    ARK_PROTOCOL: ProtocolConfig(
        frontend=ARK_PROTOCOL,
        implementation=OPENAI_PROTOCOL,
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        label="Ark (OpenAI)",
    ),
}

FRONTEND_PROTOCOLS = tuple(FRONTEND_PROTOCOL_CONFIGS.keys())
FRONTEND_PROTOCOL_PATTERN = "^(" + "|".join(FRONTEND_PROTOCOLS) + ")$"
IMPLEMENTATION_PROTOCOLS = (
    OPENAI_PROTOCOL,
    OPENAI_RESPONSES_PROTOCOL,
    ANTHROPIC_PROTOCOL,
    GEMINI_PROTOCOL,
    JEV_PROTOCOL,
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


def uses_deepseek_compatible_thinking(protocol: str | None) -> bool:
    return normalize_frontend_protocol(protocol) in DEEPSEEK_COMPATIBLE_THINKING_PROTOCOLS


def uses_dashscope_thinking(protocol: str | None) -> bool:
    return normalize_frontend_protocol(protocol) in DASHSCOPE_THINKING_PROTOCOLS


def list_frontend_protocol_configs() -> list[ProtocolConfig]:
    return list(FRONTEND_PROTOCOL_CONFIGS.values())
