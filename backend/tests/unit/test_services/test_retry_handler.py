"""
Retry Handler Unit Tests
"""

import pytest
from unittest.mock import AsyncMock
from app.services.retry_handler import RetryHandler
from app.services.strategy import PriorityStrategy, RoundRobinStrategy
from app.domain.model import LatencyRoutingConfig
from app.services.provider_health import provider_health_key
from app.services.stream_latency import StreamLatencyTracker, stream_chunk_has_text
from app.providers.base import ProviderResponse
from app.rules.models import CandidateProvider


class TestRetryHandler:
    """Retry Handler Tests"""
    
    def setup_method(self):
        """Setup before test"""
        self.strategy = RoundRobinStrategy()
        self.handler = RetryHandler(self.strategy)
        self.handler.max_retries = 3
        self.handler.retry_delay_ms = 10  # Speed up test
        
        self.candidates = [
            CandidateProvider(
                provider_id=1,
                provider_name="Provider1",
                base_url="https://api1.com",
                protocol="openai",
                api_key="key1",
                target_model="model1",
                priority=1,
            ),
            CandidateProvider(
                provider_id=2,
                provider_name="Provider2",
                base_url="https://api2.com",
                protocol="openai",
                api_key="key2",
                target_model="model2",
                priority=2,
            ),
        ]
    
    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        """Test success on first attempt"""
        self.strategy.reset()
        
        async def forward_fn(candidate):
            return ProviderResponse(status_code=200, body={"result": "ok"})
        
        result = await self.handler.execute_with_retry(
            candidates=self.candidates,
            requested_model="test",
            forward_fn=forward_fn,
        )
        
        assert result.success is True
        assert result.retry_count == 0
        assert result.response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_retry_on_500_error(self):
        """Test retry on 500 error"""
        self.strategy.reset()
        call_count = 0
        
        async def forward_fn(candidate):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return ProviderResponse(status_code=500, error="Server error")
            return ProviderResponse(status_code=200, body={"result": "ok"})
        
        result = await self.handler.execute_with_retry(
            candidates=self.candidates,
            requested_model="test",
            forward_fn=forward_fn,
        )
        
        assert result.success is True
        assert result.retry_count == 2  # Succeeded after 2 retries
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_switch_provider_on_400_error(self):
        """Test switch provider on 400 error"""
        self.strategy.reset()
        provider_calls = []
        
        async def forward_fn(candidate):
            provider_calls.append(candidate.provider_id)
            if candidate.provider_id == 1:
                return ProviderResponse(status_code=400, error="Bad request")
            return ProviderResponse(status_code=200, body={"result": "ok"})
        
        result = await self.handler.execute_with_retry(
            candidates=self.candidates,
            requested_model="test",
            forward_fn=forward_fn,
        )
        
        assert result.success is True
        assert result.final_provider.provider_id == 2
        # Switch to second provider immediately after first failure
        assert provider_calls == [1, 2]
    
    @pytest.mark.asyncio
    async def test_max_retries_then_switch(self):
        """Test switch provider after max retries"""
        self.strategy.reset()
        provider_calls = []
        
        async def forward_fn(candidate):
            provider_calls.append(candidate.provider_id)
            if candidate.provider_id == 1:
                return ProviderResponse(status_code=500, error="Server error")
            return ProviderResponse(status_code=200, body={"result": "ok"})
        
        result = await self.handler.execute_with_retry(
            candidates=self.candidates,
            requested_model="test",
            forward_fn=forward_fn,
        )
        
        assert result.success is True
        assert result.final_provider.provider_id == 2
        # Provider1 retries 3 times then switch to Provider2
        assert provider_calls == [1, 1, 1, 2]
    
    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        """Test all providers fail"""
        self.strategy.reset()
        
        async def forward_fn(candidate):
            return ProviderResponse(status_code=500, error="Server error")
        
        result = await self.handler.execute_with_retry(
            candidates=self.candidates,
            requested_model="test",
            forward_fn=forward_fn,
        )
        
        assert result.success is False
        assert result.response.status_code == 500
        # Each provider retries 3 times, total 6 times
        assert result.retry_count == 6
    
    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        """Test empty candidate list"""
        result = await self.handler.execute_with_retry(
            candidates=[],
            requested_model="test",
            forward_fn=AsyncMock(),
        )
        
        assert result.success is False
        assert result.response.status_code == 503

    @pytest.mark.asyncio
    async def test_stream_records_only_first_meaningful_text_chunk(self):
        tracker = StreamLatencyTracker()
        policy = LatencyRoutingConfig(
            enabled=True,
            ttft_threshold_ms=300000,
            min_samples=1,
            breach_count=1,
        )
        handler = RetryHandler(
            self.strategy,
            latency_tracker=tracker,
            latency_config=policy,
        )
        candidate = self.candidates[0]

        def forward_stream_fn(_candidate):
            async def stream():
                response = ProviderResponse(status_code=200)
                yield b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n', response
                yield b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n', response
                yield b'data: {"choices":[{"delta":{"content":"again"}}]}\n\n', response

            return stream()

        chunks = [
            item
            async for item in handler.execute_with_retry_stream(
                [candidate],
                "test",
                forward_stream_fn,
                is_meaningful_chunk=stream_chunk_has_text,
            )
        ]
        snapshot = (await tracker.get_snapshots([candidate], policy))[
            provider_health_key(candidate)
        ]

        assert len(chunks) == 3
        assert snapshot.sample_count == 1

    @pytest.mark.asyncio
    async def test_switch_between_same_provider_multiple_target_models(self):
        """Failover should work for multiple mappings under one provider."""
        self.strategy.reset()
        candidates = [
            CandidateProvider(
                provider_mapping_id=201,
                provider_id=1,
                provider_name="Provider1",
                base_url="https://api1.com",
                protocol="openai",
                api_key="key1",
                target_model="model-a",
                priority=1,
            ),
            CandidateProvider(
                provider_mapping_id=202,
                provider_id=1,
                provider_name="Provider1",
                base_url="https://api1.com",
                protocol="openai",
                api_key="key1",
                target_model="model-b",
                priority=2,
            ),
        ]
        called_models: list[str] = []

        async def forward_fn(candidate):
            called_models.append(candidate.target_model)
            if candidate.target_model == "model-a":
                return ProviderResponse(status_code=400, error="Bad request")
            return ProviderResponse(status_code=200, body={"result": "ok"})

        result = await self.handler.execute_with_retry(
            candidates=candidates,
            requested_model="test",
            forward_fn=forward_fn,
        )

        assert result.success is True
        assert result.final_provider.provider_mapping_id == 202
        assert called_models == ["model-a", "model-b"]


def _priority_fallback_candidates() -> list[CandidateProvider]:
    return [
        CandidateProvider(
            provider_mapping_id=301,
            provider_id=1,
            provider_name="Primary",
            base_url="https://primary.example.com",
            protocol="openai",
            api_key="key1",
            target_model="primary-model",
            priority=0,
            weight=1,
        ),
        CandidateProvider(
            provider_mapping_id=302,
            provider_id=2,
            provider_name="FallbackA",
            base_url="https://fallback-a.example.com",
            protocol="openai",
            api_key="key2",
            target_model="fallback-a-model",
            priority=1,
            weight=1,
        ),
        CandidateProvider(
            provider_mapping_id=303,
            provider_id=3,
            provider_name="FallbackB",
            base_url="https://fallback-b.example.com",
            protocol="openai",
            api_key="key3",
            target_model="fallback-b-model",
            priority=1,
            weight=3,
        ),
    ]


@pytest.mark.asyncio
async def test_unattempted_priority_fallback_does_not_advance_weight_counter():
    handler = RetryHandler(PriorityStrategy())
    candidates = _priority_fallback_candidates()
    fallback_provider_ids: list[int] = []

    for request_number in range(1, 9):
        async def forward_fn(candidate, current_request=request_number):
            if candidate.priority == 0:
                if current_request % 4 == 0:
                    return ProviderResponse(status_code=400, error="primary failed")
                return ProviderResponse(status_code=200, body={"ok": True})

            fallback_provider_ids.append(candidate.provider_id)
            return ProviderResponse(status_code=200, body={"ok": True})

        result = await handler.execute_with_retry(
            candidates,
            "test-model",
            forward_fn,
        )
        assert result.success is True

    # The 1:3 fallback group was reached only twice, so its first two actual
    # selections must be A then B. Successful primary requests do not count.
    assert fallback_provider_ids == [2, 3]


@pytest.mark.asyncio
async def test_unattempted_stream_fallback_does_not_advance_weight_counter():
    handler = RetryHandler(PriorityStrategy())
    candidates = _priority_fallback_candidates()
    fallback_provider_ids: list[int] = []

    for request_number in range(1, 9):
        def forward_stream_fn(candidate, current_request=request_number):
            async def stream():
                if candidate.priority == 0:
                    if current_request % 4 == 0:
                        yield b"", ProviderResponse(
                            status_code=400,
                            error="primary failed",
                        )
                        return
                    yield b"ok", ProviderResponse(status_code=200)
                    return

                fallback_provider_ids.append(candidate.provider_id)
                yield b"ok", ProviderResponse(status_code=200)

            return stream()

        chunks = [
            item
            async for item in handler.execute_with_retry_stream(
                candidates,
                "test-model",
                forward_stream_fn,
            )
        ]
        assert chunks[-1][1].is_success is True

    assert fallback_provider_ids == [2, 3]


def _paused_candidates(paused_until):
    """Three candidates A, C active and B paused (paused_until)."""
    return [
        CandidateProvider(
            provider_mapping_id=401,
            provider_id=1,
            provider_name="A",
            base_url="https://a.example.com",
            protocol="openai",
            api_key="k1",
            target_model="model-a",
            priority=0,
        ),
        CandidateProvider(
            provider_mapping_id=402,
            provider_id=2,
            provider_name="B-paused",
            base_url="https://b.example.com",
            protocol="openai",
            api_key="k2",
            target_model="model-b",
            priority=1,
            paused_until=paused_until,
        ),
        CandidateProvider(
            provider_mapping_id=403,
            provider_id=3,
            provider_name="C",
            base_url="https://c.example.com",
            protocol="openai",
            api_key="k3",
            target_model="model-c",
            priority=2,
        ),
    ]


@pytest.mark.asyncio
async def test_paused_candidate_scheduled_last():
    """A candidate paused into the future is ordered after all active ones."""
    from datetime import timedelta
    from app.common.time import utc_now

    handler = RetryHandler(PriorityStrategy())
    candidates = _paused_candidates(utc_now() + timedelta(hours=1))

    ordered = await handler.get_ordered_candidates(candidates, "test-model")
    ids = [c.provider_mapping_id for c in ordered]

    # B (402) is paused, so it must come after both active A (401) and C (403).
    assert ids[-1] == 402
    assert set(ids[:-1]) == {401, 403}


@pytest.mark.asyncio
async def test_expired_pause_is_treated_as_active():
    """A paused_until in the past no longer deprioritizes the candidate."""
    from datetime import timedelta
    from app.common.time import utc_now

    handler = RetryHandler(PriorityStrategy())
    candidates = _paused_candidates(utc_now() - timedelta(hours=1))

    ordered = await handler.get_ordered_candidates(candidates, "test-model")
    ids = [c.provider_mapping_id for c in ordered]

    # Expired pause => normal priority order 401, 402, 403.
    assert ids == [401, 402, 403]


@pytest.mark.asyncio
async def test_paused_candidate_still_tried_when_active_fail():
    """When every active provider fails, the paused one is used as last resort."""
    from datetime import timedelta
    from app.common.time import utc_now

    handler = RetryHandler(PriorityStrategy())
    handler.max_retries = 1
    candidates = _paused_candidates(utc_now() + timedelta(hours=1))
    tried: list[int] = []

    async def forward_fn(candidate):
        tried.append(candidate.provider_mapping_id)
        # Active providers (A, C) fail with client error; paused B succeeds.
        if candidate.provider_mapping_id == 402:
            return ProviderResponse(status_code=200, body={"ok": True})
        return ProviderResponse(status_code=400, body={"err": "bad"})

    result = await handler.execute_with_retry(
        candidates=candidates,
        requested_model="test-model",
        forward_fn=forward_fn,
    )

    assert result.success is True
    assert result.final_provider.provider_mapping_id == 402
    # Paused B is only reached after both active providers were tried.
    assert tried[-1] == 402
    assert set(tried[:-1]) == {401, 403}
