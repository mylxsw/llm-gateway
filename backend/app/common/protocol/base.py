"""
Protocol Converter Base Classes

Defines the abstract interface for protocol converters.
Follows the Strategy pattern for extensibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union


class Protocol(str, Enum):
    """Supported API protocols."""
    OPENAI = "openai"
    OPENAI_RESPONSES = "openai_responses"
    ANTHROPIC = "anthropic"

    @classmethod
    def from_string(cls, value: str) -> "Protocol":
        """Convert string to Protocol enum with normalization."""
        normalized = value.lower().strip()
        mapping = {
            "openai": cls.OPENAI,
            "openai_chat": cls.OPENAI,
            "openai_classic": cls.OPENAI,
            "openai_responses": cls.OPENAI_RESPONSES,
            "anthropic": cls.ANTHROPIC,
            "anthropic_messages": cls.ANTHROPIC,
        }
        if normalized in mapping:
            return mapping[normalized]
        raise ValueError(f"Unknown protocol: {value}")


@dataclass
class ConversionContext:
    """Context for protocol conversion operations."""
    source_protocol: Protocol
    target_protocol: Protocol
    target_model: str
    path: str = ""
    stream: bool = False
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionResult:
    """Result of a protocol conversion."""
    path: str
    body: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)


class ProtocolConversionError(Exception):
    """Base exception for protocol conversion errors."""

    def __init__(
        self,
        message: str,
        code: str = "conversion_error",
        source_protocol: Optional[str] = None,
        target_protocol: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.source_protocol = source_protocol
        self.target_protocol = target_protocol


class UnsupportedConversionError(ProtocolConversionError):
    """Raised when a conversion path is not supported."""

    def __init__(
        self,
        source_protocol: str,
        target_protocol: str,
        message: Optional[str] = None,
    ):
        msg = message or f"Unsupported protocol conversion: {source_protocol} -> {target_protocol}"
        super().__init__(
            message=msg,
            code="unsupported_protocol_conversion",
            source_protocol=source_protocol,
            target_protocol=target_protocol,
        )


class ValidationError(ProtocolConversionError):
    """Raised when request/response validation fails."""

    def __init__(self, field: str, message: str, expected: Optional[str] = None):
        super().__init__(
            message=f"Validation error for '{field}': {message}",
            code="validation_error",
        )
        self.field = field
        self.expected = expected


class IRequestConverter(ABC):
    """Abstract interface for request conversion."""

    @property
    @abstractmethod
    def source_protocol(self) -> Protocol:
        """The source protocol this converter handles."""
        pass

    @property
    @abstractmethod
    def target_protocol(self) -> Protocol:
        """The target protocol this converter produces."""
        pass

    @abstractmethod
    def convert(
        self,
        path: str,
        body: Dict[str, Any],
        target_model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """
        Convert a request from source protocol to target protocol.

        Args:
            path: Original request path
            body: Request body in source protocol format
            target_model: Target model name for the converted request
            options: Optional conversion options

        Returns:
            ConversionResult with converted path and body

        Raises:
            ProtocolConversionError: If conversion fails
        """
        pass

    @abstractmethod
    def get_target_path(self, source_path: str) -> str:
        """
        Get the target API path for the converted request.

        Args:
            source_path: Original request path

        Returns:
            Target API path
        """
        pass


class IResponseConverter(ABC):
    """Abstract interface for response conversion."""

    @property
    @abstractmethod
    def source_protocol(self) -> Protocol:
        """The source protocol (supplier response)."""
        pass

    @property
    @abstractmethod
    def target_protocol(self) -> Protocol:
        """The target protocol (user expects)."""
        pass

    @abstractmethod
    def convert(
        self,
        body: Dict[str, Any],
        target_model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convert a response from source protocol to target protocol.

        Args:
            body: Response body in source protocol format
            target_model: Target model name
            options: Optional conversion options

        Returns:
            Converted response body

        Raises:
            ProtocolConversionError: If conversion fails
        """
        pass


class IStreamConverter(ABC):
    """Abstract interface for streaming response conversion."""

    @property
    @abstractmethod
    def source_protocol(self) -> Protocol:
        """The source protocol (supplier stream)."""
        pass

    @property
    @abstractmethod
    def target_protocol(self) -> Protocol:
        """The target protocol (user expects)."""
        pass

    @abstractmethod
    async def convert(
        self,
        upstream: AsyncGenerator[bytes, None],
        model: str,
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Convert a streaming response from source protocol to target protocol.

        Args:
            upstream: Async generator yielding bytes from upstream provider
            model: Model name for the response
            options: Optional conversion options

        Yields:
            Converted SSE bytes in target protocol format

        Raises:
            ProtocolConversionError: If conversion fails
        """
        pass


class IProtocolAdapter(ABC):
    """
    Unified adapter interface for a specific protocol.

    Each protocol implements this adapter to provide encoding/decoding
    capabilities for requests, responses, and streams.
    """

    @property
    @abstractmethod
    def protocol(self) -> Protocol:
        """The protocol this adapter handles."""
        pass

    @property
    @abstractmethod
    def default_path(self) -> str:
        """Default API path for this protocol."""
        pass

    @abstractmethod
    def decode_request(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decode a request into intermediate representation.

        Args:
            body: Request body in this protocol's format

        Returns:
            Intermediate representation dictionary
        """
        pass

    @abstractmethod
    def encode_request(
        self,
        ir: Dict[str, Any],
        target_model: str,
        *,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Encode intermediate representation to this protocol's request format.

        Args:
            ir: Intermediate representation
            target_model: Target model name
            stream: Whether this is a streaming request

        Returns:
            Request body in this protocol's format
        """
        pass

    @abstractmethod
    def decode_response(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decode a response into intermediate representation.

        Args:
            body: Response body in this protocol's format

        Returns:
            Intermediate representation dictionary
        """
        pass

    @abstractmethod
    def encode_response(
        self,
        ir: Dict[str, Any],
        target_model: str,
    ) -> Dict[str, Any]:
        """
        Encode intermediate representation to this protocol's response format.

        Args:
            ir: Intermediate representation
            target_model: Target model name

        Returns:
            Response body in this protocol's format
        """
        pass

    @abstractmethod
    def decode_stream_chunk(
        self,
        chunk: bytes,
    ) -> List[Dict[str, Any]]:
        """
        Decode a stream chunk into intermediate events.

        Args:
            chunk: Raw bytes from SSE stream

        Returns:
            List of intermediate event dictionaries
        """
        pass

    @abstractmethod
    def encode_stream_event(
        self,
        event: Dict[str, Any],
    ) -> bytes:
        """
        Encode an intermediate event to this protocol's SSE format.

        Args:
            event: Intermediate event dictionary

        Returns:
            SSE-formatted bytes
        """
        pass
