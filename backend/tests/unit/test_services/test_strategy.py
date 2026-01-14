"""
Round Robin Strategy Unit Tests
"""

import pytest
import asyncio
from app.services.strategy import RoundRobinStrategy
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