"""
Rule Engine Core Module

Provides the main functionality of the rule engine, including rule matching and candidate provider output.
"""

from typing import Optional

from app.rules.context import RuleContext
from app.rules.models import RuleSet, CandidateProvider
from app.rules.evaluator import RuleEvaluator
from app.domain.model import ModelMapping, ModelMappingProviderResponse
from app.domain.provider import Provider


class RuleEngine:
    """
    Rule Engine
    
    Responsible for evaluating all rules based on context and outputting a list of matching candidate providers.
    
    Workflow:
    1. Check model-level rules (model_mapping.matching_rules)
    2. Check provider-level rules for each provider (provider_mapping.provider_rules)
    3. Return all matching providers and their target_model
    """
    
    def __init__(self):
        """Initialize Rule Engine"""
        self.evaluator = RuleEvaluator()
    
    async def evaluate(
        self,
        context: RuleContext,
        model_mapping: ModelMapping,
        provider_mappings: list[ModelMappingProviderResponse],
        providers: dict[int, Provider],
    ) -> list[CandidateProvider]:
        """
        Evaluate all rules, return list of candidate providers
        
        Args:
            context: Rule context
            model_mapping: Model mapping configuration
            provider_mappings: List of model-provider mappings
            providers: Provider dictionary (provider_id -> Provider)
        
        Returns:
            list[CandidateProvider]: List of candidate providers (sorted by priority)
        """
        candidates: list[CandidateProvider] = []
        
        # 1. Check model-level rules
        model_rules = RuleSet.from_dict(model_mapping.matching_rules)
        if not self.evaluator.evaluate_ruleset(model_rules, context):
            # Model-level rules failed, return empty list immediately
            return candidates
        
        # 2. Check provider-level rules for each provider
        for pm in provider_mappings:
            # Skip inactive mappings
            if not pm.is_active:
                continue
            
            # Get provider info
            provider = providers.get(pm.provider_id)
            if not provider or not provider.is_active:
                continue
            
            # Check provider-level rules
            provider_rules = RuleSet.from_dict(pm.provider_rules)
            if self.evaluator.evaluate_ruleset(provider_rules, context):
                # Rules passed, add to candidate list
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
        
        # 3. Sort by priority (lower value means higher priority)
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
        Synchronous version of rule evaluation (for testing or synchronous scenarios)
        
        Arguments and return values are same as evaluate.
        """
        candidates: list[CandidateProvider] = []
        
        # 1. Check model-level rules
        model_rules = RuleSet.from_dict(model_mapping.matching_rules)
        if not self.evaluator.evaluate_ruleset(model_rules, context):
            return candidates
        
        # 2. Check provider-level rules for each provider
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
        
        # 3. Sort by priority
        candidates.sort(key=lambda c: (c.priority, c.provider_id))
        
        return candidates