"""
规则引擎核心模块

提供规则引擎的主要功能，包括规则匹配和候选供应商输出。
"""

from typing import Optional

from app.rules.context import RuleContext
from app.rules.models import RuleSet, CandidateProvider
from app.rules.evaluator import RuleEvaluator
from app.domain.model import ModelMapping, ModelMappingProviderResponse
from app.domain.provider import Provider


class RuleEngine:
    """
    规则引擎
    
    负责根据上下文评估所有规则，输出匹配的候选供应商列表。
    
    工作流程：
    1. 检查模型级规则（model_mapping.matching_rules）
    2. 对每个供应商检查供应商级规则（provider_mapping.provider_rules）
    3. 返回所有通过的供应商及其 target_model
    """
    
    def __init__(self):
        """初始化规则引擎"""
        self.evaluator = RuleEvaluator()
    
    async def evaluate(
        self,
        context: RuleContext,
        model_mapping: ModelMapping,
        provider_mappings: list[ModelMappingProviderResponse],
        providers: dict[int, Provider],
    ) -> list[CandidateProvider]:
        """
        评估所有规则，返回候选供应商列表
        
        Args:
            context: 规则上下文
            model_mapping: 模型映射配置
            provider_mappings: 模型-供应商映射列表
            providers: 供应商字典（provider_id -> Provider）
        
        Returns:
            list[CandidateProvider]: 候选供应商列表（按优先级排序）
        """
        candidates: list[CandidateProvider] = []
        
        # 1. 检查模型级规则
        model_rules = RuleSet.from_dict(model_mapping.matching_rules)
        if not self.evaluator.evaluate_ruleset(model_rules, context):
            # 模型级规则不通过，直接返回空列表
            return candidates
        
        # 2. 对每个供应商检查供应商级规则
        for pm in provider_mappings:
            # 跳过未激活的映射
            if not pm.is_active:
                continue
            
            # 获取供应商信息
            provider = providers.get(pm.provider_id)
            if not provider or not provider.is_active:
                continue
            
            # 检查供应商级规则
            provider_rules = RuleSet.from_dict(pm.provider_rules)
            if self.evaluator.evaluate_ruleset(provider_rules, context):
                # 规则通过，添加到候选列表
                candidates.append(
                    CandidateProvider(
                        provider_id=provider.id,
                        provider_name=provider.name,
                        base_url=provider.base_url,
                        protocol=provider.protocol,
                        api_key=provider.api_key,
                        extra_headers=provider.extra_headers,
                        target_model=pm.target_model_name,
                        priority=pm.priority,
                        weight=pm.weight,
                    )
                )
        
        # 3. 按优先级排序（数值越小优先级越高）
        candidates.sort(key=lambda c: (c.priority, c.provider_id))
        
        return candidates
    
    def evaluate_sync(
        self,
        context: RuleContext,
        model_mapping: ModelMapping,
        provider_mappings: list[ModelMappingProviderResponse],
        providers: dict[int, Provider],
    ) -> list[CandidateProvider]:
        """
        同步版本的规则评估（用于测试或同步场景）
        
        参数和返回值与 evaluate 相同。
        """
        candidates: list[CandidateProvider] = []
        
        # 1. 检查模型级规则
        model_rules = RuleSet.from_dict(model_mapping.matching_rules)
        if not self.evaluator.evaluate_ruleset(model_rules, context):
            return candidates
        
        # 2. 对每个供应商检查供应商级规则
        for pm in provider_mappings:
            if not pm.is_active:
                continue
            
            provider = providers.get(pm.provider_id)
            if not provider or not provider.is_active:
                continue
            
            provider_rules = RuleSet.from_dict(pm.provider_rules)
            if self.evaluator.evaluate_ruleset(provider_rules, context):
                candidates.append(
                    CandidateProvider(
                        provider_id=provider.id,
                        provider_name=provider.name,
                        base_url=provider.base_url,
                        protocol=provider.protocol,
                        api_key=provider.api_key,
                        extra_headers=provider.extra_headers,
                        target_model=pm.target_model_name,
                        priority=pm.priority,
                        weight=pm.weight,
                    )
                )
        
        # 3. 按优先级排序
        candidates.sort(key=lambda c: (c.priority, c.provider_id))
        
        return candidates
