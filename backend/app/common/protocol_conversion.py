"""
Protocol Conversion (OpenAI <-> Anthropic <-> OpenAI Responses)

Convert request/response between different LLM API protocols
when provider protocol differs from user request protocol.

This module provides backward-compatible functions that delegate
to the new modular protocol conversion architecture.

Main entry points:
    - convert_request_for_supplier(): Convert user request to supplier protocol
    - convert_response_for_user(): Convert supplier response to user protocol
    - convert_stream_for_user(): Convert supplier stream to user protocol
    - normalize_protocol(): Normalize protocol string to canonical form
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Optional

from app.common.errors import ServiceError

# Import from new modular architecture
from app.common.protocol import (
    ConversionResult,
    Protocol,
    ProtocolConversionError,
    UnsupportedConversionError,
)
from app.common.protocol import (
    convert_request as _convert_request,
)
from app.common.protocol import (
    convert_response as _convert_response,
)
from app.common.protocol import (
    convert_stream as _convert_stream,
)
from app.common.protocol import (
    normalize_protocol as _normalize_protocol,
)
from app.common.provider_protocols import (
    ANTHROPIC_PROTOCOL,
    IMPLEMENTATION_PROTOCOLS,
    OPENAI_PROTOCOL,
    OPENAI_RESPONSES_PROTOCOL,
    resolve_implementation_protocol,
)

logger = logging.getLogger(__name__)


def normalize_protocol(protocol: str) -> str:
    """
    Normalize a protocol string to its canonical form.

    Args:
        protocol: Protocol string (e.g., "openai", "openai_chat", "anthropic")

    Returns:
        Canonical protocol name (openai, openai_responses, or anthropic)

    Raises:
        ServiceError: If protocol is not supported
    """
    try:
        implementation = resolve_implementation_protocol(protocol)
        implementation = (implementation or OPENAI_PROTOCOL).lower().strip()
        if implementation not in IMPLEMENTATION_PROTOCOLS:
            raise ServiceError(
                message=f"Unsupported protocol '{protocol}'",
                code="unsupported_protocol",
            )
        return implementation
    except Exception as e:
        if isinstance(e, ServiceError):
            raise
        raise ServiceError(
            message=f"Unsupported protocol '{protocol}'",
            code="unsupported_protocol",
        ) from e


def convert_request_for_supplier(
    *,
    request_protocol: str,
    supplier_protocol: str,
    path: str,
    body: dict[str, Any],
    target_model: str,
) -> tuple[str, dict[str, Any]]:
    """
    Convert user request protocol to supplier protocol request body/path.

    Supports conversion between:
    - OpenAI: /v1/chat/completions
    - Anthropic: /v1/messages
    - OpenAI Responses: /v1/responses

    Args:
        request_protocol: Protocol of the incoming user request
        supplier_protocol: Protocol expected by the supplier/provider
        path: Original request path
        body: Request body in user protocol format
        target_model: Target model name for the supplier

    Returns:
        tuple[str, dict]: (target_path, converted_body)

    Raises:
        ServiceError: If conversion fails or is not supported
    """
    try:
        # Normalize protocols
        request_protocol = normalize_protocol(request_protocol)
        supplier_protocol = normalize_protocol(supplier_protocol)

        # Use new conversion module
        result = _convert_request(
            source_protocol=request_protocol,
            target_protocol=supplier_protocol,
            path=path,
            body=body,
            target_model=target_model,
        )

        return result.path, result.body

    except UnsupportedConversionError as e:
        raise ServiceError(
            message=e.message,
            code=e.code,
        ) from e
    except ProtocolConversionError as e:
        raise ServiceError(
            message=e.message,
            code=e.code,
        ) from e
    except ServiceError:
        raise
    except Exception as e:
        logger.exception(
            "Unexpected error during request conversion: %s -> %s",
            request_protocol,
            supplier_protocol,
        )
        raise ServiceError(
            message=f"Request conversion failed: {str(e)}",
            code="conversion_error",
        ) from e


def convert_response_for_user(
    *,
    request_protocol: str,
    supplier_protocol: str,
    body: Any,
    target_model: str,
) -> Any:
    """
    Convert supplier response to user request protocol response body.

    Args:
        request_protocol: Protocol the user expects (original request protocol)
        supplier_protocol: Protocol of the supplier response
        body: Response body from supplier
        target_model: Target model name

    Returns:
        Converted response body in user's expected protocol format

    Raises:
        ServiceError: If conversion fails or is not supported
    """
    try:
        # Normalize protocols
        request_protocol = normalize_protocol(request_protocol)
        supplier_protocol = normalize_protocol(supplier_protocol)

        # No conversion needed for same protocol
        if request_protocol == supplier_protocol:
            return body

        # Skip non-dict bodies
        if not isinstance(body, dict):
            return body

        # Use new conversion module
        # Note: For response conversion, we convert FROM supplier TO user request protocol
        return _convert_response(
            source_protocol=supplier_protocol,
            target_protocol=request_protocol,
            body=body,
            target_model=target_model,
        )

    except UnsupportedConversionError as e:
        raise ServiceError(
            message=e.message,
            code=e.code,
        ) from e
    except ProtocolConversionError as e:
        raise ServiceError(
            message=e.message,
            code=e.code,
        ) from e
    except ServiceError:
        raise
    except Exception as e:
        logger.exception(
            "Unexpected error during response conversion: %s -> %s",
            supplier_protocol,
            request_protocol,
        )
        raise ServiceError(
            message=f"Response conversion failed: {str(e)}",
            code="conversion_error",
        ) from e


async def convert_stream_for_user(
    *,
    request_protocol: str,
    supplier_protocol: str,
    upstream: AsyncGenerator[bytes, None],
    model: str,
    input_tokens: Optional[int] = None,
) -> AsyncGenerator[bytes, None]:
    """
    Convert supplier SSE bytes stream to user request protocol SSE bytes stream.

    SSE Formats:
    - OpenAI: data: {chat.completion.chunk}\n\n + data: [DONE]\n\n
    - Anthropic: data: {type: ...}\n\n (ends with message_stop event)
    - OpenAI Responses: data: {type: ...}\n\n

    Args:
        request_protocol: Protocol the user expects
        supplier_protocol: Protocol of the supplier stream
        upstream: Async generator yielding bytes from upstream provider
        model: Model name for the response

    Yields:
        Converted SSE bytes in user's expected protocol format

    Raises:
        ServiceError: If conversion fails or is not supported
    """
    try:
        # Normalize protocols
        request_protocol = normalize_protocol(request_protocol)
        supplier_protocol = normalize_protocol(supplier_protocol)

        # No conversion needed for same protocol
        if request_protocol == supplier_protocol:
            async for chunk in upstream:
                yield chunk
            return

        # Use new conversion module
        # Note: For stream conversion, we convert FROM supplier TO user request protocol
        async for chunk in _convert_stream(
            source_protocol=supplier_protocol,
            target_protocol=request_protocol,
            upstream=upstream,
            model=model,
            options={"input_tokens": input_tokens}
            if input_tokens is not None
            else None,
        ):
            yield chunk

    except UnsupportedConversionError as e:
        raise ServiceError(
            message=e.message,
            code=e.code,
        ) from e
    except ProtocolConversionError as e:
        raise ServiceError(
            message=e.message,
            code=e.code,
        ) from e
    except ServiceError:
        raise
    except Exception as e:
        logger.exception(
            "Unexpected error during stream conversion: %s -> %s",
            supplier_protocol,
            request_protocol,
        )
        raise ServiceError(
            message=f"Stream conversion failed: {str(e)}",
            code="conversion_error",
        ) from e


# Export for backward compatibility
__all__ = [
    "normalize_protocol",
    "convert_request_for_supplier",
    "convert_response_for_user",
    "convert_stream_for_user",
]
