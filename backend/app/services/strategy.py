"""
Strategy Service Module

Provides implementation for provider selection strategies.
"""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio

from app.rules.models import CandidateProvider


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
    ) -> Optional[CandidateProvider]:
        """
        Select a provider from the candidate list
        
        Args:
            candidates: List of candidate providers
            requested_model: Requested model name (for state isolation)
        
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
    ) -> Optional[CandidateProvider]:
        """
        Get next provider (used for failover)
        
        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
        
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
    ) -> Optional[CandidateProvider]:
        """
        Round-robin provider selection
        
        Args:
            candidates: List of candidate providers (sorted by priority)
            requested_model: Requested model name
        
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
    ) -> Optional[CandidateProvider]:
        """
        Get next provider (used for failover)
        
        Args:
            candidates: List of candidate providers
            requested_model: Requested model name
            current: Current provider
        
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