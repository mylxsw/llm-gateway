from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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

    def __init__(
        self,
        kv_repo: Optional[KVStoreRepository] = None,
        *,
        kv_repo_factory: Optional[Callable[[AsyncSession], KVStoreRepository]] = None,
        session_factory: Optional[async_sessionmaker] = None,
    ):
        """
        Initialize hooks with optional KV store access.

        Two modes:
        - Long-lived repo: pass ``kv_repo`` (e.g. a Redis-backed repo or a test
          fake). Reused for every KV op.
        - DB mode: pass ``kv_repo_factory`` + ``session_factory``. Each KV op
          opens a short-lived session so per-chunk stream caching does not pin a
          pooled DB connection for the whole stream.

        Args:
            kv_repo: KV store repository instance (long-lived)
            kv_repo_factory: builds a KVStoreRepository from a session (DB mode)
            session_factory: async_sessionmaker for per-op sessions (DB mode)
        """
        self._kv_repo = kv_repo
        self._kv_repo_factory = kv_repo_factory
        self._session_factory = session_factory
        # KV caching is active if either a long-lived repo or a DB factory is set.
        self._kv_enabled = kv_repo is not None or kv_repo_factory is not None

    @asynccontextmanager
    async def _kv(self):
        """Yield a KV repository for a single operation. In DB mode this opens
        a short-lived session and releases the connection on exit; otherwise it
        yields the long-lived repo (which may be None when KV is disabled)."""
        if self._kv_repo is not None or self._session_factory is None:
            yield self._kv_repo
            return
        async with self._session_factory() as session:
            yield self._kv_repo_factory(session)

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
        if request_protocol == "openai" and self._kv_enabled:
            await self._inject_cached_content(body)

        return body

    async def after_request_conversion(
        self,
        supplier_body: dict[str, Any],
        request_protocol: str,
        supplier_protocol: str,
    ) -> dict[str, Any]:
        if supplier_protocol == "openai" and request_protocol != "openai" and self._kv_enabled:
            await self._inject_cached_content(supplier_body)

        return supplier_body

    async def before_response_conversion(
        self,
        supplier_body: Any,
        request_protocol: str,
        supplier_protocol: str,
    ) -> Any:
        if supplier_protocol == "openai" and self._kv_enabled and isinstance(supplier_body, dict):
            await self._cache_response_tool_call_extra_content(supplier_body)
        return supplier_body

    async def after_response_conversion(
        self,
        response_body: Any,
        request_protocol: str,
        supplier_protocol: str,
    ) -> Any:
        if request_protocol == "openai" and supplier_protocol != "openai" and self._kv_enabled and isinstance(response_body, dict):
            await self._cache_response_tool_call_extra_content(response_body)

        return response_body

    async def before_stream_chunk_conversion(
        self,
        chunk: bytes,
        request_protocol: str,
        supplier_protocol: str,
    ) -> bytes:
        if supplier_protocol == "openai":
            await self._cache_response_tool_call_extra_content_stream(chunk)
        return chunk

    async def after_stream_chunk_conversion(
        self,
        chunk: bytes,
        request_protocol: str,
        supplier_protocol: str,
    ) -> bytes:
        if request_protocol == "openai" and supplier_protocol != "openai":
            await self._cache_response_tool_call_extra_content_stream(chunk)
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
        if not self._kv_enabled:
            return chunk
        try:
            # One short-lived session per chunk: released as soon as this chunk's
            # KV ops finish, so streaming never pins a pooled connection.
            async with self._kv() as kv:
                if kv is None:
                    return chunk
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
                        if reasoning_content and chat_id:
                            cache_key = f"chat_reasoning:{chat_id}"
                            try:
                                cached = await kv.get(cache_key)
                                new_val = cached.value + reasoning_content if cached else reasoning_content
                                await kv.set(cache_key, new_val, ttl_seconds=TOOL_CALL_EXTRA_CONTENT_TTL)
                            except Exception as e:
                                logger.debug(f"Error caching reasoning_content: {e}")

                        # Process tool_calls. Some OpenAI-compatible providers return
                        # explicit null when there are no tool calls.
                        tool_calls = delta.get("tool_calls")
                        if not isinstance(tool_calls, list):
                            tool_calls = []
                        for tool_call in tool_calls:
                            tool_call_id = tool_call.get("id", "")

                            # Link tool_call_id to chat_id for reasoning_content recovery
                            if tool_call_id and chat_id:
                                link_key = f"tool_call_chat_id:{tool_call_id}"
                                try:
                                    await kv.set(link_key, chat_id, ttl_seconds=TOOL_CALL_EXTRA_CONTENT_TTL)
                                except Exception as e:
                                    logger.debug(f"Error linking tool_call to chat_id: {e}")

                            # for google: https://ai.google.dev/gemini-api/docs/thought-signatures#openai
                            extra_content = tool_call.get("extra_content")
                            if not extra_content:
                                continue

                            if not tool_call_id:
                                continue

                            cache_key = f"tool_call_extra:{tool_call_id}"
                            await kv.set(
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
        if not self._kv_enabled:
            return
        async with self._kv() as kv:
            if kv is None:
                return
            choices = supplier_body.get("choices", [])
            for choice in choices:
                message = choice.get("message", {})
                reasoning_content = message.get("reasoning_content")

                tool_calls = message.get("tool_calls")
                if not isinstance(tool_calls, list):
                    tool_calls = []

                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id", "")
                    if not tool_call_id:
                        continue

                    if reasoning_content:
                        cache_key = f"tool_call_reasoning:{tool_call_id}"
                        try:
                            await kv.set(
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
                        await kv.set(
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
        if not self._kv_enabled:
            return
        async with self._kv() as kv:
            if kv is None:
                return
            messages = supplier_body.get("messages", [])
            for message in messages:
                if message.get("role") != "assistant":
                    continue

                tool_calls = message.get("tool_calls")
                if not isinstance(tool_calls, list):
                    tool_calls = []

                # Inject reasoning_content if missing
                if tool_calls and not message.get("reasoning_content"):
                    for tool_call in tool_calls:
                        tool_call_id = tool_call.get("id", "")
                        if not tool_call_id:
                            continue

                        reasoning_content = None
                        try:
                            # 1. Direct fetch
                            cached = await kv.get(f"tool_call_reasoning:{tool_call_id}")
                            if cached:
                                reasoning_content = cached.value
                            else:
                                # 2. Indirect fetch (from stream)
                                link_cached = await kv.get(f"tool_call_chat_id:{tool_call_id}")
                                if link_cached:
                                    chat_id = link_cached.value
                                    content_cached = await kv.get(f"chat_reasoning:{chat_id}")
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
                        cached_model = await kv.get(cache_key)
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
