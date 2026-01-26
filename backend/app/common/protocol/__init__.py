"""
Protocol Conversion Module

Provides a unified interface for converting requests, responses,
and streams between different LLM API protocols.

Supported protocols:
- OpenAI Chat Completions (openai)
- OpenAI Responses API (openai_responses)
- Anthropic Messages API (anthropic)

Example usage:
    from app.common.protocol import (
        convert_request,
        convert_response,
        convert_stream,
        Protocol,
    )

    # Convert request
    result = convert_request(
        source_protocol="openai",
        target_protocol="anthropic",
        path="/v1/chat/completions",
        body=request_body,
        target_model="claude-3-5-sonnet-20241022",
    )

    # Convert response
    converted = convert_response(
        source_protocol="anthropic",
        target_protocol="openai",
        body=response_body,
        target_model="claude-3-5-sonnet-20241022",
    )

    # Convert stream
    async for chunk in convert_stream(
        source_protocol="anthropic",
        target_protocol="openai",
        upstream=upstream_generator,
        model="claude-3-5-sonnet-20241022",
    ):
        yield chunk
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, Optional

from .base import (
    Protocol,
    ConversionContext,
    ConversionResult,
    ProtocolConversionError,
    UnsupportedConversionError,
    ValidationError,
    IRequestConverter,
    IResponseConverter,
    IStreamConverter,
    IProtocolAdapter,
)
from .registry import (
    ConverterRegistry,
    ProtocolConverterManager,
)
from .converters import (
    SDKRequestConverter,
    SDKResponseConverter,
    SDKStreamConverter,
)

logger = logging.getLogger(__name__)

# Global registry and manager instances
_registry: Optional[ConverterRegistry] = None
_manager: Optional[ProtocolConverterManager] = None


def _get_registry() -> ConverterRegistry:
    """Get or create the global registry instance."""
    global _registry
    if _registry is None:
        _registry = ConverterRegistry()
        _register_all_converters(_registry)
    return _registry


def _get_manager() -> ProtocolConverterManager:
    """Get or create the global manager instance."""
    global _manager
    if _manager is None:
        _manager = ProtocolConverterManager(_get_registry())
    return _manager


def _register_all_converters(registry: ConverterRegistry) -> None:
    """Register all supported converters."""
    # Request converters
    # OpenAI <-> Anthropic
    registry.register_request_converter(
        SDKRequestConverter(Protocol.OPENAI, Protocol.ANTHROPIC)
    )
    registry.register_request_converter(
        SDKRequestConverter(Protocol.ANTHROPIC, Protocol.OPENAI)
    )

    # OpenAI <-> OpenAI Responses
    registry.register_request_converter(
        SDKRequestConverter(Protocol.OPENAI, Protocol.OPENAI_RESPONSES)
    )
    registry.register_request_converter(
        SDKRequestConverter(Protocol.OPENAI_RESPONSES, Protocol.OPENAI)
    )

    # OpenAI Responses <-> Anthropic
    registry.register_request_converter(
        SDKRequestConverter(Protocol.OPENAI_RESPONSES, Protocol.ANTHROPIC)
    )
    registry.register_request_converter(
        SDKRequestConverter(Protocol.ANTHROPIC, Protocol.OPENAI_RESPONSES)
    )

    # Response converters
    # OpenAI <-> Anthropic
    registry.register_response_converter(
        SDKResponseConverter(Protocol.OPENAI, Protocol.ANTHROPIC)
    )
    registry.register_response_converter(
        SDKResponseConverter(Protocol.ANTHROPIC, Protocol.OPENAI)
    )

    # OpenAI <-> OpenAI Responses
    registry.register_response_converter(
        SDKResponseConverter(Protocol.OPENAI, Protocol.OPENAI_RESPONSES)
    )
    registry.register_response_converter(
        SDKResponseConverter(Protocol.OPENAI_RESPONSES, Protocol.OPENAI)
    )

    # OpenAI Responses <-> Anthropic
    registry.register_response_converter(
        SDKResponseConverter(Protocol.OPENAI_RESPONSES, Protocol.ANTHROPIC)
    )
    registry.register_response_converter(
        SDKResponseConverter(Protocol.ANTHROPIC, Protocol.OPENAI_RESPONSES)
    )

    # Stream converters
    # OpenAI <-> Anthropic
    registry.register_stream_converter(
        SDKStreamConverter(Protocol.OPENAI, Protocol.ANTHROPIC)
    )
    registry.register_stream_converter(
        SDKStreamConverter(Protocol.ANTHROPIC, Protocol.OPENAI)
    )

    # OpenAI <-> OpenAI Responses
    registry.register_stream_converter(
        SDKStreamConverter(Protocol.OPENAI, Protocol.OPENAI_RESPONSES)
    )
    registry.register_stream_converter(
        SDKStreamConverter(Protocol.OPENAI_RESPONSES, Protocol.OPENAI)
    )

    # OpenAI Responses <-> Anthropic
    registry.register_stream_converter(
        SDKStreamConverter(Protocol.OPENAI_RESPONSES, Protocol.ANTHROPIC)
    )
    registry.register_stream_converter(
        SDKStreamConverter(Protocol.ANTHROPIC, Protocol.OPENAI_RESPONSES)
    )

    logger.debug("Registered all protocol converters")


def normalize_protocol(protocol: str) -> Protocol:
    """
    Normalize a protocol string to Protocol enum.

    Args:
        protocol: Protocol string (e.g., "openai", "anthropic")

    Returns:
        Protocol enum value

    Raises:
        UnsupportedConversionError: If protocol is not supported
    """
    try:
        return Protocol.from_string(protocol)
    except ValueError as e:
        raise UnsupportedConversionError(
            source_protocol=protocol,
            target_protocol="unknown",
            message=f"Unsupported protocol: {protocol}",
        ) from e


def convert_request(
    source_protocol: str,
    target_protocol: str,
    path: str,
    body: Dict[str, Any],
    target_model: str,
    *,
    options: Optional[Dict[str, Any]] = None,
) -> ConversionResult:
    """
    Convert a request from source protocol to target protocol.

    Args:
        source_protocol: Source protocol name (e.g., "openai")
        target_protocol: Target protocol name (e.g., "anthropic")
        path: Original request path
        body: Request body
        target_model: Target model name
        options: Optional conversion options

    Returns:
        ConversionResult with converted path and body

    Raises:
        UnsupportedConversionError: If conversion is not supported
        ProtocolConversionError: If conversion fails
    """
    source = normalize_protocol(source_protocol)
    target = normalize_protocol(target_protocol)

    manager = _get_manager()
    return manager.convert_request(
        source_protocol=source,
        target_protocol=target,
        path=path,
        body=body,
        target_model=target_model,
        options=options,
    )


def convert_response(
    source_protocol: str,
    target_protocol: str,
    body: Dict[str, Any],
    target_model: str,
    *,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert a response from source protocol to target protocol.

    Args:
        source_protocol: Source protocol name (supplier response)
        target_protocol: Target protocol name (user expects)
        body: Response body
        target_model: Target model name
        options: Optional conversion options

    Returns:
        Converted response body

    Raises:
        UnsupportedConversionError: If conversion is not supported
        ProtocolConversionError: If conversion fails
    """
    source = normalize_protocol(source_protocol)
    target = normalize_protocol(target_protocol)

    manager = _get_manager()
    return manager.convert_response(
        source_protocol=source,
        target_protocol=target,
        body=body,
        target_model=target_model,
        options=options,
    )


async def convert_stream(
    source_protocol: str,
    target_protocol: str,
    upstream: AsyncGenerator[bytes, None],
    model: str,
    *,
    options: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[bytes, None]:
    """
    Convert a streaming response from source protocol to target protocol.

    Args:
        source_protocol: Source protocol name (supplier stream)
        target_protocol: Target protocol name (user expects)
        upstream: Upstream byte stream
        model: Model name
        options: Optional conversion options

    Yields:
        Converted SSE bytes

    Raises:
        UnsupportedConversionError: If conversion is not supported
        ProtocolConversionError: If conversion fails
    """
    source = normalize_protocol(source_protocol)
    target = normalize_protocol(target_protocol)

    manager = _get_manager()
    async for chunk in manager.convert_stream(
        source_protocol=source,
        target_protocol=target,
        upstream=upstream,
        model=model,
        options=options,
    ):
        yield chunk


def reset_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _registry, _manager
    _registry = None
    _manager = None
    # Also reset the ConverterRegistry singleton
    ConverterRegistry.reset()


__all__ = [
    # Main functions
    "convert_request",
    "convert_response",
    "convert_stream",
    "normalize_protocol",
    "reset_registry",
    # Types
    "Protocol",
    "ConversionContext",
    "ConversionResult",
    # Exceptions
    "ProtocolConversionError",
    "UnsupportedConversionError",
    "ValidationError",
    # Interfaces (for extension)
    "IRequestConverter",
    "IResponseConverter",
    "IStreamConverter",
    "IProtocolAdapter",
    # Registry (for advanced usage)
    "ConverterRegistry",
    "ProtocolConverterManager",
]
