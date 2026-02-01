from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProtocolConversionHooks:
    """
    Protocol conversion hooks for request/response/stream customization.

    - request_protocol: original user request protocol
    - supplier_protocol: supplier/provider protocol (target for request conversion)
    """

    @staticmethod
    def _log_call(name: str, **kwargs: Any) -> None:
        # Convert bytes to string for JSON serialization
        sanitized_kwargs = {
            k: v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v
            for k, v in kwargs.items()
        }
        payload = {"hook": name, "args": sanitized_kwargs}
        logger.info("protocol_hook=%s", json.dumps(payload, ensure_ascii=False))

    def before_request_conversion(
        self,
        body: dict[str, Any],
        request_protocol: str,
        supplier_protocol: str,
    ) -> dict[str, Any]:
        self._log_call(
            "before_request_conversion",
            body=body,
            request_protocol=request_protocol,
            supplier_protocol=supplier_protocol,
        )
        return body

    def after_request_conversion(
        self,
        supplier_body: dict[str, Any],
        request_protocol: str,
        supplier_protocol: str,
    ) -> dict[str, Any]:
        self._log_call(
            "after_request_conversion",
            supplier_body=supplier_body,
            request_protocol=request_protocol,
            supplier_protocol=supplier_protocol,
        )
        return supplier_body

    def before_response_conversion(
        self,
        supplier_body: Any,
        request_protocol: str,
        supplier_protocol: str,
    ) -> Any:
        self._log_call(
            "before_response_conversion",
            supplier_body=supplier_body,
            request_protocol=request_protocol,
            supplier_protocol=supplier_protocol,
        )
        return supplier_body

    def after_response_conversion(
        self,
        response_body: Any,
        request_protocol: str,
        supplier_protocol: str,
    ) -> Any:
        self._log_call(
            "after_response_conversion",
            response_body=response_body,
            request_protocol=request_protocol,
            supplier_protocol=supplier_protocol,
        )
        return response_body

    def before_stream_chunk_conversion(
        self,
        chunk: bytes,
        request_protocol: str,
        supplier_protocol: str,
    ) -> bytes:
        self._log_call(
            "before_stream_chunk_conversion",
            chunk=chunk,
            request_protocol=request_protocol,
            supplier_protocol=supplier_protocol,
        )
        return chunk

    def after_stream_chunk_conversion(
        self,
        chunk: bytes,
        request_protocol: str,
        supplier_protocol: str,
    ) -> bytes:
        self._log_call(
            "after_stream_chunk_conversion",
            chunk=chunk,
            request_protocol=request_protocol,
            supplier_protocol=supplier_protocol,
        )
        return chunk
