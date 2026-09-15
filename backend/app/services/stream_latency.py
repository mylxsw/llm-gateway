"""Streaming time-to-first-text tracking used by provider scheduling."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable

from app.domain.model import LatencyRoutingConfig
from app.rules.models import CandidateProvider
from app.services.provider_health import ProviderHealthKey, provider_health_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamLatencySnapshot:
    sample_count: int = 0
    average_ttft_ms: float = 0.0
    consecutive_breaches: int = 0
    consecutive_recoveries: int = 0
    degraded: bool = False
    probing: bool = False


@dataclass
class _LatencyWindow:
    samples: deque[float]
    last_updated_at: float
    config_signature: tuple[int, ...]
    consecutive_breaches: int = 0
    consecutive_recoveries: int = 0
    degraded_until: float = 0.0
    probing: bool = False


def _config_signature(config: LatencyRoutingConfig) -> tuple[int, ...]:
    return (
        config.ttft_threshold_ms,
        config.min_samples,
        config.breach_count,
        config.penalty_weight_percent,
        config.cooldown_seconds,
        config.recovery_count,
    )


def _non_empty_text(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(
            isinstance(item, dict)
            and item.get("type") in {"text", "output_text"}
            and _non_empty_text(item.get("text"))
            for item in value
        )
    return False


def _payload_has_text(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False

    # OpenAI chat completions.
    for choice in payload.get("choices") or []:
        if isinstance(choice, dict):
            delta = choice.get("delta")
            if isinstance(delta, dict) and _non_empty_text(delta.get("content")):
                return True

    # OpenAI Responses and Anthropic Messages.
    delta = payload.get("delta")
    if _non_empty_text(delta):
        return True
    if isinstance(delta, dict) and _non_empty_text(delta.get("text")):
        return True

    content_block = payload.get("content_block")
    if isinstance(content_block, dict) and _non_empty_text(content_block.get("text")):
        return True

    # Google GenerateContent streams.
    for candidate in payload.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        for part in content.get("parts") or []:
            if isinstance(part, dict) and _non_empty_text(part.get("text")):
                return True

    return False


def stream_chunk_has_text(chunk: bytes) -> bool:
    """Return True only when a stream chunk carries user-visible model text."""
    if not chunk or not chunk.strip():
        return False

    text = chunk.decode("utf-8", errors="ignore")
    data_lines = [
        line[5:].strip()
        for line in text.splitlines()
        if line.startswith("data:")
    ]
    if not data_lines:
        if any(
            line.startswith((":", "event:", "id:", "retry:"))
            for line in text.splitlines()
        ):
            return False
        # Some compatible providers return a raw text stream instead of SSE.
        try:
            return _payload_has_text(json.loads(text))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return bool(text.strip())

    for data in data_lines:
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if _payload_has_text(payload):
            return True
    return False


class StreamLatencyTracker:
    """Process-local soft circuit for slow streaming provider mappings."""

    def __init__(
        self,
        *,
        stale_after_seconds: int = 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if stale_after_seconds < 1:
            raise ValueError("stale_after_seconds must be >= 1")
        self._stale_after_seconds = stale_after_seconds
        self._clock = clock
        self._windows: dict[ProviderHealthKey, _LatencyWindow] = {}
        self._lock = asyncio.Lock()

    def _window(
        self,
        key: ProviderHealthKey,
        config: LatencyRoutingConfig,
        now: float,
    ) -> _LatencyWindow:
        signature = _config_signature(config)
        window = self._windows.get(key)
        if window is None or window.config_signature != signature:
            window = _LatencyWindow(
                samples=deque(maxlen=config.min_samples),
                last_updated_at=now,
                config_signature=signature,
            )
            self._windows[key] = window
        return window

    def _cleanup(self, now: float) -> None:
        cutoff = now - self._stale_after_seconds
        for key, window in list(self._windows.items()):
            if window.last_updated_at <= cutoff and window.degraded_until <= now:
                self._windows.pop(key, None)

    @staticmethod
    def _advance_cooldown(window: _LatencyWindow, now: float) -> None:
        if window.degraded_until and now >= window.degraded_until:
            window.degraded_until = 0.0
            window.probing = True
            window.consecutive_recoveries = 0

    @staticmethod
    def _snapshot(window: _LatencyWindow, now: float) -> StreamLatencySnapshot:
        return StreamLatencySnapshot(
            sample_count=len(window.samples),
            average_ttft_ms=(sum(window.samples) / len(window.samples))
            if window.samples
            else 0.0,
            consecutive_breaches=window.consecutive_breaches,
            consecutive_recoveries=window.consecutive_recoveries,
            degraded=window.degraded_until > now,
            probing=window.probing,
        )

    async def get_snapshots(
        self,
        candidates: Iterable[CandidateProvider],
        config: LatencyRoutingConfig,
    ) -> dict[ProviderHealthKey, StreamLatencySnapshot]:
        keys = list(dict.fromkeys(provider_health_key(item) for item in candidates))
        if not config.enabled:
            async with self._lock:
                for key in keys:
                    self._windows.pop(key, None)
            return {key: StreamLatencySnapshot() for key in keys}

        now = self._clock()
        async with self._lock:
            self._cleanup(now)
            snapshots = {}
            for key in keys:
                window = self._windows.get(key)
                if window is None:
                    snapshots[key] = StreamLatencySnapshot()
                    continue
                if window.config_signature != _config_signature(config):
                    self._windows.pop(key, None)
                    snapshots[key] = StreamLatencySnapshot()
                    continue
                self._advance_cooldown(window, now)
                snapshots[key] = self._snapshot(window, now)
            return snapshots

    async def record_ttft(
        self,
        candidate: CandidateProvider,
        config: LatencyRoutingConfig,
        ttft_ms: float,
    ) -> StreamLatencySnapshot:
        if not config.enabled or ttft_ms < 0:
            return StreamLatencySnapshot()

        key = provider_health_key(candidate)
        now = self._clock()
        async with self._lock:
            self._cleanup(now)
            window = self._window(key, config, now)
            self._advance_cooldown(window, now)
            window.samples.append(ttft_ms)
            window.last_updated_at = now
            breached = ttft_ms > config.ttft_threshold_ms

            if window.probing:
                if breached:
                    window.probing = False
                    window.consecutive_recoveries = 0
                    window.consecutive_breaches = config.breach_count
                    window.degraded_until = now + config.cooldown_seconds
                else:
                    window.consecutive_recoveries += 1
                    if window.consecutive_recoveries >= config.recovery_count:
                        window.probing = False
                        window.consecutive_recoveries = 0
                        window.consecutive_breaches = 0
            elif window.degraded_until <= now:
                window.consecutive_breaches = (
                    window.consecutive_breaches + 1 if breached else 0
                )
                if (
                    len(window.samples) >= config.min_samples
                    and window.consecutive_breaches >= config.breach_count
                ):
                    window.degraded_until = now + config.cooldown_seconds
                    window.consecutive_recoveries = 0

            snapshot = self._snapshot(window, now)

        if snapshot.degraded:
            logger.warning(
                "Provider streaming latency degraded: key=%s ttft_ms=%.1f threshold_ms=%s cooldown_seconds=%s",
                key,
                ttft_ms,
                config.ttft_threshold_ms,
                config.cooldown_seconds,
            )
        return snapshot

    async def reset(self) -> None:
        async with self._lock:
            self._windows.clear()
