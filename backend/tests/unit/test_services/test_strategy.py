"""
Round Robin Strategy Unit Tests
"""

import pytest
import asyncio
from app.services.strategy import RoundRobinStrategy, CostFirstStrategy
from app.rules.models import CandidateProvider


class TestRoundRobinStrategy:
    """Round Robin Strategy Tests"""
    
    def setup_method(self):
        """Setup before test"""
        self.strategy = RoundRobinStrategy()
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
            CandidateProvider(
                provider_id=3,
                provider_name="Provider3",
                base_url="https://api3.com",
                protocol="openai",
                api_key="key3",
                target_model="model3",
                priority=3,
            ),
        ]
    
    @pytest.mark.asyncio
    async def test_select_round_robin(self):
        """Test round robin selection"""
        self.strategy.reset()
        
        # 1st selection
        selected = await self.strategy.select(self.candidates, "test-model")
        assert selected.provider_id == 1
        
        # 2nd selection
        selected = await self.strategy.select(self.candidates, "test-model")
        assert selected.provider_id == 2
        
        # 3rd selection
        selected = await self.strategy.select(self.candidates, "test-model")
        assert selected.provider_id == 3
        
        # 4th selection (loop back to first)
        selected = await self.strategy.select(self.candidates, "test-model")
        assert selected.provider_id == 1
    
    @pytest.mark.asyncio
    async def test_select_empty_candidates(self):
        """Test empty candidate list"""
        selected = await self.strategy.select([], "test-model")
        assert selected is None
    
    @pytest.mark.asyncio
    async def test_select_model_isolation(self):
        """Test model counter isolation"""
        self.strategy.reset()
        
        # model-a selection
        selected_a = await self.strategy.select(self.candidates, "model-a")
        assert selected_a.provider_id == 1
        
        # model-b first selection (start from beginning)
        selected_b = await self.strategy.select(self.candidates, "model-b")
        assert selected_b.provider_id == 1
        
        # model-a second selection
        selected_a = await self.strategy.select(self.candidates, "model-a")
        assert selected_a.provider_id == 2
    
    @pytest.mark.asyncio
    async def test_get_next(self):
        """Test get next provider"""
        current = self.candidates[0]
        next_provider = await self.strategy.get_next(
            self.candidates, "test-model", current
        )
        assert next_provider.provider_id == 2
        
        current = self.candidates[2]
        next_provider = await self.strategy.get_next(
            self.candidates, "test-model", current
        )
        assert next_provider.provider_id == 1
    
    @pytest.mark.asyncio
    async def test_get_next_single_candidate(self):
        """Test get next with single candidate"""
        single = [self.candidates[0]]
        next_provider = await self.strategy.get_next(
            single, "test-model", single[0]
        )
        assert next_provider is None
    
    @pytest.mark.asyncio
    async def test_concurrent_selection(self):
        """Test concurrent selection safety"""
        self.strategy.reset()
        
        # Execute 100 selections concurrently
        tasks = [
            self.strategy.select(self.candidates, "concurrent-test")
            for _ in range(100)
        ]
        results = await asyncio.gather(*tasks)
        
        # Verify result distribution (should be roughly even)
        counts = {1: 0, 2: 0, 3: 0}
        for result in results:
            counts[result.provider_id] += 1
        
        # Each provider should be selected roughly 33 times
        for provider_id, count in counts.items():
            assert 20 <= count <= 50, f"Provider {provider_id} selected {count} times"


class TestCostFirstStrategy:
    """Cost First Strategy Tests"""

    def setup_method(self):
        """Setup before test"""
        self.strategy = CostFirstStrategy()
        # Create candidates with different pricing
        self.candidates = [
            CandidateProvider(
                provider_id=1,
                provider_name="ExpensiveProvider",
                base_url="https://api1.com",
                protocol="openai",
                api_key="key1",
                target_model="model1",
                priority=1,
                billing_mode="token_flat",
                input_price=10.0,  # $10 per 1M tokens
                output_price=30.0,
                model_input_price=5.0,
                model_output_price=15.0,
            ),
            CandidateProvider(
                provider_id=2,
                provider_name="CheapProvider",
                base_url="https://api2.com",
                protocol="openai",
                api_key="key2",
                target_model="model2",
                priority=2,
                billing_mode="token_flat",
                input_price=1.0,  # $1 per 1M tokens
                output_price=3.0,
                model_input_price=5.0,
                model_output_price=15.0,
            ),
            CandidateProvider(
                provider_id=3,
                provider_name="MediumProvider",
                base_url="https://api3.com",
                protocol="openai",
                api_key="key3",
                target_model="model3",
                priority=3,
                billing_mode="token_flat",
                input_price=5.0,  # $5 per 1M tokens
                output_price=15.0,
                model_input_price=5.0,
                model_output_price=15.0,
            ),
        ]

    @pytest.mark.asyncio
    async def test_select_lowest_cost(self):
        """Test that the lowest cost provider is selected"""
        # With 1000 input tokens
        selected = await self.strategy.select(self.candidates, "test-model", input_tokens=1000)
        # Should select provider 2 (CheapProvider) with $1/1M = $0.001 for 1000 tokens
        assert selected.provider_id == 2
        assert selected.provider_name == "CheapProvider"

    @pytest.mark.asyncio
    async def test_select_with_per_request_billing(self):
        """Test cost selection with per-request billing"""
        candidates_with_per_request = [
            CandidateProvider(
                provider_id=1,
                provider_name="TokenBased",
                base_url="https://api1.com",
                protocol="openai",
                api_key="key1",
                target_model="model1",
                priority=1,
                billing_mode="token_flat",
                input_price=5.0,
                output_price=15.0,
                model_input_price=5.0,
                model_output_price=15.0,
            ),
            CandidateProvider(
                provider_id=2,
                provider_name="PerRequest",
                base_url="https://api2.com",
                protocol="openai",
                api_key="key2",
                target_model="model2",
                priority=2,
                billing_mode="per_request",
                per_request_price=0.001,  # $0.001 per request
                model_input_price=5.0,
                model_output_price=15.0,
            ),
        ]

        # With 1000 input tokens, token-based: 1000/1M * $5 = $0.005
        # Per-request: $0.001
        # Per-request should be selected
        selected = await self.strategy.select(candidates_with_per_request, "test-model", input_tokens=1000)
        assert selected.provider_id == 2
        assert selected.provider_name == "PerRequest"

    @pytest.mark.asyncio
    async def test_get_next_by_cost(self):
        """Test that get_next returns the next cheapest provider"""
        current = self.candidates[1]  # CheapProvider (ID: 2)
        next_provider = await self.strategy.get_next(
            self.candidates, "test-model", current, input_tokens=1000
        )
        # Next cheapest should be MediumProvider (ID: 3)
        assert next_provider.provider_id == 3
        assert next_provider.provider_name == "MediumProvider"

        # After medium, should be expensive
        current = self.candidates[2]  # MediumProvider (ID: 3)
        next_provider = await self.strategy.get_next(
            self.candidates, "test-model", current, input_tokens=1000
        )
        assert next_provider.provider_id == 1
        assert next_provider.provider_name == "ExpensiveProvider"

    @pytest.mark.asyncio
    async def test_select_no_input_tokens(self):
        """Test selection without input tokens falls back to first candidate"""
        selected = await self.strategy.select(self.candidates, "test-model", input_tokens=None)
        # Should fall back to first candidate (by priority)
        assert selected.provider_id == 1

    @pytest.mark.asyncio
    async def test_select_empty_candidates(self):
        """Test empty candidate list"""
        selected = await self.strategy.select([], "test-model", input_tokens=1000)
        assert selected is None

    @pytest.mark.asyncio
    async def test_get_next_no_more_providers(self):
        """Test get_next when already at the last (most expensive) provider"""
        current = self.candidates[0]  # ExpensiveProvider (ID: 1)
        # After the most expensive, there should be no next
        next_provider = await self.strategy.get_next(
            self.candidates, "test-model", current, input_tokens=1000
        )
        # get_next should return None when at the end
        assert next_provider is None

    @pytest.mark.asyncio
    async def test_cost_calculation_with_different_token_counts(self):
        """Test that cost is recalculated based on actual input tokens"""
        # With 100 tokens, all should be very cheap
        selected = await self.strategy.select(self.candidates, "test-model", input_tokens=100)
        assert selected.provider_id == 2  # Still cheapest

        # With 1M tokens, cost differences should be significant
        selected = await self.strategy.select(self.candidates, "test-model", input_tokens=1000000)
        assert selected.provider_id == 2  # Still cheapest
        # Provider 2: $1 * 1M/1M = $1.00
        # Provider 3: $5 * 1M/1M = $5.00
        # Provider 1: $10 * 1M/1M = $10.00