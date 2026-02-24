from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.repositories.kv_store_repo import KVStoreRepository

logger = logging.getLogger(__name__)

# 30 days in seconds
TOOL_CALL_EXTRA_CONTENT_TTL = 30 * 24 * 60 * 60
OPENAI_IMAGE_PATHS = {
    "/v1/images/generations",
    "/v1/images/edits",
    "/v1/images/variations",
}


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
        return body

    async def after_request_conversion(
        self,
        supplier_body: dict[str, Any],
        request_protocol: str,
        supplier_protocol: str,
    ) -> dict[str, Any]:
        if supplier_protocol == "openai" and self._kv_repo:
            await self._inject_cached_content(supplier_body)

        return supplier_body

    async def before_response_conversion(
        self,
        supplier_body: Any,
        request_protocol: str,
        supplier_protocol: str,
    ) -> Any:
        if self._kv_repo and isinstance(supplier_body, dict):
            await self._cache_response_tool_call_extra_content(supplier_body)

        return supplier_body

    async def after_response_conversion(
        self,
        response_body: Any,
        request_protocol: str,
        supplier_protocol: str,
    ) -> Any:
        return response_body

    async def before_stream_chunk_conversion(
        self,
        chunk: bytes,
        request_protocol: str,
        supplier_protocol: str,
    ) -> bytes:
        return await self._cache_response_tool_call_extra_content_stream(chunk)

    async def after_stream_chunk_conversion(
        self,
        chunk: bytes,
        request_protocol: str,
        supplier_protocol: str,
    ) -> bytes:
        return chunk

    async def before_image_request_conversion(
        self,
        body: dict[str, Any],
        request_protocol: str,
        supplier_protocol: str,
        path: str,
    ) -> dict[str, Any]:
        return body

    async def after_image_request_conversion(
        self,
        supplier_body: dict[str, Any],
        request_protocol: str,
        supplier_protocol: str,
        path: str,
    ) -> dict[str, Any]:
        return supplier_body

    async def before_image_response_conversion(
        self,
        supplier_body: Any,
        request_protocol: str,
        supplier_protocol: str,
        path: str,
    ) -> Any:
        return supplier_body

    async def after_image_response_conversion(
        self,
        response_body: Any,
        request_protocol: str,
        supplier_protocol: str,
        path: str,
    ) -> Any:
        return response_body

    async def _cache_response_tool_call_extra_content_stream(
        self, chunk: bytes
    ) -> bytes:
        try:
            chunk_str = chunk.decode("utf-8", errors="replace")
            for line in chunk_str.split("\n"):
                if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                    continue

                try:
                    data = json.loads(line[6:])
                except Exception:
                    continue

                chat_id = data.get("id", "")

                for choice in data.get("choices", []):
                    delta = choice.get("delta", {})

                    # Accumulate reasoning_content keyed by chat_id
                    reasoning_content = delta.get("reasoning_content")
                    if reasoning_content and chat_id and self._kv_repo:
                        cache_key = f"chat_reasoning:{chat_id}"
                        try:
                            cached = await self._kv_repo.get(cache_key)
                            new_val = cached.value + reasoning_content if cached else reasoning_content
                            await self._kv_repo.set(cache_key, new_val, ttl_seconds=TOOL_CALL_EXTRA_CONTENT_TTL)
                        except Exception as e:
                            logger.debug(f"Error caching reasoning_content: {e}")

                    # Process tool_calls
                    for tool_call in delta.get("tool_calls", []):
                        tool_call_id = tool_call.get("id", "")
                        
                        # Link tool_call_id to chat_id for reasoning_content recovery
                        if tool_call_id and chat_id and self._kv_repo:
                            link_key = f"tool_call_chat_id:{tool_call_id}"
                            try:
                                await self._kv_repo.set(link_key, chat_id, ttl_seconds=TOOL_CALL_EXTRA_CONTENT_TTL)
                            except Exception as e:
                                logger.debug(f"Error linking tool_call to chat_id: {e}")

                        # for google: https://ai.google.dev/gemini-api/docs/thought-signatures#openai
                        extra_content = tool_call.get("extra_content")
                        if not extra_content:
                            continue

                        if not tool_call_id or not self._kv_repo:
                            continue

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

    async def _cache_response_tool_call_extra_content(
        self, supplier_body: dict[str, Any]
    ) -> None:
        """
        Cache extra_content and reasoning_content from tool_calls in non-streaming response.
        """
        choices = supplier_body.get("choices", [])
        for choice in choices:
            message = choice.get("message", {})
            reasoning_content = message.get("reasoning_content")

            for tool_call in message.get("tool_calls", []):
                tool_call_id = tool_call.get("id", "")
                if not tool_call_id:
                    continue

                if reasoning_content and self._kv_repo:
                    cache_key = f"tool_call_reasoning:{tool_call_id}"
                    try:
                        await self._kv_repo.set(
                            cache_key,
                            reasoning_content,
                            ttl_seconds=TOOL_CALL_EXTRA_CONTENT_TTL,
                        )
                        logger.info(f"Cached reasoning_content (non-stream): id={tool_call_id}")
                    except Exception as e:
                        logger.warning(f"Error caching reasoning_content for {tool_call_id}: {e}")

                extra_content = tool_call.get("extra_content")
                if not extra_content:
                    continue

                cache_key = f"tool_call_extra:{tool_call_id}"
                try:
                    await self._kv_repo.set(
                        cache_key,
                        json.dumps(extra_content, ensure_ascii=False),
                        ttl_seconds=TOOL_CALL_EXTRA_CONTENT_TTL,
                    )
                    logger.info(
                        f"Cached tool_call extra_content (non-stream): id={tool_call_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Error caching extra_content for tool_call {tool_call_id}: {e}"
                    )

    async def _inject_cached_content(
        self, supplier_body: dict[str, Any]
    ) -> None:
        """
        Inject cached extra_content and reasoning_content from KV store into messages.
        """
        messages = supplier_body.get("messages", [])
        for message in messages:
            if message.get("role") != "assistant":
                continue

            tool_calls = message.get("tool_calls", [])
            
            # Inject reasoning_content if missing
            if tool_calls and not message.get("reasoning_content"):
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id", "")
                    if not tool_call_id or not self._kv_repo:
                        continue

                    reasoning_content = None
                    try:
                        # 1. Direct fetch
                        cached = await self._kv_repo.get(f"tool_call_reasoning:{tool_call_id}")
                        if cached:
                            reasoning_content = cached.value
                        else:
                            # 2. Indirect fetch (from stream)
                            link_cached = await self._kv_repo.get(f"tool_call_chat_id:{tool_call_id}")
                            if link_cached:
                                chat_id = link_cached.value
                                content_cached = await self._kv_repo.get(f"chat_reasoning:{chat_id}")
                                if content_cached:
                                    reasoning_content = content_cached.value
                    except Exception as e:
                        logger.warning(f"Error retrieving reasoning_content for {tool_call_id}: {e}")

                    if reasoning_content:
                        message["reasoning_content"] = reasoning_content
                        logger.info(f"Injected reasoning_content for message with tool_call: id={tool_call_id}")
                        break

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
