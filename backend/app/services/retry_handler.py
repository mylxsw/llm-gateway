"""
Retry and Failover Handler Module

Implements logic for request retry and provider failover.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.config import get_settings
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.strategy import SelectionStrategy

logger = logging.getLogger(__name__)


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
    
    async def execute_with_retry(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        forward_fn: Callable[[CandidateProvider], Any],
    ) -> RetryResult:
        """
        Execute Request with Retry
        
        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            forward_fn: Forwarding function, accepts CandidateProvider and returns ProviderResponse
        
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
            )
        
        # Track tried providers
        tried_providers: set[int] = set()
        total_retry_count = 0
        last_response: Optional[ProviderResponse] = None
        last_provider: Optional[CandidateProvider] = None
        
        # Select the first provider
        current_provider = await self.strategy.select(candidates, requested_model)
        
        while current_provider is not None:
            # Record current provider as tried
            tried_providers.add(current_provider.provider_id)
            last_provider = current_provider
            
            # Same provider retry count
            same_provider_retries = 0
            
            while same_provider_retries < self.max_retries:
                # Execute request
                response = await forward_fn(current_provider)
                last_response = response

                # Success response
                if response.is_success:
                    return RetryResult(
                        response=response,
                        retry_count=total_retry_count,
                        final_provider=current_provider,
                        success=True,
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
                candidates, tried_providers
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
        )

    async def execute_with_retry_stream(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        forward_stream_fn: Callable[[CandidateProvider], Any],
    ) -> Any:
        """
        Execute Streaming Request with Retry
        
        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            forward_stream_fn: Streaming forwarding function
            
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
        
        current_provider = await self.strategy.select(candidates, requested_model)
        
        while current_provider is not None:
            tried_providers.add(current_provider.provider_id)
            last_provider = current_provider
            same_provider_retries = 0
            
            while same_provider_retries < self.max_retries:
                try:
                    # Get generator
                    generator = forward_stream_fn(current_provider)
                    # Get first chunk
                    chunk, response = await anext(generator)
                    last_response = response
                    last_chunk = chunk

                    if response.is_success:
                        # Success, yield subsequent data
                        yield chunk, response, current_provider, total_retry_count
                        async for chunk, response in generator:
                            yield chunk, response, current_provider, total_retry_count
                        return

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
            
            next_provider = await self._get_next_untried_provider(
                candidates, tried_providers
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
    ) -> Optional[CandidateProvider]:
        """
        Get next untried provider
        
        Args:
            candidates: List of candidate providers
            tried_providers: Set of tried provider IDs
        
        Returns:
            Optional[CandidateProvider]: Next provider
        """
        for candidate in candidates:
            if candidate.provider_id not in tried_providers:
                return candidate
        return None