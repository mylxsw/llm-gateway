"""
API Protocol Converter SDK

A Python library for converting between OpenAI Classic, OpenAI Responses, and Anthropic Messages APIs.
Supports request/response conversion for both streaming and non-streaming modes.
"""

from .converters import (
    convert_request,
    convert_response,
    convert_stream,
    # OpenAI Classic to others
    openai_chat_to_openai_responses_request,
    openai_chat_to_openai_responses_response,
    openai_chat_to_anthropic_messages_request,
    openai_chat_to_anthropic_messages_response,
    # OpenAI Responses to others
    openai_responses_to_openai_chat_request,
    openai_responses_to_openai_chat_response,
    openai_responses_to_anthropic_messages_request,
    openai_responses_to_anthropic_messages_response,
    # Anthropic Messages to others
    anthropic_messages_to_openai_chat_request,
    anthropic_messages_to_openai_chat_response,
    anthropic_messages_to_openai_responses_request,
    anthropic_messages_to_openai_responses_response,
)

from .ir import (
    IRRequest,
    IRResponse,
    IRMessage,
    IRContentBlock,
    IRToolDeclaration,
    IRUsage,
)

from .schemas import Protocol

__version__ = "0.1.0"
__all__ = [
    # Generic converters
    "convert_request",
    "convert_response",
    "convert_stream",
    # OpenAI Classic converters
    "openai_chat_to_openai_responses_request",
    "openai_chat_to_openai_responses_response",
    "openai_chat_to_anthropic_messages_request",
    "openai_chat_to_anthropic_messages_response",
    # OpenAI Responses converters
    "openai_responses_to_openai_chat_request",
    "openai_responses_to_openai_chat_response",
    "openai_responses_to_anthropic_messages_request",
    "openai_responses_to_anthropic_messages_response",
    # Anthropic Messages converters
    "anthropic_messages_to_openai_chat_request",
    "anthropic_messages_to_openai_chat_response",
    "anthropic_messages_to_openai_responses_request",
    "anthropic_messages_to_openai_responses_response",
    # IR types
    "IRRequest",
    "IRResponse",
    "IRMessage",
    "IRContentBlock",
    "IRToolDeclaration",
    "IRUsage",
    # Enums
    "Protocol",
]
