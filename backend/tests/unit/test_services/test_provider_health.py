import pytest

from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider
from app.services.provider_health import (
    HealthOutcome,
    ProviderHealthTracker,
    classify_provider_response,
    provider_health_key,
)
from app.services.retry_handler import RetryHandler
from app.services.strategy import CostFirstStrategy, PriorityStrategy, RoundRobinStrategy


class MutableClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_candidate(
    mapping_id: int,
    *,
    priority: int = 0,
    weight: int = 1,
    input_price: float = 1.0,
) -> CandidateProvider:
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
        billing_mode="token_flat",
        input_price=input_price,
        output_price=input_price,
    )


@pytest.mark.asyncio
async def test_degrades_only_after_minimum_samples_and_expires() -> None:
    clock = MutableClock()
    tracker = ProviderHealthTracker(
        window_seconds=600,
        min_samples=6,
        failure_rate_threshold=0.5,
        clock=clock,
    )
    candidate = make_candidate(1)

    for _ in range(5):
        await tracker.record(candidate, HealthOutcome.FAILURE)

    snapshot = (await tracker.get_snapshots([candidate]))[
        provider_health_key(candidate)
    ]
    assert snapshot.sample_count == 5
    assert snapshot.failure_rate == 1.0
    assert snapshot.degraded is False

    await tracker.record(candidate, HealthOutcome.FAILURE)
    snapshot = (await tracker.get_snapshots([candidate]))[
        provider_health_key(candidate)
    ]
    assert snapshot.sample_count == 6
    assert snapshot.degraded is True

    clock.now = 600
    snapshot = (await tracker.get_snapshots([candidate]))[
        provider_health_key(candidate)
    ]
    assert snapshot.sample_count == 0
    assert snapshot.degraded is False


@pytest.mark.asyncio
async def test_expiration_updates_incremental_failure_count() -> None:
    clock = MutableClock()
    tracker = ProviderHealthTracker(
        window_seconds=600,
        min_samples=1,
        failure_rate_threshold=0.5,
        clock=clock,
    )
    candidate = make_candidate(1)

    await tracker.record(candidate, HealthOutcome.FAILURE)
    clock.now = 100
    await tracker.record(candidate, HealthOutcome.FAILURE)
    clock.now = 200
    await tracker.record(candidate, HealthOutcome.SUCCESS)

    clock.now = 601
    snapshot = (await tracker.get_snapshots([candidate]))[
        provider_health_key(candidate)
    ]
    assert snapshot.sample_count == 2
    assert snapshot.failure_count == 1
    assert snapshot.failure_rate == 0.5


@pytest.mark.asyncio
async def test_periodic_cleanup_removes_inactive_mapping_history() -> None:
    clock = MutableClock()
    tracker = ProviderHealthTracker(
        window_seconds=600,
        min_samples=1,
        failure_rate_threshold=0.5,
        cleanup_interval_seconds=60,
        clock=clock,
    )
    inactive = make_candidate(1)
    active = make_candidate(2)
    inactive_key = provider_health_key(inactive)

    await tracker.record(inactive, HealthOutcome.FAILURE)
    assert inactive_key in tracker._windows
    assert inactive_key in tracker._known_states

    # The inactive mapping is no longer queried. Activity on another mapping
    # still triggers global cleanup after the original window has expired.
    clock.now = 601
    await tracker.get_snapshots([active])

    assert inactive_key not in tracker._windows
    assert inactive_key not in tracker._known_states


@pytest.mark.parametrize(
    "strategy",
    [RoundRobinStrategy(), PriorityStrategy(), CostFirstStrategy()],
)
@pytest.mark.asyncio
async def test_health_order_precedes_each_base_strategy(strategy) -> None:
    tracker = ProviderHealthTracker(min_samples=2, failure_rate_threshold=0.5)
    # The least healthy provider is intentionally most attractive by priority/cost.
    healthy = make_candidate(1, priority=100, input_price=100.0)
    degraded_50 = make_candidate(2, priority=10, input_price=10.0)
    degraded_100 = make_candidate(3, priority=0, input_price=1.0)

    await tracker.record(healthy, HealthOutcome.SUCCESS)
    await tracker.record(healthy, HealthOutcome.SUCCESS)
    await tracker.record(degraded_50, HealthOutcome.SUCCESS)
    await tracker.record(degraded_50, HealthOutcome.FAILURE)
    await tracker.record(degraded_100, HealthOutcome.FAILURE)
    await tracker.record(degraded_100, HealthOutcome.FAILURE)

    handler = RetryHandler(strategy, tracker)
    ordered = await handler.get_ordered_candidates(
        [degraded_100, degraded_50, healthy],
        "requested-model",
        input_tokens=1000,
    )

    assert [candidate.provider_mapping_id for candidate in ordered] == [1, 2, 3]


@pytest.mark.asyncio
async def test_retry_records_one_logical_sample_per_provider() -> None:
    tracker = ProviderHealthTracker(min_samples=1, failure_rate_threshold=0.5)
    candidate = make_candidate(1)
    handler = RetryHandler(RoundRobinStrategy(), tracker)
    handler.max_retries = 3
    handler.retry_delay_ms = 0
    calls = 0

    async def forward_fn(_candidate):
        nonlocal calls
        calls += 1
        return ProviderResponse(status_code=500, error="upstream failed")

    result = await handler.execute_with_retry(
        [candidate],
        "requested-model",
        forward_fn,
    )

    snapshot = (await tracker.get_snapshots([candidate]))[
        provider_health_key(candidate)
    ]
    assert result.success is False
    assert calls == 3
    assert snapshot.sample_count == 1
    assert snapshot.failure_count == 1


@pytest.mark.asyncio
async def test_success_after_retry_is_one_success_sample() -> None:
    tracker = ProviderHealthTracker(min_samples=1, failure_rate_threshold=0.5)
    candidate = make_candidate(1)
    handler = RetryHandler(RoundRobinStrategy(), tracker)
    handler.max_retries = 3
    handler.retry_delay_ms = 0
    calls = 0

    async def forward_fn(_candidate):
        nonlocal calls
        calls += 1
        if calls < 3:
            return ProviderResponse(status_code=500, error="temporary failure")
        return ProviderResponse(status_code=200, body={"ok": True})

    result = await handler.execute_with_retry(
        [candidate],
        "requested-model",
        forward_fn,
    )

    snapshot = (await tracker.get_snapshots([candidate]))[
        provider_health_key(candidate)
    ]
    assert result.success is True
    assert snapshot.sample_count == 1
    assert snapshot.failure_count == 0


@pytest.mark.asyncio
async def test_stream_records_result_after_stream_finishes() -> None:
    tracker = ProviderHealthTracker(min_samples=1, failure_rate_threshold=0.5)
    candidate = make_candidate(1)
    handler = RetryHandler(RoundRobinStrategy(), tracker)

    def forward_stream_fn(_candidate):
        async def stream():
            response = ProviderResponse(status_code=200)
            yield b"first", response
            response.status_code = 502
            response.error = "upstream disconnected"
            yield b"error", response

        return stream()

    chunks = [
        item
        async for item in handler.execute_with_retry_stream(
            [candidate],
            "requested-model",
            forward_stream_fn,
        )
    ]

    snapshot = (await tracker.get_snapshots([candidate]))[
        provider_health_key(candidate)
    ]
    assert [chunk for chunk, *_ in chunks] == [b"first", b"error"]
    assert snapshot.sample_count == 1
    assert snapshot.failure_count == 1


def test_response_classification_is_conservative() -> None:
    assert (
        classify_provider_response(ProviderResponse(status_code=200))
        is HealthOutcome.SUCCESS
    )
    assert (
        classify_provider_response(ProviderResponse(status_code=429))
        is HealthOutcome.FAILURE
    )
    assert (
        classify_provider_response(ProviderResponse(status_code=503))
        is HealthOutcome.FAILURE
    )
    assert (
        classify_provider_response(ProviderResponse(status_code=400))
        is HealthOutcome.IGNORED
    )
    assert (
        classify_provider_response(ProviderResponse(status_code=404))
        is HealthOutcome.IGNORED
    )
