"""
Retry and Failover Handler Module

Implements logic for request retry and provider failover.
"""

import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Callable, Optional, Awaitable

from app.config import get_settings
from app.common.time import utc_now
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
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
    
    def __init__(self, strategy: SelectionStrategy):
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

    async def get_ordered_candidates(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        *,
        input_tokens: Optional[int] = None,
    ) -> list[CandidateProvider]:
        """
        Get candidate order based on the selection strategy.

        This mirrors provider selection + failover ordering without making requests.
        """
        if not candidates:
            return []

        ordered: list[CandidateProvider] = []
        tried_providers: set[int] = set()
        current_provider = await self.strategy.select(candidates, requested_model, input_tokens)
        while current_provider is not None:
            if current_provider.provider_id in tried_providers:
                break
            ordered.append(current_provider)
            tried_providers.add(current_provider.provider_id)
            if len(tried_providers) >= len(candidates):
                break
            current_provider = await self._get_next_untried_provider(
                candidates, tried_providers, requested_model, current_provider, input_tokens
            )

        if len(ordered) == len(candidates):
            return ordered

        for candidate in candidates:
            if candidate.provider_id not in tried_providers:
                ordered.append(candidate)

        return ordered
    
    async def execute_with_retry(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        forward_fn: Callable[[CandidateProvider], Any],
        *,
        input_tokens: Optional[int] = None,
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
        
        # Track tried providers
        tried_providers: set[int] = set()
        total_retry_count = 0
        last_response: Optional[ProviderResponse] = None
        last_provider: Optional[CandidateProvider] = None
        attempts: list[AttemptRecord] = []
        attempt_index = 0
        
        # Select the first provider
        current_provider = await self.strategy.select(candidates, requested_model, input_tokens)
        
        while current_provider is not None:
            # Record current provider as tried
            tried_providers.add(current_provider.provider_id)
            last_provider = current_provider
            
            # Same provider retry count
            same_provider_retries = 0
            
            while same_provider_retries < self.max_retries:
                # Execute request
                attempt_time = utc_now()
                response = await forward_fn(current_provider)
                last_response = response
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
            
            # Try to switch to the next provider
            next_provider = await self._get_next_untried_provider(
                candidates, tried_providers, requested_model, current_provider, input_tokens
            )
            
            if next_provider is None:
                # All providers tried
                break
            
            current_provider = next_provider
        
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
            
        tried_providers: set[int] = set()
        total_retry_count = 0
        last_chunk: bytes = b""
        last_response: Optional[ProviderResponse] = None
        last_provider: Optional[CandidateProvider] = None
        attempt_index = 0

        current_provider = await self.strategy.select(candidates, requested_model, input_tokens)
        
        while current_provider is not None:
            tried_providers.add(current_provider.provider_id)
            last_provider = current_provider
            same_provider_retries = 0
            pending_attempt_record: Optional[AttemptRecord] = None
            
            while same_provider_retries < self.max_retries:
                try:
                    # Get generator
                    attempt_time = utc_now()
                    generator = forward_stream_fn(current_provider)
                    # Get first chunk
                    chunk, response = await anext(generator)
                    last_response = response
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
                        async for chunk, response in generator:
                            yield chunk, response, current_provider, total_retry_count
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
                            pending_attempt_record = attempt_record
                            break
                    else:
                        logger.warning(
                            "Client error from stream provider, switching: provider_id=%s, provider_name=%s, status_code=%s",
                            current_provider.provider_id,
                            current_provider.provider_name,
                            response.status_code,
                        )
                        total_retry_count += 1
                        pending_attempt_record = attempt_record
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
                        pending_attempt_record = attempt_record
                        break
            
            next_provider = await self._get_next_untried_provider(
                candidates, tried_providers, requested_model, current_provider, input_tokens
            )
            if next_provider is None:
                break
            current_provider = next_provider
            
        # All failed, return last error
        yield last_chunk, last_response or ProviderResponse(
            status_code=503,
            error="All providers failed",
        ), last_provider, total_retry_count
    
    async def _get_next_untried_provider(
        self,
        candidates: list[CandidateProvider],
        tried_providers: set[int],
        requested_model: str,
        current_provider: CandidateProvider,
        input_tokens: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next untried provider using the selection strategy

        Args:
            candidates: List of candidate providers
            tried_providers: Set of tried provider IDs
            requested_model: Requested model name
            current_provider: Current provider
            input_tokens: Number of input tokens (for cost-based selection)

        Returns:
            Optional[CandidateProvider]: Next provider
        """
        candidate_provider_ids = {c.provider_id for c in candidates}
        if candidate_provider_ids and candidate_provider_ids.issubset(tried_providers):
            return None

        # Use the strategy to get the next provider
        next_provider = await self.strategy.get_next(
            candidates, requested_model, current_provider, input_tokens
        )

        # Keep trying until we find an untried provider or run out of options.
        # Some strategies can cycle indefinitely; cap iterations to avoid infinite loops.
        for _ in range(max(1, len(candidate_provider_ids))):
            if next_provider is None:
                return None
            if next_provider.provider_id not in tried_providers:
                return next_provider
            next_provider = await self.strategy.get_next(
                candidates, requested_model, next_provider, input_tokens
            )

        return None
