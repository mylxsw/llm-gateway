from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.repositories.kv_store_repo import KVStoreRepository

logger = logging.getLogger(__name__)

# 30 days in seconds
TOOL_CALL_EXTRA_CONTENT_TTL = 30 * 24 * 60 * 60


class ProtocolConversionHooks:
    """
    Protocol conversion hooks for request/response/stream customization.

    - request_protocol: original user request protocol
    - supplier_protocol: supplier/provider protocol (target for request conversion)
    """

    def __init__(self, kv_repo: Optional[KVStoreRepository] = None):
        """
        Initialize hooks with optional KV store repository.

        Args:
            kv_repo: KV store repository for caching tool call extra content
        """
        self._kv_repo = kv_repo

    @staticmethod
    def _log_call(name: str, **kwargs: Any) -> None:
        # Convert bytes to string for JSON serialization
        sanitized_kwargs = {
            k: v.decode("utf-8", errors="replace") if isinstance(v, bytes) else v
            for k, v in kwargs.items()
        }
        payload = {"hook": name, "args": sanitized_kwargs}
        logger.info("protocol_hook=%s", json.dumps(payload, ensure_ascii=False))
        pass

    async def before_request_conversion(
        self,
        body: dict[str, Any],
        request_protocol: str,
        supplier_protocol: str,
    ) -> dict[str, Any]:
        # self._log_call(
        #     "before_request_conversion",
        #     body=body,
        #     request_protocol=request_protocol,
        #     supplier_protocol=supplier_protocol,
        # )
        return body

    async def after_request_conversion(
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

        if supplier_protocol == "openai" and self._kv_repo:
            await self._inject_tool_call_extra_content(supplier_body)

        logger.info(
            "after_request_conversion: %s",
            json.dumps(supplier_body, ensure_ascii=False),
        )

        return supplier_body

    async def _inject_tool_call_extra_content(
        self, supplier_body: dict[str, Any]
    ) -> None:
        """
        Inject extra_content from KV store into tool_calls in messages.

        For openai protocol, look up cached extra_content by tool_call_id
        and insert it into the corresponding tool_call.
        """
        messages = supplier_body.get("messages", [])
        for message in messages:
            if message.get("role") != "assistant":
                continue

            tool_calls = message.get("tool_calls", [])
            for tool_call in tool_calls:
                tool_call_id = tool_call.get("id", "")
                if not tool_call_id:
                    continue

                # for google: https://ai.google.dev/gemini-api/docs/thought-signatures#openai
                cache_key = f"tool_call_extra:{tool_call_id}"
                try:
                    cached_model = await self._kv_repo.get(cache_key)
                    if cached_model:
                        extra_content = json.loads(cached_model.value)
                        tool_call["extra_content"] = extra_content
                        logger.info(
                            f"Injected extra_content for tool_call: id={tool_call_id}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Error retrieving extra_content for tool_call {tool_call_id}: {e}"
                    )

    async def before_response_conversion(
        self,
        supplier_body: Any,
        request_protocol: str,
        supplier_protocol: str,
    ) -> Any:
        # self._log_call(
        #     "before_response_conversion",
        #     supplier_body=supplier_body,
        #     request_protocol=request_protocol,
        #     supplier_protocol=supplier_protocol,
        # )
        return supplier_body

    async def after_response_conversion(
        self,
        response_body: Any,
        request_protocol: str,
        supplier_protocol: str,
    ) -> Any:
        # self._log_call(
        #     "after_response_conversion",
        #     response_body=response_body,
        #     request_protocol=request_protocol,
        #     supplier_protocol=supplier_protocol,
        # )
        return response_body

    async def before_stream_chunk_conversion(
        self,
        chunk: bytes,
        request_protocol: str,
        supplier_protocol: str,
    ) -> bytes:
        # self._log_call(
        #     "before_stream_chunk_conversion",
        #     chunk=chunk,
        #     request_protocol=request_protocol,
        #     supplier_protocol=supplier_protocol,
        # )

        try:
            chunk_str = chunk.decode("utf-8", errors="replace")
            for line in chunk_str.split("\n"):
                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                    data = json.loads(line[6:])
                    choices = data.get("choices", [])
                    for choice in choices:
                        delta = choice.get("delta", {})
                        tool_calls = delta.get("tool_calls", [])
                        for tool_call in tool_calls:
                            # for google: https://ai.google.dev/gemini-api/docs/thought-signatures#openai
                            extra_content = tool_call.get("extra_content")
                            if extra_content:
                                tool_call_id = tool_call.get("id", "")
                                if tool_call_id and self._kv_repo:
                                    cache_key = f"tool_call_extra:{tool_call_id}"
                                    await self._kv_repo.set(
                                        cache_key,
                                        json.dumps(extra_content, ensure_ascii=False),
                                        ttl_seconds=TOOL_CALL_EXTRA_CONTENT_TTL,
                                    )
                                    logger.info(
                                        f"Cached tool_call extra_content: id={tool_call_id}"
                                    )
        except Exception as e:
            logger.debug(f"Error processing stream chunk for extra_content: {e}")

        return chunk

    async def after_stream_chunk_conversion(
        self,
        chunk: bytes,
        request_protocol: str,
        supplier_protocol: str,
    ) -> bytes:
        # self._log_call(
        #     "after_stream_chunk_conversion",
        #     chunk=chunk,
        #     request_protocol=request_protocol,
        #     supplier_protocol=supplier_protocol,
        # )
        return chunk
