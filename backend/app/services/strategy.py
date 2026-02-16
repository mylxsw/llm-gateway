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


def _candidate_key(candidate: CandidateProvider) -> tuple[str, int] | tuple[str, int, str]:
    if candidate.provider_mapping_id is not None:
        return ("mapping", candidate.provider_mapping_id)
    return ("provider_target", candidate.provider_id, candidate.target_model)


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
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Select a provider from the candidate list

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name (for state isolation)
            input_tokens: Number of input tokens (for cost-based selection)
            image_count: Number of images (for per_image billing)

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
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next provider (used for failover)

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
            input_tokens: Number of input tokens (for cost-based selection)
            image_count: Number of images (for per_image billing)

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
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Round-robin provider selection

        Args:
            candidates: List of candidate providers (sorted by priority)
            requested_model: Requested model name
            input_tokens: Number of input tokens (unused in round-robin)
            image_count: Number of images (unused in round-robin)

        Returns:
            Optional[CandidateProvider]: Selected provider
        """
        if not candidates:
            return None

        # Calculate total weight
        total_weight = sum(c.weight for c in candidates)
        if total_weight <= 0:
            # Fallback to simple round robin if weights are invalid
            total_weight = len(candidates)
            use_simple_rr = True
        else:
            use_simple_rr = False

        async with self.lock:
            # Get current count
            counter = self._counters.get(requested_model, 0)

            if use_simple_rr:
                index = counter % len(candidates)
                selected = candidates[index]
            else:
                # Weighted selection
                current_val = counter % total_weight
                selected = None
                cumulative_weight = 0
                for candidate in candidates:
                    cumulative_weight += candidate.weight
                    if current_val < cumulative_weight:
                        selected = candidate
                        break

                # Should not happen if logic is correct
                if selected is None:
                    selected = candidates[0]

            # Update count
            self._counters[requested_model] = counter + 1

        return selected

    async def get_next(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        current: CandidateProvider,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next provider (used for failover)

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
            input_tokens: Number of input tokens (unused in round-robin)
            image_count: Number of images (unused in round-robin)

        Returns:
            Optional[CandidateProvider]: Next provider
        """
        if not candidates or len(candidates) <= 1:
            return None

        # Find index of current provider
        current_index = -1
        for i, c in enumerate(candidates):
            if _candidate_key(c) == _candidate_key(current):
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


class PriorityStrategy(SelectionStrategy):
    """
    Priority Strategy

    Selects providers by priority (lower value means higher priority).
    Uses round robin within the same priority group.
    """

    def __init__(self):
        """Initialize Strategy"""
        self._counters: dict[tuple[str, int], int] = {}
        self._last_selected_index: dict[tuple[str, int], int] = {}
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Get lock (lazy loading)"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _group_candidates(
        self,
        candidates: list[CandidateProvider],
    ) -> dict[int, list[CandidateProvider]]:
        grouped: dict[int, list[CandidateProvider]] = {}
        for candidate in candidates:
            grouped.setdefault(candidate.priority, []).append(candidate)
        for priority, group in grouped.items():
            grouped[priority] = sorted(
                group,
                key=lambda c: (
                    c.provider_id,
                    c.target_model,
                    c.provider_mapping_id or 0,
                ),
            )
        return grouped

    async def _select_from_group(
        self,
        group: list[CandidateProvider],
        requested_model: str,
        priority: int,
    ) -> CandidateProvider:
        key = (requested_model, priority)
        
        # Calculate total weight
        total_weight = sum(c.weight for c in group)
        if total_weight <= 0:
            total_weight = len(group)
            use_simple_rr = True
        else:
            use_simple_rr = False
            
        async with self.lock:
            counter = self._counters.get(key, 0)
            
            if use_simple_rr:
                index = counter % len(group)
                selected = group[index]
            else:
                current_val = counter % total_weight
                selected = None
                cumulative_weight = 0
                for i, candidate in enumerate(group):
                    cumulative_weight += candidate.weight
                    if current_val < cumulative_weight:
                        selected = candidate
                        index = i
                        break
                
                if selected is None:
                    selected = group[0]
                    index = 0

            self._counters[key] = counter + 1
            self._last_selected_index[key] = index
        return selected

    async def select(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Select provider by priority with round robin within same priority

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            input_tokens: Number of input tokens (unused in priority strategy)
            image_count: Number of images (unused in priority strategy)

        Returns:
            Optional[CandidateProvider]: Selected provider
        """
        if not candidates:
            return None

        grouped = self._group_candidates(candidates)
        top_priority = min(grouped.keys())
        return await self._select_from_group(grouped[top_priority], requested_model, top_priority)

    async def get_next(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        current: CandidateProvider,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next provider by priority (used for failover)

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
            input_tokens: Number of input tokens (unused in priority strategy)
            image_count: Number of images (unused in priority strategy)

        Returns:
            Optional[CandidateProvider]: Next provider, or None if no provider available
        """
        if not candidates or len(candidates) <= 1:
            return None

        grouped = self._group_candidates(candidates)
        priorities = sorted(grouped.keys())

        if current.priority not in grouped:
            return None

        group = grouped[current.priority]
        if len(group) > 1:
            key = (requested_model, current.priority)
            rotation_start = self._last_selected_index.get(key)
            if rotation_start is None or rotation_start >= len(group):
                rotation_start = next(
                    (i for i, c in enumerate(group) if _candidate_key(c) == _candidate_key(current)),
                    0,
                )

            rotated = group[rotation_start:] + group[:rotation_start]
            current_index = next(
                (i for i, c in enumerate(rotated) if _candidate_key(c) == _candidate_key(current)),
                -1,
            )
            if current_index != -1 and current_index + 1 < len(rotated):
                return rotated[current_index + 1]

        current_priority_index = priorities.index(current.priority)
        if current_priority_index + 1 >= len(priorities):
            return None

        next_priority = priorities[current_priority_index + 1]
        next_group = grouped[next_priority]
        return await self._select_from_group(next_group, requested_model, next_priority)

    def reset(self, requested_model: Optional[str] = None) -> None:
        """
        Reset counters (for testing)

        Args:
            requested_model: Specific model name, resets all if None
        """
        if requested_model:
            keys = [key for key in self._counters if key[0] == requested_model]
            for key in keys:
                self._counters.pop(key, None)
                self._last_selected_index.pop(key, None)
        else:
            self._counters.clear()
            self._last_selected_index.clear()


class CostFirstStrategy(SelectionStrategy):
    """
    Cost First Strategy

    Selects providers based on lowest cost for the current request.
    Calculates cost based on input tokens and provider billing configuration.
    Falls back to next lowest cost provider on failure.
    If multiple providers have the same lowest cost, uses Round Robin to distribute load.
    """

    def __init__(self):
        """Initialize Strategy"""
        self._round_robin = RoundRobinStrategy()

    def _calculate_input_cost(self, candidate: CandidateProvider, input_tokens: int, image_count: Optional[int] = None) -> float:
        """
        Calculate input cost for a candidate provider

        Args:
            candidate: Candidate provider with billing information
            input_tokens: Number of input tokens
            image_count: Number of images (for per_image billing)

        Returns:
            float: Estimated input cost in USD
        """
        # Resolve billing configuration
        billing = resolve_billing(
            input_tokens=input_tokens,
            model_input_price=candidate.model_input_price,
            model_output_price=candidate.model_output_price,
            model_billing_mode=candidate.model_billing_mode,
            model_per_request_price=candidate.model_per_request_price,
            model_per_image_price=candidate.model_per_image_price,
            model_tiered_pricing=candidate.model_tiered_pricing,
            provider_billing_mode=candidate.billing_mode,
            provider_per_request_price=candidate.per_request_price,
            provider_per_image_price=candidate.per_image_price,
            provider_tiered_pricing=candidate.tiered_pricing,
            provider_input_price=candidate.input_price,
            provider_output_price=candidate.output_price,
        )

        # Calculate cost (only input cost, as we're selecting before making the request)
        cost_breakdown = calculate_cost_from_billing(
            input_tokens=input_tokens,
            output_tokens=0,  # We don't know output tokens yet
            billing=billing,
            image_count=image_count,
        )

        # For per_request/per_image billing, use the full total_cost
        # For token-based billing, use only the input_cost
        return cost_breakdown.total_cost if billing.billing_mode in ("per_request", "per_image") else cost_breakdown.input_cost

    async def select(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        input_tokens: Optional[int] = None,
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Select provider with lowest cost

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            input_tokens: Number of input tokens
            image_count: Number of images (for per_image billing)

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
                cost = self._calculate_input_cost(candidate, input_tokens, image_count)
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
        candidates_with_cost.sort(
            key=lambda x: (
                x[1],
                x[0].priority,
                x[0].provider_id,
                x[0].target_model,
                x[0].provider_mapping_id or 0,
            )
        )

        # Find all candidates with the same lowest cost
        min_cost = candidates_with_cost[0][1]
        lowest_cost_candidates = []
        # Use a small epsilon for float comparison if needed, but costs are likely exact or distinctly different
        # Using exact match for now as price configuration is usually precise
        for c, cost in candidates_with_cost:
            if abs(cost - min_cost) < 1e-9:
                lowest_cost_candidates.append(c)
            else:
                break
        
        if len(lowest_cost_candidates) > 1:
            # Use Round Robin for ties
            selected = await self._round_robin.select(lowest_cost_candidates, requested_model)
            selected_cost = min_cost
            logger.info(
                f"CostFirstStrategy: Found {len(lowest_cost_candidates)} providers with same lowest cost "
                f"(${min_cost:.6f}). Using Round Robin selection."
            )
        else:
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
        image_count: Optional[int] = None,
    ) -> Optional[CandidateProvider]:
        """
        Get next provider by cost (used for failover)

        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
            input_tokens: Number of input tokens
            image_count: Number of images (for per_image billing)

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
                if _candidate_key(c) == _candidate_key(current):
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
                cost = self._calculate_input_cost(candidate, input_tokens, image_count)
                candidates_with_cost.append((candidate, cost))
            except Exception as e:
                logger.error(
                    f"CostFirstStrategy.get_next: Error calculating cost for provider "
                    f"{candidate.provider_name} (ID: {candidate.provider_id}): {e}"
                )
                candidates_with_cost.append((candidate, float('inf')))

        # Sort by cost, then priority, then provider_id
        candidates_with_cost.sort(
            key=lambda x: (
                x[1],
                x[0].priority,
                x[0].provider_id,
                x[0].target_model,
                x[0].provider_mapping_id or 0,
            )
        )

        # Find current provider in the sorted list
        current_index = -1
        for i, (c, _) in enumerate(candidates_with_cost):
            if _candidate_key(c) == _candidate_key(current):
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
