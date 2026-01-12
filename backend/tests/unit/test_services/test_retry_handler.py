"""
Retry Handler Unit Tests
"""

import pytest
from unittest.mock import AsyncMock
from app.services.retry_handler import RetryHandler
from app.services.strategy import RoundRobinStrategy
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