"""
Conversion Exceptions

Custom exceptions for protocol conversion errors.
"""

from typing import Any, Dict, Optional


class ConversionError(Exception):
    """Base exception for conversion errors."""

    def __init__(
        self,
        message: str,
        source_protocol: Optional[str] = None,
        target_protocol: Optional[str] = None,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.source_protocol = source_protocol
        self.target_protocol = target_protocol
        self.field = field
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error": "conversion_error",
            "message": self.message,
            "source_protocol": self.source_protocol,
            "target_protocol": self.target_protocol,
            "field": self.field,
            "details": self.details,
        }


class CapabilityNotSupportedError(ConversionError):
    """
    Raised when the target protocol doesn't support a required capability.

    Examples:
    - Audio I/O when converting to Anthropic
    - Multiple completions (n > 1) when converting from OpenAI to Anthropic
    - Document/PDF input when converting to OpenAI Classic
    """

    def __init__(
        self,
        capability: str,
        source_protocol: Optional[str] = None,
        target_protocol: Optional[str] = None,
        suggestion: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Capability '{capability}' is not supported by target protocol"
        if suggestion:
            message += f". {suggestion}"
        super().__init__(
            message=message,
            source_protocol=source_protocol,
            target_protocol=target_protocol,
            field=capability,
            details=details or {},
        )
        self.capability = capability
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["error"] = "capability_not_supported"
        result["capability"] = self.capability
        result["suggestion"] = self.suggestion
        return result


class ValidationError(ConversionError):
    """
    Raised when input validation fails.

    Examples:
    - Missing required field (e.g., max_tokens for Anthropic)
    - Invalid value range (e.g., temperature > 1 for Anthropic)
    - Invalid content structure
    """

    def __init__(
        self,
        field: str,
        message: str,
        value: Any = None,
        expected: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        full_message = f"Validation error for '{field}': {message}"
        super().__init__(
            message=full_message,
            field=field,
            details=details or {},
        )
        self.value = value
        self.expected = expected

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["error"] = "validation_error"
        result["value"] = repr(self.value) if self.value is not None else None
        result["expected"] = self.expected
        return result


class StreamConversionError(ConversionError):
    """
    Raised when stream conversion fails.

    Examples:
    - Unexpected event type
    - Missing required fields in stream event
    - Stream state inconsistency
    """

    def __init__(
        self,
        message: str,
        event_type: Optional[str] = None,
        event_index: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message=message, details=details or {})
        self.event_type = event_type
        self.event_index = event_index

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["error"] = "stream_conversion_error"
        result["event_type"] = self.event_type
        result["event_index"] = self.event_index
        return result
