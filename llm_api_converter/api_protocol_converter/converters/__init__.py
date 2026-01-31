"""
Protocol Converters Module

Provides functions for converting between different LLM API protocols.
Supports all 6 conversion directions for requests, responses, and streams.
"""

from typing import Any, Dict, Iterator, List, Optional, Union

from ..ir import IRRequest, IRResponse, IRStreamEvent
from ..schemas import Protocol

from .openai_chat import (
    OpenAIChatEncoder,
    OpenAIChatDecoder,
)
from .openai_responses import (
    OpenAIResponsesEncoder,
    OpenAIResponsesDecoder,
)
from .anthropic_messages import (
    AnthropicMessagesEncoder,
    AnthropicMessagesDecoder,
)
from .exceptions import (
    ConversionError,
    CapabilityNotSupportedError,
    ValidationError,
)


# Encoder/Decoder registry
_ENCODERS = {
    Protocol.OPENAI_CHAT: OpenAIChatEncoder(),
    Protocol.OPENAI_RESPONSES: OpenAIResponsesEncoder(),
    Protocol.ANTHROPIC_MESSAGES: AnthropicMessagesEncoder(),
}

_DECODERS = {
    Protocol.OPENAI_CHAT: OpenAIChatDecoder(),
    Protocol.OPENAI_RESPONSES: OpenAIResponsesDecoder(),
    Protocol.ANTHROPIC_MESSAGES: AnthropicMessagesDecoder(),
}

def _apply_default_parameters(
    ir_request: IRRequest, options: Dict[str, Any]
) -> None:
    default_params = options.get("default_parameters")
    if not isinstance(default_params, dict):
        return

    config = ir_request.generation_config
    mapping = {
        "temperature": "temperature",
        "top_p": "top_p",
        "top_k": "top_k",
        "max_tokens": "max_tokens",
    }
    for key, attr in mapping.items():
        if key not in default_params:
            continue
        if getattr(config, attr) is not None:
            continue
        setattr(config, attr, default_params[key])


def _get_protocol(protocol: Union[Protocol, str]) -> Protocol:
    """Convert string to Protocol enum if needed."""
    if isinstance(protocol, str):
        protocol_map = {
            "openai_chat": Protocol.OPENAI_CHAT,
            "openai_classic": Protocol.OPENAI_CHAT,
            "openai_responses": Protocol.OPENAI_RESPONSES,
            "anthropic_messages": Protocol.ANTHROPIC_MESSAGES,
            "anthropic": Protocol.ANTHROPIC_MESSAGES,
        }
        return protocol_map.get(protocol.lower(), Protocol(protocol))
    return protocol


# =============================================================================
# Generic Conversion Functions
# =============================================================================

def convert_request(
    source_protocol: Union[Protocol, str],
    target_protocol: Union[Protocol, str],
    payload: Dict[str, Any],
    *,
    stream: bool = False,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert a request from source protocol to target protocol.

    Args:
        source_protocol: The source API protocol
        target_protocol: The target API protocol
        payload: The request payload in source format
        stream: Whether this is a streaming request
        options: Optional conversion options

    Returns:
        The converted request payload in target format

    Raises:
        ConversionError: If conversion fails
        CapabilityNotSupportedError: If target protocol doesn't support a required feature
    """
    source = _get_protocol(source_protocol)
    target = _get_protocol(target_protocol)
    options = options or {}

    # Decode to IR
    decoder = _DECODERS[source]
    ir_request = decoder.decode_request(payload)

    # Set stream flag
    ir_request.stream = stream
    _apply_default_parameters(ir_request, options)

    # Encode to target
    encoder = _ENCODERS[target]
    return encoder.encode_request(ir_request, options=options)


def convert_response(
    source_protocol: Union[Protocol, str],
    target_protocol: Union[Protocol, str],
    payload: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert a response from source protocol to target protocol.

    Args:
        source_protocol: The source API protocol
        target_protocol: The target API protocol
        payload: The response payload in source format
        options: Optional conversion options

    Returns:
        The converted response payload in target format

    Raises:
        ConversionError: If conversion fails
    """
    source = _get_protocol(source_protocol)
    target = _get_protocol(target_protocol)
    options = options or {}

    # Decode to IR
    decoder = _DECODERS[source]
    ir_response = decoder.decode_response(payload)

    # Encode to target
    encoder = _ENCODERS[target]
    return encoder.encode_response(ir_response, options=options)


def convert_stream(
    source_protocol: Union[Protocol, str],
    target_protocol: Union[Protocol, str],
    events: Iterator[Union[Dict[str, Any], str]],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Iterator[Union[Dict[str, Any], str]]:
    """
    Convert a stream of events from source protocol to target protocol.

    Args:
        source_protocol: The source API protocol
        target_protocol: The target API protocol
        events: Iterator of source protocol events (dict or SSE text lines)
        options: Optional conversion options

    Yields:
        Converted events in target protocol format

    Raises:
        ConversionError: If conversion fails
    """
    source = _get_protocol(source_protocol)
    target = _get_protocol(target_protocol)
    options = options or {}

    decoder = _DECODERS[source]
    encoder = _ENCODERS[target]

    # Convert events through IR
    for event in events:
        # Decode to IR events
        ir_events = decoder.decode_stream_event(event)

        # Encode each IR event to target format
        for ir_event in ir_events:
            target_events = encoder.encode_stream_event(ir_event, options=options)
            yield from target_events


# =============================================================================
# OpenAI Classic to Others
# =============================================================================

def openai_chat_to_openai_responses_request(
    payload: Dict[str, Any],
    *,
    stream: bool = False,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert OpenAI Chat Completions request to OpenAI Responses request."""
    return convert_request(
        Protocol.OPENAI_CHAT,
        Protocol.OPENAI_RESPONSES,
        payload,
        stream=stream,
        options=options,
    )


def openai_chat_to_openai_responses_response(
    payload: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert OpenAI Chat Completions response to OpenAI Responses response."""
    return convert_response(
        Protocol.OPENAI_CHAT,
        Protocol.OPENAI_RESPONSES,
        payload,
        options=options,
    )


def openai_chat_to_anthropic_messages_request(
    payload: Dict[str, Any],
    *,
    stream: bool = False,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert OpenAI Chat Completions request to Anthropic Messages request."""
    return convert_request(
        Protocol.OPENAI_CHAT,
        Protocol.ANTHROPIC_MESSAGES,
        payload,
        stream=stream,
        options=options,
    )


def openai_chat_to_anthropic_messages_response(
    payload: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert OpenAI Chat Completions response to Anthropic Messages response."""
    return convert_response(
        Protocol.OPENAI_CHAT,
        Protocol.ANTHROPIC_MESSAGES,
        payload,
        options=options,
    )


def openai_chat_to_openai_responses_stream(
    events: Iterator[Union[Dict[str, Any], str]],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Iterator[Union[Dict[str, Any], str]]:
    """Convert OpenAI Chat Completions stream to OpenAI Responses stream."""
    return convert_stream(
        Protocol.OPENAI_CHAT,
        Protocol.OPENAI_RESPONSES,
        events,
        options=options,
    )


def openai_chat_to_anthropic_messages_stream(
    events: Iterator[Union[Dict[str, Any], str]],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Iterator[Union[Dict[str, Any], str]]:
    """Convert OpenAI Chat Completions stream to Anthropic Messages stream."""
    return convert_stream(
        Protocol.OPENAI_CHAT,
        Protocol.ANTHROPIC_MESSAGES,
        events,
        options=options,
    )


# =============================================================================
# OpenAI Responses to Others
# =============================================================================

def openai_responses_to_openai_chat_request(
    payload: Dict[str, Any],
    *,
    stream: bool = False,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert OpenAI Responses request to OpenAI Chat Completions request."""
    return convert_request(
        Protocol.OPENAI_RESPONSES,
        Protocol.OPENAI_CHAT,
        payload,
        stream=stream,
        options=options,
    )


def openai_responses_to_openai_chat_response(
    payload: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert OpenAI Responses response to OpenAI Chat Completions response."""
    return convert_response(
        Protocol.OPENAI_RESPONSES,
        Protocol.OPENAI_CHAT,
        payload,
        options=options,
    )


def openai_responses_to_anthropic_messages_request(
    payload: Dict[str, Any],
    *,
    stream: bool = False,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert OpenAI Responses request to Anthropic Messages request."""
    return convert_request(
        Protocol.OPENAI_RESPONSES,
        Protocol.ANTHROPIC_MESSAGES,
        payload,
        stream=stream,
        options=options,
    )


def openai_responses_to_anthropic_messages_response(
    payload: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert OpenAI Responses response to Anthropic Messages response."""
    return convert_response(
        Protocol.OPENAI_RESPONSES,
        Protocol.ANTHROPIC_MESSAGES,
        payload,
        options=options,
    )


def openai_responses_to_openai_chat_stream(
    events: Iterator[Union[Dict[str, Any], str]],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Iterator[Union[Dict[str, Any], str]]:
    """Convert OpenAI Responses stream to OpenAI Chat Completions stream."""
    return convert_stream(
        Protocol.OPENAI_RESPONSES,
        Protocol.OPENAI_CHAT,
        events,
        options=options,
    )


def openai_responses_to_anthropic_messages_stream(
    events: Iterator[Union[Dict[str, Any], str]],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Iterator[Union[Dict[str, Any], str]]:
    """Convert OpenAI Responses stream to Anthropic Messages stream."""
    return convert_stream(
        Protocol.OPENAI_RESPONSES,
        Protocol.ANTHROPIC_MESSAGES,
        events,
        options=options,
    )


# =============================================================================
# Anthropic Messages to Others
# =============================================================================

def anthropic_messages_to_openai_chat_request(
    payload: Dict[str, Any],
    *,
    stream: bool = False,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert Anthropic Messages request to OpenAI Chat Completions request."""
    return convert_request(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_CHAT,
        payload,
        stream=stream,
        options=options,
    )


def anthropic_messages_to_openai_chat_response(
    payload: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert Anthropic Messages response to OpenAI Chat Completions response."""
    return convert_response(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_CHAT,
        payload,
        options=options,
    )


def anthropic_messages_to_openai_responses_request(
    payload: Dict[str, Any],
    *,
    stream: bool = False,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert Anthropic Messages request to OpenAI Responses request."""
    return convert_request(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_RESPONSES,
        payload,
        stream=stream,
        options=options,
    )


def anthropic_messages_to_openai_responses_response(
    payload: Dict[str, Any],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert Anthropic Messages response to OpenAI Responses response."""
    return convert_response(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_RESPONSES,
        payload,
        options=options,
    )


def anthropic_messages_to_openai_chat_stream(
    events: Iterator[Union[Dict[str, Any], str]],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Iterator[Union[Dict[str, Any], str]]:
    """Convert Anthropic Messages stream to OpenAI Chat Completions stream."""
    return convert_stream(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_CHAT,
        events,
        options=options,
    )


def anthropic_messages_to_openai_responses_stream(
    events: Iterator[Union[Dict[str, Any], str]],
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Iterator[Union[Dict[str, Any], str]]:
    """Convert Anthropic Messages stream to OpenAI Responses stream."""
    return convert_stream(
        Protocol.ANTHROPIC_MESSAGES,
        Protocol.OPENAI_RESPONSES,
        events,
        options=options,
    )


__all__ = [
    # Generic converters
    "convert_request",
    "convert_response",
    "convert_stream",
    # OpenAI Chat converters
    "openai_chat_to_openai_responses_request",
    "openai_chat_to_openai_responses_response",
    "openai_chat_to_openai_responses_stream",
    "openai_chat_to_anthropic_messages_request",
    "openai_chat_to_anthropic_messages_response",
    "openai_chat_to_anthropic_messages_stream",
    # OpenAI Responses converters
    "openai_responses_to_openai_chat_request",
    "openai_responses_to_openai_chat_response",
    "openai_responses_to_openai_chat_stream",
    "openai_responses_to_anthropic_messages_request",
    "openai_responses_to_anthropic_messages_response",
    "openai_responses_to_anthropic_messages_stream",
    # Anthropic Messages converters
    "anthropic_messages_to_openai_chat_request",
    "anthropic_messages_to_openai_chat_response",
    "anthropic_messages_to_openai_chat_stream",
    "anthropic_messages_to_openai_responses_request",
    "anthropic_messages_to_openai_responses_response",
    "anthropic_messages_to_openai_responses_stream",
    # Encoder/Decoder classes
    "OpenAIChatEncoder",
    "OpenAIChatDecoder",
    "OpenAIResponsesEncoder",
    "OpenAIResponsesDecoder",
    "AnthropicMessagesEncoder",
    "AnthropicMessagesDecoder",
    # Exceptions
    "ConversionError",
    "CapabilityNotSupportedError",
    "ValidationError",
]
