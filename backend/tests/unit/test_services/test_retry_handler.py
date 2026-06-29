"""
Retry Handler Unit Tests
"""

import pytest
from unittest.mock import AsyncMock
from app.services.retry_handler import RetryHandler
from app.services.strategy import PriorityStrategy, RoundRobinStrategy
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
