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


# Model type that must be served by the Jev protocol. The model type and the
# protocol deliberately share the name: a Jev model is exactly a model served
# over the Jev protocol.
JEV_MODEL_TYPE = JEV_PROTOCOL


def normalize_model_type(model_type: str | None) -> str:
    return (model_type or "chat").lower().strip()


def is_model_type_protocol_compatible(
    model_type: str | None, protocol: str | None
) -> bool:
    """Whether a model of ``model_type`` may be served by a ``protocol`` provider.

    Jev has no conversion path to or from the chat-oriented protocols, so a Jev
    model must be bound to a Jev provider and a Jev provider must only serve Jev
    models. Every other combination stays unconstrained, matching the gateway's
    existing freedom to serve e.g. an embedding model over any chat protocol.
    """
    try:
        implementation = resolve_implementation_protocol(protocol)
    except ServiceError:
        # An unknown protocol cannot be a Jev provider; report the mismatch
        # rather than raising, so callers get the clearer validation error.
        implementation = normalize_frontend_protocol(protocol)

    is_jev_model = normalize_model_type(model_type) == JEV_MODEL_TYPE
    is_jev_protocol = implementation == JEV_PROTOCOL
    return is_jev_model == is_jev_protocol


def model_type_protocol_mismatch_message(
    model_type: str | None, protocol: str | None, provider_name: str | None = None
) -> str:
    """Human-readable explanation for an incompatible model/provider pairing."""
    normalized_type = normalize_model_type(model_type)
    normalized_protocol = normalize_frontend_protocol(protocol)
    provider_label = f"provider '{provider_name}'" if provider_name else "the provider"

    if normalized_type == JEV_MODEL_TYPE:
        return (
            f"Model type '{JEV_MODEL_TYPE}' requires a provider using the "
            f"'{JEV_PROTOCOL}' protocol, but {provider_label} uses "
            f"'{normalized_protocol}'"
        )
    return (
        f"The selected {provider_label} uses the '{normalized_protocol}' "
        f"protocol, which can only serve models of type '{JEV_MODEL_TYPE}' "
        f"(this model is '{normalized_type}')"
    )
