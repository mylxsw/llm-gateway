"""
Strategy Service Module

Provides implementation for provider selection strategies.
"""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio
import logging

from app.rules.models import CandidateProvider
from app.common.costs import resolve_billing, calculate_cost_from_billing

logger = logging.getLogger(__name__)


class SelectionStrategy(ABC):
    """
    Provider Selection Strategy Abstract Base Class
    
    Defines the interface for selecting a provider from a list of candidates.
    """
    
    @abstractmethod
    async def select(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        input_tokens: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Select a provider from the candidate list

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name (for state isolation)
            input_tokens: Number of input tokens (for cost-based selection)

        Returns:
            Optional[CandidateProvider]: Selected provider, or None if no provider available
        """
        pass
    
    @abstractmethod
    async def get_next(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        current: CandidateProvider,
        input_tokens: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next provider (used for failover)

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
            input_tokens: Number of input tokens (for cost-based selection)

        Returns:
            Optional[CandidateProvider]: Next provider, or None if no provider available
        """
        pass


class RoundRobinStrategy(SelectionStrategy):
    """
    Round Robin Strategy
    
    Selects providers in a round-robin fashion to ensure even distribution of requests.
    Uses atomic counters for concurrency safety.
    """
    
    def __init__(self):
        """Initialize Strategy"""
        # Maintain independent counters for each model
        self._counters: dict[str, int] = {}
        # Lock to protect counters
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Get lock (lazy loading)"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    async def select(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        input_tokens: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Round-robin provider selection

        Args:
            candidates: List of candidate providers (sorted by priority)
            requested_model: Requested model name
            input_tokens: Number of input tokens (unused in round-robin)

        Returns:
            Optional[CandidateProvider]: Selected provider
        """
        if not candidates:
            return None
        
        async with self.lock:
            # Get current count
            counter = self._counters.get(requested_model, 0)
            # Select provider
            index = counter % len(candidates)
            # Update count
            self._counters[requested_model] = counter + 1
        
        return candidates[index]
    
    async def get_next(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        current: CandidateProvider,
        input_tokens: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next provider (used for failover)

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
            input_tokens: Number of input tokens (unused in round-robin)

        Returns:
            Optional[CandidateProvider]: Next provider
        """
        if not candidates or len(candidates) <= 1:
            return None
        
        # Find index of current provider
        current_index = -1
        for i, c in enumerate(candidates):
            if c.provider_id == current.provider_id:
                current_index = i
                break
        
        if current_index == -1:
            return None
        
        # Return next provider
        next_index = (current_index + 1) % len(candidates)
        if next_index == current_index:
            return None
        
        return candidates[next_index]
    
    def reset(self, requested_model: Optional[str] = None) -> None:
        """
        Reset counters (for testing)

        Args:
            requested_model: Specific model name, resets all if None
        """
        if requested_model:
            self._counters.pop(requested_model, None)
        else:
            self._counters.clear()


class CostFirstStrategy(SelectionStrategy):
    """
    Cost First Strategy

    Selects providers based on lowest cost for the current request.
    Calculates cost based on input tokens and provider billing configuration.
    Falls back to next lowest cost provider on failure.
    """

    def _calculate_input_cost(self, candidate: CandidateProvider, input_tokens: int) -> float:
        """
        Calculate input cost for a candidate provider

        Args:
            candidate: Candidate provider with billing information
            input_tokens: Number of input tokens

        Returns:
            float: Estimated input cost in USD
        """
        # Resolve billing configuration
        billing = resolve_billing(
            input_tokens=input_tokens,
            model_input_price=candidate.model_input_price,
            model_output_price=candidate.model_output_price,
            provider_billing_mode=candidate.billing_mode,
            provider_per_request_price=candidate.per_request_price,
            provider_tiered_pricing=candidate.tiered_pricing,
            provider_input_price=candidate.input_price,
            provider_output_price=candidate.output_price,
        )

        # Calculate cost (only input cost, as we're selecting before making the request)
        cost_breakdown = calculate_cost_from_billing(
            input_tokens=input_tokens,
            output_tokens=0,  # We don't know output tokens yet
            billing=billing,
        )

        # For per_request billing, use the full per_request_price as the cost
        # For token-based billing, use only the input_cost
        return cost_breakdown.total_cost if billing.billing_mode == "per_request" else cost_breakdown.input_cost

    async def select(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        input_tokens: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Select provider with lowest cost

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            input_tokens: Number of input tokens

        Returns:
            Optional[CandidateProvider]: Provider with lowest cost, or None if no providers available
        """
        if not candidates:
            return None

        # If no input_tokens provided, fall back to first candidate (by priority)
        if input_tokens is None or input_tokens == 0:
            logger.warning("CostFirstStrategy: No input_tokens provided, falling back to first candidate")
            return candidates[0]

        # Calculate cost for each candidate
        candidates_with_cost = []
        for candidate in candidates:
            try:
                cost = self._calculate_input_cost(candidate, input_tokens)
                candidates_with_cost.append((candidate, cost))
                logger.debug(
                    f"CostFirstStrategy: Provider {candidate.provider_name} (ID: {candidate.provider_id}) "
                    f"estimated input cost: ${cost:.6f} for {input_tokens} input tokens"
                )
            except Exception as e:
                logger.error(
                    f"CostFirstStrategy: Error calculating cost for provider {candidate.provider_name} "
                    f"(ID: {candidate.provider_id}): {e}"
                )
                # Assign a high cost to providers with calculation errors
                # so they're deprioritized but not excluded
                candidates_with_cost.append((candidate, float('inf')))

        # Sort by cost (lowest first), then by priority, then by provider_id
        candidates_with_cost.sort(key=lambda x: (x[1], x[0].priority, x[0].provider_id))

        selected = candidates_with_cost[0][0]
        selected_cost = candidates_with_cost[0][1]

        logger.info(
            f"CostFirstStrategy: Selected provider {selected.provider_name} (ID: {selected.provider_id}) "
            f"with estimated input cost ${selected_cost:.6f}"
        )

        return selected

    async def get_next(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        current: CandidateProvider,
        input_tokens: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next provider by cost (used for failover)

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
            input_tokens: Number of input tokens

        Returns:
            Optional[CandidateProvider]: Next cheapest provider, or None if no more providers
        """
        if not candidates or len(candidates) <= 1:
            return None

        # If no input_tokens provided, fall back to simple next-in-list logic
        if input_tokens is None or input_tokens == 0:
            # Find index of current provider
            current_index = -1
            for i, c in enumerate(candidates):
                if c.provider_id == current.provider_id:
                    current_index = i
                    break

            if current_index == -1:
                return None

            next_index = (current_index + 1) % len(candidates)
            if next_index == current_index:
                return None

            return candidates[next_index]

        # Re-sort candidates by cost to find the next cheapest option
        candidates_with_cost = []
        for candidate in candidates:
            try:
                cost = self._calculate_input_cost(candidate, input_tokens)
                candidates_with_cost.append((candidate, cost))
            except Exception as e:
                logger.error(
                    f"CostFirstStrategy.get_next: Error calculating cost for provider "
                    f"{candidate.provider_name} (ID: {candidate.provider_id}): {e}"
                )
                candidates_with_cost.append((candidate, float('inf')))

        # Sort by cost, then priority, then provider_id
        candidates_with_cost.sort(key=lambda x: (x[1], x[0].priority, x[0].provider_id))

        # Find current provider in the sorted list
        current_index = -1
        for i, (c, _) in enumerate(candidates_with_cost):
            if c.provider_id == current.provider_id:
                current_index = i
                break

        if current_index == -1:
            return None

        # Return next provider in the sorted list
        next_index = current_index + 1
        if next_index >= len(candidates_with_cost):
            return None

        next_candidate = candidates_with_cost[next_index][0]
        next_cost = candidates_with_cost[next_index][1]

        logger.info(
            f"CostFirstStrategy: Failover to provider {next_candidate.provider_name} "
            f"(ID: {next_candidate.provider_id}) with estimated input cost ${next_cost:.6f}"
        )

        return next_candidate