"""
Retry and Failover Handler Module

Implements logic for request retry and provider failover.
"""

import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Optional, Awaitable

from app.config import get_settings
from app.common.time import utc_now
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.provider_health import (
    ProviderHealthTracker,
    provider_health_key,
)
from app.services.strategy import SelectionStrategy

logger = logging.getLogger(__name__)

@dataclass
class AttemptRecord:
    """
    Attempt Record

    Stores per-attempt information so callers can persist logs for failures/retries.
    """

    provider: CandidateProvider
    response: ProviderResponse
    request_time: datetime
    attempt_index: int


@dataclass
class RetryResult:
    """
    Retry Result Data Class
    
    Encapsulates result information after retry execution.
    """
    
    # Final Response
    response: ProviderResponse
    # Total Retry Count
    retry_count: int
    # Final Provider Used
    final_provider: CandidateProvider
    # Success Status
    success: bool
    # All attempts in order (including final)
    attempts: list[AttemptRecord]


class RetryHandler:
    """
    Retry and Failover Handler
    
    Implements the following retry logic:
    - Status code >= 500: Retry on the same provider, max 3 times, 1000ms interval
    - Status code < 500: Switch directly to the next provider
    - All providers failed: Return the last failed response
    """
    
    def __init__(
        self,
        strategy: SelectionStrategy,
        health_tracker: ProviderHealthTracker | None = None,
    ):
        """
        Initialize Handler
        
        Args:
            strategy: Provider Selection Strategy
        """
        settings = get_settings()
        self.strategy = strategy
        # Max retries on same provider
        self.max_retries = settings.RETRY_MAX_ATTEMPTS
        # Retry interval (ms)
        self.retry_delay_ms = settings.RETRY_DELAY_MS
        self.health_tracker = health_tracker

    @staticmethod
    def _candidate_key(
        candidate: CandidateProvider,
    ) -> tuple[str, int] | tuple[str, int, str]:
        if candidate.provider_mapping_id is not None:
            return ("mapping", candidate.provider_mapping_id)
        return ("provider_target", candidate.provider_id, candidate.target_model)

    async def get_ordered_candidates(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        *,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
    ) -> list[CandidateProvider]:
        """
        Get candidate order based on the selection strategy.

        This mirrors provider selection + failover ordering without making requests.
        """
        return [
            candidate
            async for candidate in self._iter_ordered_candidates(
                candidates,
                requested_model,
                input_tokens=input_tokens,
                image_count=image_count,
            )
        ]

    async def _iter_ordered_candidates(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        *,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
    ) -> AsyncIterator[CandidateProvider]:
        """Yield candidates lazily in health-aware strategy order.

        Strategy selection for a fallback group is deferred until the caller
        actually asks for a candidate from that group. This is important for
        stateful weighted strategies: a successful primary request must not
        advance counters for fallback providers that were never attempted.
        """
        if not candidates:
            return

        groups: list[tuple[str, list[CandidateProvider]]] = []
        if self.health_tracker is None or not self.health_tracker.enabled:
            groups.append((requested_model, candidates))
        else:
            snapshots = await self.health_tracker.get_snapshots(candidates)
            healthy: list[CandidateProvider] = []
            degraded_groups: dict[float, list[CandidateProvider]] = {}
            for candidate in candidates:
                snapshot = snapshots[provider_health_key(candidate)]
                if not snapshot.degraded:
                    healthy.append(candidate)
                    continue
                degraded_groups.setdefault(snapshot.failure_rate, []).append(candidate)

            if healthy:
                groups.append((requested_model, healthy))
            for failure_rate in sorted(degraded_groups):
                # Isolate round-robin counters for degraded fallback groups so
                # their distribution does not disturb the healthy pool.
                group_model_key = f"{requested_model}::degraded::{failure_rate:.6f}"
                groups.append((group_model_key, degraded_groups[failure_rate]))

        for group_model_key, group_candidates in groups:
            async for candidate in self._iter_strategy_candidates(
                group_candidates,
                group_model_key,
                input_tokens=input_tokens,
                image_count=image_count,
            ):
                yield candidate

    async def _iter_strategy_candidates(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        *,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
    ) -> AsyncIterator[CandidateProvider]:
        """Lazily yield one strategy group in selection/failover order."""
        if not candidates:
            return

        tried_candidates: set[tuple[str, int] | tuple[str, int, str]] = set()
        current_provider = await self.strategy.select(candidates, requested_model, input_tokens, image_count)
        while current_provider is not None:
            current_key = self._candidate_key(current_provider)
            if current_key in tried_candidates:
                break
            tried_candidates.add(current_key)
            yield current_provider
            if len(tried_candidates) >= len(candidates):
                return
            current_provider = await self._get_next_untried_provider(
                candidates, tried_candidates, requested_model, current_provider, input_tokens, image_count
            )

        for candidate in candidates:
            if self._candidate_key(candidate) not in tried_candidates:
                yield candidate

    async def _record_health(
        self,
        provider: CandidateProvider,
        response: ProviderResponse,
    ) -> None:
        if self.health_tracker is None:
            return
        try:
            await self.health_tracker.record_response(provider, response)
        except Exception:
            # Health tracking must never make the proxy request fail.
            logger.exception(
                "Failed to update provider health: provider_id=%s target_model=%s",
                provider.provider_id,
                provider.target_model,
            )
    
    async def execute_with_retry(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        forward_fn: Callable[[CandidateProvider], Any],
        *,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
        on_failure_attempt: Callable[[AttemptRecord], Awaitable[None]] | None = None,
    ) -> RetryResult:
        """
        Execute Request with Retry

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            forward_fn: Forwarding function, accepts CandidateProvider and returns ProviderResponse
            input_tokens: Number of input tokens (for cost-based selection)

        Returns:
            RetryResult: Retry result
        """
        if not candidates:
            return RetryResult(
                response=ProviderResponse(
                    status_code=503,
                    error="No available providers",
                ),
                retry_count=0,
                final_provider=None,  # type: ignore
                success=False,
                attempts=[],
            )
        
        total_retry_count = 0
        last_response: Optional[ProviderResponse] = None
        last_provider: Optional[CandidateProvider] = None
        attempts: list[AttemptRecord] = []
        attempt_index = 0
        
        async for current_provider in self._iter_ordered_candidates(
            candidates,
            requested_model,
            input_tokens=input_tokens,
            image_count=image_count,
        ):
            last_provider = current_provider
            provider_response: Optional[ProviderResponse] = None
            
            # Same provider retry count
            same_provider_retries = 0
            
            while same_provider_retries < self.max_retries:
                # Execute request
                attempt_time = utc_now()
                response = await forward_fn(current_provider)
                last_response = response
                provider_response = response
                attempt_record = AttemptRecord(
                    provider=current_provider,
                    response=response,
                    request_time=attempt_time,
                    attempt_index=attempt_index,
                )
                attempts.append(attempt_record)
                attempt_index += 1

                # Success response
                if response.is_success:
                    await self._record_health(current_provider, response)
                    return RetryResult(
                        response=response,
                        retry_count=total_retry_count,
                        final_provider=current_provider,
                        success=True,
                        attempts=attempts,
                    )

                if on_failure_attempt is not None:
                    try:
                        await on_failure_attempt(attempt_record)
                    except Exception:
                        logger.exception(
                            "on_failure_attempt callback failed: provider_id=%s attempt_index=%s",
                            current_provider.provider_id,
                            attempt_record.attempt_index,
                        )

                # Log failure
                logger.warning(
                    "Provider request failed: provider_id=%s, provider_name=%s, protocol=%s, "
                    "status_code=%s, error=%s, retry_attempt=%s/%s",
                    current_provider.provider_id,
                    current_provider.provider_name,
                    current_provider.protocol,
                    response.status_code,
                    response.error,
                    same_provider_retries + 1,
                    self.max_retries,
                )

                # Status code >= 500: Retry on same provider
                if response.is_server_error:
                    same_provider_retries += 1
                    total_retry_count += 1

                    if same_provider_retries < self.max_retries:
                        # Wait before retry
                        await asyncio.sleep(self.retry_delay_ms / 1000)
                        continue
                    else:
                        # Max retries reached, switch provider
                        logger.warning(
                            "Max retries reached for provider: provider_id=%s, provider_name=%s, switching to next provider",
                            current_provider.provider_id,
                            current_provider.provider_name,
                        )
                        break
                else:
                    # Status code < 500: Switch provider immediately
                    logger.warning(
                        "Client error from provider, switching: provider_id=%s, provider_name=%s, status_code=%s",
                        current_provider.provider_id,
                        current_provider.provider_name,
                        response.status_code,
                    )
                    total_retry_count += 1
                    break

            if provider_response is not None:
                await self._record_health(current_provider, provider_response)

        # All providers failed
        return RetryResult(
            response=last_response or ProviderResponse(
                status_code=503,
                error="All providers failed",
            ),
            retry_count=total_retry_count,
            final_provider=last_provider,  # type: ignore
            success=False,
            attempts=attempts,
        )

    async def execute_with_retry_stream(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        forward_stream_fn: Callable[[CandidateProvider], Any],
        *,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
        on_failure_attempt: Callable[[AttemptRecord], Awaitable[None]] | None = None,
    ) -> Any:
        """
        Execute Streaming Request with Retry

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            forward_stream_fn: Streaming forwarding function
            input_tokens: Number of input tokens (for cost-based selection)

        Yields:
            tuple[bytes, ProviderResponse, CandidateProvider, int]: (Data chunk, Response info, Final Provider, Retry Count)
        """
        if not candidates:
            yield b"", ProviderResponse(
                status_code=503,
                error="No available providers",
            ), None, 0
            return
            
        total_retry_count = 0
        last_chunk: bytes = b""
        last_response: Optional[ProviderResponse] = None
        last_provider: Optional[CandidateProvider] = None
        attempt_index = 0

        async for current_provider in self._iter_ordered_candidates(
            candidates,
            requested_model,
            input_tokens=input_tokens,
            image_count=image_count,
        ):
            last_provider = current_provider
            same_provider_retries = 0
            provider_response: Optional[ProviderResponse] = None
            
            while same_provider_retries < self.max_retries:
                try:
                    # Get generator
                    attempt_time = utc_now()
                    result = forward_stream_fn(current_provider)
                    # Handle both sync and async forward_stream_fn
                    if asyncio.iscoroutine(result):
                        generator = await result
                    else:
                        generator = result
                    # Get first chunk
                    chunk, response = await anext(generator)
                    last_response = response
                    provider_response = response
                    last_chunk = chunk
                    attempt_record = AttemptRecord(
                        provider=current_provider,
                        response=response,
                        request_time=attempt_time,
                        attempt_index=attempt_index,
                    )
                    attempt_index += 1

                    if response.is_success:
                        # Success, yield subsequent data
                        yield chunk, response, current_provider, total_retry_count
                        final_response = response
                        async for chunk, stream_response in generator:
                            final_response = stream_response
                            last_response = stream_response
                            yield chunk, stream_response, current_provider, total_retry_count
                        await self._record_health(current_provider, final_response)
                        return

                    if on_failure_attempt is not None:
                        try:
                            await on_failure_attempt(attempt_record)
                        except Exception:
                            logger.exception(
                                "on_failure_attempt callback failed (stream): provider_id=%s attempt_index=%s",
                                current_provider.provider_id,
                                attempt_record.attempt_index,
                            )

                    # Log failure
                    logger.warning(
                        "Provider stream request failed: provider_id=%s, provider_name=%s, protocol=%s, "
                        "status_code=%s, error=%s, retry_attempt=%s/%s",
                        current_provider.provider_id,
                        current_provider.provider_name,
                        current_provider.protocol,
                        response.status_code,
                        response.error,
                        same_provider_retries + 1,
                        self.max_retries,
                    )

                    # Failure logic
                    if response.is_server_error:
                        same_provider_retries += 1
                        total_retry_count += 1
                        if same_provider_retries < self.max_retries:
                            await asyncio.sleep(self.retry_delay_ms / 1000)
                            continue
                        else:
                            logger.warning(
                                "Max retries reached for stream provider: provider_id=%s, provider_name=%s, switching to next provider",
                                current_provider.provider_id,
                                current_provider.provider_name,
                            )
                            break
                    else:
                        logger.warning(
                            "Client error from stream provider, switching: provider_id=%s, provider_name=%s, status_code=%s",
                            current_provider.provider_id,
                            current_provider.provider_name,
                            response.status_code,
                        )
                        total_retry_count += 1
                        break

                except Exception as e:
                    # Network or other exceptions
                    attempt_time = utc_now()
                    attempt_record = AttemptRecord(
                        provider=current_provider,
                        response=ProviderResponse(status_code=502, error=str(e)),
                        request_time=attempt_time,
                        attempt_index=attempt_index,
                    )
                    last_response = attempt_record.response
                    provider_response = attempt_record.response
                    attempt_index += 1
                    if on_failure_attempt is not None:
                        try:
                            await on_failure_attempt(attempt_record)
                        except Exception:
                            logger.exception(
                                "on_failure_attempt callback failed (stream exception): provider_id=%s attempt_index=%s",
                                current_provider.provider_id,
                                attempt_record.attempt_index,
                            )
                    logger.warning(
                        "Exception during stream request: provider_id=%s, provider_name=%s, protocol=%s, "
                        "exception=%s, retry_attempt=%s/%s",
                        current_provider.provider_id,
                        current_provider.provider_name,
                        current_provider.protocol,
                        str(e),
                        same_provider_retries + 1,
                        self.max_retries,
                    )
                    same_provider_retries += 1
                    total_retry_count += 1
                    if same_provider_retries < self.max_retries:
                        await asyncio.sleep(self.retry_delay_ms / 1000)
                        continue
                    else:
                        logger.warning(
                            "Max exception retries reached for stream provider: provider_id=%s, provider_name=%s, switching to next provider",
                            current_provider.provider_id,
                            current_provider.provider_name,
                        )
                        break

            if provider_response is not None:
                await self._record_health(current_provider, provider_response)
            
        # All failed, return last error
        yield last_chunk, last_response or ProviderResponse(
            status_code=503,
            error="All providers failed",
        ), last_provider, total_retry_count
    
    async def _get_next_untried_provider(
        self,
        candidates: list[CandidateProvider],
        tried_candidates: set[tuple[str, int] | tuple[str, int, str]],
        requested_model: str,
        current_provider: CandidateProvider,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next untried provider using the selection strategy

        Args:
            candidates: List of candidate providers
            tried_candidates: Set of tried candidate keys
            requested_model: Requested model name
            current_provider: Current provider
            input_tokens: Number of input tokens (for cost-based selection)
            image_count: Number of images (for per_image billing)

        Returns:
            Optional[CandidateProvider]: Next provider
        """
        candidate_keys = {self._candidate_key(c) for c in candidates}
        if candidate_keys and candidate_keys.issubset(tried_candidates):
            return None

        # Use the strategy to get the next provider
        next_provider = await self.strategy.get_next(
            candidates, requested_model, current_provider, input_tokens, image_count
        )

        # Keep trying until we find an untried provider or run out of options.
        # Some strategies can cycle indefinitely; cap iterations to avoid infinite loops.
        for _ in range(max(1, len(candidate_keys))):
            if next_provider is None:
                return None
            if self._candidate_key(next_provider) not in tried_candidates:
                return next_provider
            next_provider = await self.strategy.get_next(
                candidates, requested_model, next_provider, input_tokens, image_count
            )

        return None
