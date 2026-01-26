"""
Protocol Converter Registry

Manages registration and lookup of protocol converters.
Implements a factory pattern for converter instantiation.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Tuple, Type

from .base import (
    Protocol,
    IRequestConverter,
    IResponseConverter,
    IStreamConverter,
    IProtocolAdapter,
    ConversionResult,
    UnsupportedConversionError,
)

logger = logging.getLogger(__name__)


class ConverterRegistry:
    """
    Registry for protocol converters.

    Manages converter instances and provides lookup by protocol pairs.
    Uses lazy initialization for converter instances.
    """

    _instance: Optional["ConverterRegistry"] = None

    def __init__(self):
        self._request_converters: Dict[Tuple[Protocol, Protocol], IRequestConverter] = {}
        self._response_converters: Dict[Tuple[Protocol, Protocol], IResponseConverter] = {}
        self._stream_converters: Dict[Tuple[Protocol, Protocol], IStreamConverter] = {}
        self._adapters: Dict[Protocol, IProtocolAdapter] = {}

    @classmethod
    def get_instance(cls) -> "ConverterRegistry":
        """Get singleton instance of the registry."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None

    def register_adapter(self, adapter: IProtocolAdapter) -> None:
        """
        Register a protocol adapter.

        Args:
            adapter: The adapter instance to register
        """
        self._adapters[adapter.protocol] = adapter
        logger.debug(f"Registered adapter for protocol: {adapter.protocol.value}")

    def register_request_converter(self, converter: IRequestConverter) -> None:
        """
        Register a request converter.

        Args:
            converter: The converter instance to register
        """
        key = (converter.source_protocol, converter.target_protocol)
        self._request_converters[key] = converter
        logger.debug(
            f"Registered request converter: {key[0].value} -> {key[1].value}"
        )

    def register_response_converter(self, converter: IResponseConverter) -> None:
        """
        Register a response converter.

        Args:
            converter: The converter instance to register
        """
        key = (converter.source_protocol, converter.target_protocol)
        self._response_converters[key] = converter
        logger.debug(
            f"Registered response converter: {key[0].value} -> {key[1].value}"
        )

    def register_stream_converter(self, converter: IStreamConverter) -> None:
        """
        Register a stream converter.

        Args:
            converter: The converter instance to register
        """
        key = (converter.source_protocol, converter.target_protocol)
        self._stream_converters[key] = converter
        logger.debug(
            f"Registered stream converter: {key[0].value} -> {key[1].value}"
        )

    def get_adapter(self, protocol: Protocol) -> Optional[IProtocolAdapter]:
        """
        Get adapter for a protocol.

        Args:
            protocol: The protocol to get adapter for

        Returns:
            The adapter or None if not found
        """
        return self._adapters.get(protocol)

    def get_request_converter(
        self,
        source: Protocol,
        target: Protocol,
    ) -> Optional[IRequestConverter]:
        """
        Get a request converter for a protocol pair.

        Args:
            source: Source protocol
            target: Target protocol

        Returns:
            The converter or None if not found
        """
        return self._request_converters.get((source, target))

    def get_response_converter(
        self,
        source: Protocol,
        target: Protocol,
    ) -> Optional[IResponseConverter]:
        """
        Get a response converter for a protocol pair.

        Args:
            source: Source protocol (supplier)
            target: Target protocol (user expects)

        Returns:
            The converter or None if not found
        """
        return self._response_converters.get((source, target))

    def get_stream_converter(
        self,
        source: Protocol,
        target: Protocol,
    ) -> Optional[IStreamConverter]:
        """
        Get a stream converter for a protocol pair.

        Args:
            source: Source protocol (supplier)
            target: Target protocol (user expects)

        Returns:
            The converter or None if not found
        """
        return self._stream_converters.get((source, target))

    def list_supported_conversions(self) -> Dict[str, list]:
        """
        List all supported conversion paths.

        Returns:
            Dictionary with 'request', 'response', 'stream' keys
            containing lists of (source, target) tuples
        """
        return {
            "request": [
                (s.value, t.value) for s, t in self._request_converters.keys()
            ],
            "response": [
                (s.value, t.value) for s, t in self._response_converters.keys()
            ],
            "stream": [
                (s.value, t.value) for s, t in self._stream_converters.keys()
            ],
        }


class ProtocolConverterManager:
    """
    High-level manager for protocol conversions.

    Provides a unified interface for converting requests, responses,
    and streams between protocols.
    """

    def __init__(self, registry: Optional[ConverterRegistry] = None):
        """
        Initialize the manager.

        Args:
            registry: Optional custom registry. Uses singleton if not provided.
        """
        self._registry = registry or ConverterRegistry.get_instance()

    def convert_request(
        self,
        source_protocol: Protocol,
        target_protocol: Protocol,
        path: str,
        body: Dict[str, Any],
        target_model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """
        Convert a request from source to target protocol.

        Args:
            source_protocol: Protocol of the incoming request
            target_protocol: Protocol for the outgoing request
            path: Original request path
            body: Request body
            target_model: Target model name
            options: Optional conversion options

        Returns:
            ConversionResult with converted path and body

        Raises:
            UnsupportedConversionError: If conversion is not supported
        """
        if source_protocol == target_protocol:
            return self._identity_request_conversion(
                protocol=source_protocol,
                path=path,
                body=body,
                target_model=target_model,
            )

        converter = self._registry.get_request_converter(source_protocol, target_protocol)
        if converter is None:
            raise UnsupportedConversionError(
                source_protocol=source_protocol.value,
                target_protocol=target_protocol.value,
            )

        return converter.convert(path, body, target_model, options=options)

    def convert_response(
        self,
        source_protocol: Protocol,
        target_protocol: Protocol,
        body: Dict[str, Any],
        target_model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convert a response from source to target protocol.

        Args:
            source_protocol: Protocol of the supplier response
            target_protocol: Protocol the user expects
            body: Response body
            target_model: Target model name
            options: Optional conversion options

        Returns:
            Converted response body

        Raises:
            UnsupportedConversionError: If conversion is not supported
        """
        if source_protocol == target_protocol:
            return body

        converter = self._registry.get_response_converter(source_protocol, target_protocol)
        if converter is None:
            raise UnsupportedConversionError(
                source_protocol=source_protocol.value,
                target_protocol=target_protocol.value,
            )

        return converter.convert(body, target_model, options=options)

    async def convert_stream(
        self,
        source_protocol: Protocol,
        target_protocol: Protocol,
        upstream: AsyncGenerator[bytes, None],
        model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Convert a streaming response from source to target protocol.

        Args:
            source_protocol: Protocol of the supplier stream
            target_protocol: Protocol the user expects
            upstream: Upstream byte stream
            model: Model name
            options: Optional conversion options

        Yields:
            Converted SSE bytes

        Raises:
            UnsupportedConversionError: If conversion is not supported
        """
        if source_protocol == target_protocol:
            async for chunk in upstream:
                yield chunk
            return

        converter = self._registry.get_stream_converter(source_protocol, target_protocol)
        if converter is None:
            raise UnsupportedConversionError(
                source_protocol=source_protocol.value,
                target_protocol=target_protocol.value,
            )

        async for chunk in converter.convert(upstream, model, options=options):
            yield chunk

    def _identity_request_conversion(
        self,
        protocol: Protocol,
        path: str,
        body: Dict[str, Any],
        target_model: str,
    ) -> ConversionResult:
        """
        Handle identity conversion (same protocol).

        Normalizes the request and updates the model field.
        Also normalizes legacy OpenAI function-calling fields.
        """
        import copy
        from typing import List

        new_body = copy.deepcopy(body)
        new_body["model"] = target_model

        # Normalize OpenAI legacy functions to tools
        if protocol == Protocol.OPENAI:
            new_body = self._normalize_openai_tooling_fields(new_body)

        # Ensure max_tokens for Anthropic
        if protocol == Protocol.ANTHROPIC and path == "/v1/messages":
            if new_body.get("max_tokens") is None:
                if new_body.get("max_completion_tokens") is not None:
                    new_body["max_tokens"] = new_body["max_completion_tokens"]
                else:
                    new_body["max_tokens"] = 4096

        return ConversionResult(path=path, body=new_body)

    def _normalize_openai_tooling_fields(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize legacy OpenAI function-calling fields to modern tool-calling fields.

        - functions -> tools
        - function_call -> tool_choice
        """
        out = body  # Already a copy

        # Legacy: functions + function_call -> tools + tool_choice
        if "tools" not in out and isinstance(out.get("functions"), list):
            tools: List[Dict[str, Any]] = []
            for fn in out["functions"]:
                if not isinstance(fn, dict):
                    continue
                name = fn.get("name")
                if not isinstance(name, str) or not name:
                    continue
                tool: Dict[str, Any] = {"type": "function", "function": {}}
                tool_fn = tool["function"]
                tool_fn["name"] = name
                if isinstance(fn.get("description"), str):
                    tool_fn["description"] = fn.get("description")
                if isinstance(fn.get("parameters"), dict):
                    tool_fn["parameters"] = fn.get("parameters")
                tools.append(tool)
            if tools:
                out["tools"] = tools
                # Remove deprecated functions field
                del out["functions"]

        if "tool_choice" not in out and "function_call" in out:
            fc = out.get("function_call")
            if isinstance(fc, str):
                out["tool_choice"] = fc
            elif isinstance(fc, dict):
                name = fc.get("name")
                if isinstance(name, str) and name:
                    out["tool_choice"] = {"type": "function", "function": {"name": name}}
            # Remove deprecated function_call field
            del out["function_call"]

        return out
