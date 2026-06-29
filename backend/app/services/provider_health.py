"""Runtime provider health tracking and soft-circuit degradation."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider

logger = logging.getLogger(__name__)

ProviderHealthKey = tuple[str, int] | tuple[str, int, str]


class HealthOutcome(str, Enum):
    """Whether a logical provider call contributes to health statistics."""

    SUCCESS = "success"
    FAILURE = "failure"
    IGNORED = "ignored"


@dataclass(frozen=True)
class ProviderHealthSnapshot:
    """Health statistics for one provider/model candidate."""

    sample_count: int = 0
    failure_count: int = 0
    failure_rate: float = 0.0
    degraded: bool = False


@dataclass
class _HealthWindow:
    """Mutable rolling-window data with O(1) aggregate reads."""

    events: deque[tuple[float, bool]]
    failure_count: int = 0


def provider_health_key(candidate: CandidateProvider) -> ProviderHealthKey:
    """Use mapping identity when available so model failures stay isolated."""
    if candidate.provider_mapping_id is not None:
        return ("mapping", candidate.provider_mapping_id)
    return ("provider_target", candidate.provider_id, candidate.target_model)


def classify_provider_response(response: ProviderResponse) -> HealthOutcome:
    """Classify an upstream result conservatively for availability tracking.

    Client payload errors are ignored because they do not establish that a
    provider is unavailable. Authentication, timeout, throttling and upstream
    server errors do establish an availability/configuration problem.
    """
    if response.is_success:
        return HealthOutcome.SUCCESS

    if response.status_code in {401, 403, 408, 429} or response.status_code >= 500:
        return HealthOutcome.FAILURE

    return HealthOutcome.IGNORED


class ProviderHealthTracker:
    """Keep a low-volume, in-memory sliding window for provider outcomes.

    The tracker intentionally stores one event per logical provider call, not
    one event per physical retry. It is process-local; the interface can later
    be backed by Redis if the gateway runs multiple workers or instances.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        window_seconds: int = 600,
        min_samples: int = 6,
        failure_rate_threshold: float = 0.5,
        cleanup_interval_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        if min_samples < 1:
            raise ValueError("min_samples must be >= 1")
        if not 0 < failure_rate_threshold <= 1:
            raise ValueError("failure_rate_threshold must be in (0, 1]")
        if cleanup_interval_seconds is not None and cleanup_interval_seconds <= 0:
            raise ValueError("cleanup_interval_seconds must be > 0")

        self.enabled = enabled
        self.window_seconds = window_seconds
        self.min_samples = min_samples
        self.failure_rate_threshold = failure_rate_threshold
        self._clock = clock
        self._windows: dict[ProviderHealthKey, _HealthWindow] = {}
        self._known_states: dict[ProviderHealthKey, bool] = {}
        self._cleanup_interval_seconds = (
            cleanup_interval_seconds
            if cleanup_interval_seconds is not None
            else min(60.0, float(window_seconds))
        )
        self._next_cleanup_at = self._clock() + self._cleanup_interval_seconds
        self._lock = asyncio.Lock()

    @classmethod
    def from_settings(cls, settings) -> "ProviderHealthTracker":
        return cls(
            enabled=settings.PROVIDER_HEALTH_ENABLED,
            window_seconds=settings.PROVIDER_HEALTH_WINDOW_SECONDS,
            min_samples=settings.PROVIDER_HEALTH_MIN_SAMPLES,
            failure_rate_threshold=settings.PROVIDER_HEALTH_FAILURE_RATE_THRESHOLD,
        )

    def _prune(self, key: ProviderHealthKey, now: float) -> bool:
        window = self._windows.get(key)
        if window is None:
            return False
        cutoff = now - self.window_seconds
        while window.events and window.events[0][0] <= cutoff:
            _, failed = window.events.popleft()
            if failed:
                window.failure_count -= 1
        if not window.events:
            self._windows.pop(key, None)
            return True
        return False

    def _cleanup_expired(self, now: float) -> None:
        """Periodically prune every key, including removed/inactive mappings."""
        if now < self._next_cleanup_at:
            return

        for key in list(self._windows):
            removed = self._prune(key, now)
            if removed:
                self._known_states.pop(key, None)

        # A healthy/unknown key can be known without having window events.
        # Keeping it offers no value and would retain deleted mapping IDs.
        live_keys = self._windows.keys()
        for key in list(self._known_states):
            if key not in live_keys:
                self._known_states.pop(key, None)

        self._next_cleanup_at = now + self._cleanup_interval_seconds

    def _snapshot(self, key: ProviderHealthKey) -> ProviderHealthSnapshot:
        window = self._windows.get(key)
        if window is None:
            return ProviderHealthSnapshot()

        sample_count = len(window.events)
        failure_count = window.failure_count
        failure_rate = failure_count / sample_count
        degraded = (
            sample_count >= self.min_samples
            and failure_rate >= self.failure_rate_threshold
        )
        return ProviderHealthSnapshot(
            sample_count=sample_count,
            failure_count=failure_count,
            failure_rate=failure_rate,
            degraded=degraded,
        )

    def _state_transition(
        self,
        key: ProviderHealthKey,
        snapshot: ProviderHealthSnapshot,
    ) -> tuple[bool, bool] | None:
        previous = self._known_states.get(key, False)
        self._known_states[key] = snapshot.degraded
        if previous == snapshot.degraded:
            return None
        return previous, snapshot.degraded

    @staticmethod
    def _log_transition(
        key: ProviderHealthKey,
        snapshot: ProviderHealthSnapshot,
        transition: tuple[bool, bool] | None,
    ) -> None:
        if transition is None:
            return
        _, degraded = transition
        logger.warning(
            "Provider health state changed: key=%s state=%s samples=%s failures=%s failure_rate=%.3f",
            key,
            "degraded" if degraded else "healthy",
            snapshot.sample_count,
            snapshot.failure_count,
            snapshot.failure_rate,
        )

    async def get_snapshots(
        self,
        candidates: Iterable[CandidateProvider],
    ) -> dict[ProviderHealthKey, ProviderHealthSnapshot]:
        keys = list(
            dict.fromkeys(provider_health_key(candidate) for candidate in candidates)
        )
        return await self._get_snapshots_for_keys(keys)

    async def get_mapping_snapshots(
        self,
        mapping_ids: Iterable[int],
    ) -> dict[int, ProviderHealthSnapshot]:
        """Return runtime health keyed by model-provider mapping ID."""
        keys: list[ProviderHealthKey] = list(
            dict.fromkeys(("mapping", mapping_id) for mapping_id in mapping_ids)
        )
        snapshots = await self._get_snapshots_for_keys(keys)
        return {key[1]: snapshot for key, snapshot in snapshots.items()}

    async def _get_snapshots_for_keys(
        self,
        keys: list[ProviderHealthKey],
    ) -> dict[ProviderHealthKey, ProviderHealthSnapshot]:
        if not self.enabled:
            return {key: ProviderHealthSnapshot() for key in keys}

        now = self._clock()
        transitions: list[
            tuple[ProviderHealthKey, ProviderHealthSnapshot, tuple[bool, bool] | None]
        ] = []
        async with self._lock:
            self._cleanup_expired(now)
            snapshots: dict[ProviderHealthKey, ProviderHealthSnapshot] = {}
            for key in keys:
                self._prune(key, now)
                snapshot = self._snapshot(key)
                snapshots[key] = snapshot
                transitions.append((key, snapshot, self._state_transition(key, snapshot)))

        for key, snapshot, transition in transitions:
            self._log_transition(key, snapshot, transition)
        return snapshots

    async def record(
        self,
        candidate: CandidateProvider,
        outcome: HealthOutcome,
    ) -> ProviderHealthSnapshot:
        if not self.enabled or outcome is HealthOutcome.IGNORED:
            return ProviderHealthSnapshot()

        key = provider_health_key(candidate)
        now = self._clock()
        async with self._lock:
            self._cleanup_expired(now)
            self._prune(key, now)
            window = self._windows.get(key)
            if window is None:
                window = _HealthWindow(events=deque())
                self._windows[key] = window
            failed = outcome is HealthOutcome.FAILURE
            window.events.append((now, failed))
            if failed:
                window.failure_count += 1
            snapshot = self._snapshot(key)
            transition = self._state_transition(key, snapshot)

        self._log_transition(key, snapshot, transition)
        return snapshot

    async def record_response(
        self,
        candidate: CandidateProvider,
        response: ProviderResponse,
    ) -> ProviderHealthSnapshot:
        return await self.record(candidate, classify_provider_response(response))

    async def reset(self) -> None:
        """Clear all runtime state. Primarily useful for tests and operations."""
        async with self._lock:
            self._windows.clear()
            self._known_states.clear()
            self._next_cleanup_at = self._clock() + self._cleanup_interval_seconds
