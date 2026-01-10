"""
策略服务模块

提供供应商选择策略的实现。
"""

from abc import ABC, abstractmethod
from typing import Optional
import asyncio

from app.rules.models import CandidateProvider


class SelectionStrategy(ABC):
    """
    供应商选择策略抽象基类
    
    定义从候选供应商列表中选择供应商的接口。
    """
    
    @abstractmethod
    async def select(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
    ) -> Optional[CandidateProvider]:
        """
        从候选列表中选择一个供应商
        
        Args:
            candidates: 候选供应商列表
            requested_model: 请求的模型名（用于状态隔离）
        
        Returns:
            Optional[CandidateProvider]: 选中的供应商，无可用供应商时返回 None
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
        获取下一个供应商（用于故障切换）
        
        Args:
            candidates: 候选供应商列表
            requested_model: 请求的模型名
            current: 当前供应商
        
        Returns:
            Optional[CandidateProvider]: 下一个供应商，无可用供应商时返回 None
        """
        pass


class RoundRobinStrategy(SelectionStrategy):
    """
    轮询（轮转）策略
    
    在候选供应商之间进行轮询选择，确保请求均匀分布。
    使用原子计数器实现并发安全。
    """
    
    def __init__(self):
        """初始化策略"""
        # 每个模型维护独立的计数器
        self._counters: dict[str, int] = {}
        # 用于保护计数器的锁
        self._lock: Optional[asyncio.Lock] = None

    @property
    def lock(self) -> asyncio.Lock:
        """获取锁（懒加载）"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock
    
    async def select(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
    ) -> Optional[CandidateProvider]:
        """
        轮询选择供应商
        
        Args:
            candidates: 候选供应商列表（已按优先级排序）
            requested_model: 请求的模型名
        
        Returns:
            Optional[CandidateProvider]: 选中的供应商
        """
        if not candidates:
            return None
        
        async with self.lock:
            # 获取当前计数
            counter = self._counters.get(requested_model, 0)
            # 选择供应商
            index = counter % len(candidates)
            # 更新计数
            self._counters[requested_model] = counter + 1
        
        return candidates[index]
    
    async def get_next(
        self,
        candidates: list[CandidateProvider],
        requested_model: str,
        current: CandidateProvider,
    ) -> Optional[CandidateProvider]:
        """
        获取下一个供应商（故障切换时使用）
        
        Args:
            candidates: 候选供应商列表
            requested_model: 请求的模型名
            current: 当前供应商
        
        Returns:
            Optional[CandidateProvider]: 下一个供应商
        """
        if not candidates or len(candidates) <= 1:
            return None
        
        # 找到当前供应商的索引
        current_index = -1
        for i, c in enumerate(candidates):
            if c.provider_id == current.provider_id:
                current_index = i
                break
        
        if current_index == -1:
            return None
        
        # 返回下一个供应商
        next_index = (current_index + 1) % len(candidates)
        if next_index == current_index:
            return None
        
        return candidates[next_index]
    
    def reset(self, requested_model: Optional[str] = None) -> None:
        """
        重置计数器（用于测试）
        
        Args:
            requested_model: 指定模型名，为 None 时重置所有
        """
        if requested_model:
            self._counters.pop(requested_model, None)
        else:
            self._counters.clear()
