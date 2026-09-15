import pytest

from app.domain.model import LatencyRoutingConfig
from app.rules.models import CandidateProvider
from app.services.provider_health import (
    HealthOutcome,
    ProviderHealthTracker,
    provider_health_key,
)
from app.services.retry_handler import RetryHandler
from app.services.strategy import PriorityStrategy
from app.services.stream_latency import StreamLatencyTracker, stream_chunk_has_text


class MutableClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_candidate(mapping_id: int, priority: int, weight: int = 10) -> CandidateProvider:
    return CandidateProvider(
        provider_mapping_id=mapping_id,
        provider_id=mapping_id,
        provider_name=f"provider-{mapping_id}",
        base_url=f"https://provider-{mapping_id}.example.com",
        protocol="openai",
        api_key="key",
        target_model=f"model-{mapping_id}",
        priority=priority,
        weight=weight,
    )


def config(**overrides) -> LatencyRoutingConfig:
    values = {
        "enabled": True,
        "ttft_threshold_ms": 1000,
        "min_samples": 3,
        "breach_count": 2,
        "penalty_weight_percent": 30,
        "cooldown_seconds": 60,
        "recovery_count": 2,
    }
    values.update(overrides)
    return LatencyRoutingConfig(**values)


@pytest.mark.parametrize(
    "chunk",
    [
        b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n',
        b'data: {"type":"content_block_start","content_block":{"type":"text","text":""}}\n\n',
        b": keepalive\n\n",
        b"data: [DONE]\n\n",
    ],
)
def test_stream_chunk_has_text_ignores_metadata(chunk: bytes) -> None:
    assert stream_chunk_has_text(chunk) is False


@pytest.mark.parametrize(
    "chunk",
    [
        b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n',
        b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hello"}}\n\n',
        b'data: {"type":"response.output_text.delta","delta":"hello"}\n\n',
        b'data: {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}\n\n',
        b"raw text",
    ],
)
def test_stream_chunk_has_text_recognizes_supported_payloads(chunk: bytes) -> None:
    assert stream_chunk_has_text(chunk) is True


@pytest.mark.asyncio
async def test_degrades_only_after_minimum_samples_and_consecutive_breaches() -> None:
    clock = MutableClock()
    tracker = StreamLatencyTracker(clock=clock)
    candidate = make_candidate(1, 0)
    policy = config()

    await tracker.record_ttft(candidate, policy, 100)
    await tracker.record_ttft(candidate, policy, 1500)
    snapshot = await tracker.record_ttft(candidate, policy, 1600)

    assert snapshot.sample_count == 3
    assert snapshot.consecutive_breaches == 2
    assert snapshot.degraded is True


@pytest.mark.asyncio
async def test_fast_sample_breaks_consecutive_breach_sequence() -> None:
    tracker = StreamLatencyTracker()
    candidate = make_candidate(1, 0)
    policy = config()

    for ttft in (1500, 100, 1500):
        snapshot = await tracker.record_ttft(candidate, policy, ttft)

    assert snapshot.sample_count == 3
    assert snapshot.consecutive_breaches == 1
    assert snapshot.degraded is False


@pytest.mark.asyncio
async def test_cooldown_probe_recovers_after_configured_healthy_samples() -> None:
    clock = MutableClock()
    tracker = StreamLatencyTracker(clock=clock)
    candidate = make_candidate(1, 0)
    policy = config()

    for ttft in (100, 1500, 1600):
        await tracker.record_ttft(candidate, policy, ttft)

    clock.now = 60
    snapshot = (await tracker.get_snapshots([candidate], policy))[
        provider_health_key(candidate)
    ]
    assert snapshot.degraded is False
    assert snapshot.probing is True

    snapshot = await tracker.record_ttft(candidate, policy, 200)
    assert snapshot.probing is True
    assert snapshot.consecutive_recoveries == 1

    snapshot = await tracker.record_ttft(candidate, policy, 300)
    assert snapshot.probing is False
    assert snapshot.consecutive_breaches == 0


@pytest.mark.asyncio
async def test_slow_probe_restarts_cooldown() -> None:
    clock = MutableClock()
    tracker = StreamLatencyTracker(clock=clock)
    candidate = make_candidate(1, 0)
    policy = config()

    for ttft in (100, 1500, 1600):
        await tracker.record_ttft(candidate, policy, ttft)
    clock.now = 60
    await tracker.get_snapshots([candidate], policy)

    snapshot = await tracker.record_ttft(candidate, policy, 1800)
    assert snapshot.degraded is True
    clock.now = 119
    snapshot = (await tracker.get_snapshots([candidate], policy))[
        provider_health_key(candidate)
    ]
    assert snapshot.degraded is True


@pytest.mark.asyncio
async def test_policy_change_discards_incompatible_history() -> None:
    tracker = StreamLatencyTracker()
    candidate = make_candidate(1, 0)
    original = config()
    for ttft in (100, 1500, 1600):
        await tracker.record_ttft(candidate, original, ttft)

    changed = config(ttft_threshold_ms=2000)
    snapshot = (await tracker.get_snapshots([candidate], changed))[
        provider_health_key(candidate)
    ]
    assert snapshot.sample_count == 0
    assert snapshot.degraded is False


@pytest.mark.asyncio
async def test_latency_degraded_candidate_falls_behind_healthy_lower_priority() -> None:
    tracker = StreamLatencyTracker()
    primary = make_candidate(1, priority=0, weight=10)
    fallback = make_candidate(2, priority=1, weight=10)
    policy = config()
    for ttft in (100, 1500, 1600):
        await tracker.record_ttft(primary, policy, ttft)

    handler = RetryHandler(
        PriorityStrategy(), latency_tracker=tracker, latency_config=policy
    )
    ordered = await handler.get_ordered_candidates(
        [primary, fallback], "requested-model"
    )

    assert [item.provider_mapping_id for item in ordered] == [2, 1]
    assert ordered[1].weight == 3


@pytest.mark.asyncio
async def test_disabled_policy_preserves_original_order() -> None:
    tracker = StreamLatencyTracker()
    primary = make_candidate(1, priority=0)
    fallback = make_candidate(2, priority=1)
    enabled = config()
    for ttft in (100, 1500, 1600):
        await tracker.record_ttft(primary, enabled, ttft)

    handler = RetryHandler(
        PriorityStrategy(),
        latency_tracker=tracker,
        latency_config=config(enabled=False),
    )
    ordered = await handler.get_ordered_candidates(
        [primary, fallback], "requested-model"
    )
    assert [item.provider_mapping_id for item in ordered] == [1, 2]

    # Disabling is also a reset boundary: re-enabling must not resurrect an
    # earlier degraded state.
    snapshot = (await tracker.get_snapshots([primary], enabled))[
        provider_health_key(primary)
    ]
    assert snapshot.sample_count == 0
    assert snapshot.degraded is False


@pytest.mark.asyncio
async def test_long_cooldown_is_not_removed_by_stale_cleanup() -> None:
    clock = MutableClock()
    tracker = StreamLatencyTracker(stale_after_seconds=10, clock=clock)
    candidate = make_candidate(1, 0)
    policy = config(cooldown_seconds=60)
    for ttft in (100, 1500, 1600):
        await tracker.record_ttft(candidate, policy, ttft)

    clock.now = 11
    snapshot = (await tracker.get_snapshots([candidate], policy))[
        provider_health_key(candidate)
    ]
    assert snapshot.degraded is True


@pytest.mark.asyncio
async def test_failure_degraded_candidate_stays_behind_latency_degraded_candidate() -> None:
    latency_tracker = StreamLatencyTracker()
    health_tracker = ProviderHealthTracker(
        min_samples=1, failure_rate_threshold=1.0
    )
    healthy = make_candidate(1, priority=2)
    slow = make_candidate(2, priority=0)
    failing = make_candidate(3, priority=0)
    policy = config()

    for ttft in (100, 1500, 1600):
        await latency_tracker.record_ttft(slow, policy, ttft)
    await health_tracker.record(failing, HealthOutcome.FAILURE)

    handler = RetryHandler(
        PriorityStrategy(),
        health_tracker=health_tracker,
        latency_tracker=latency_tracker,
        latency_config=policy,
    )
    ordered = await handler.get_ordered_candidates(
        [failing, slow, healthy], "requested-model"
    )

    assert [item.provider_mapping_id for item in ordered] == [1, 2, 3]
