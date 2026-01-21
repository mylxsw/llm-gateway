"""
Rule Model Definition Module

Defines data structures used by the rule engine.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Rule:
    """
    Rule Definition
    
    A single rule, containing the matching field, operator, and expected value.
    
    Attributes:
        field: Matching field path (e.g., "model", "headers.x-priority", "body.temperature")
        operator: Operator (e.g., "eq", "gt", "contains")
        value: Expected value
    """
    
    field: str
    operator: str
    value: Any
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Rule":
        """Create rule from dictionary"""
        return cls(
            field=data.get("field", ""),
            operator=data.get("operator", "eq"),
            value=data.get("value"),
        )


@dataclass
class RuleSet:
    """
    Rule Set
    
    Contains multiple rules and logic operator (AND/OR).
    
    Attributes:
        rules: List of rules
        logic: Logic operator, "AND" or "OR", defaults to "AND"
    """
    
    rules: list[Rule] = field(default_factory=list)
    logic: str = "AND"  # "AND" or "OR"
    
    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> Optional["RuleSet"]:
        """
        Create rule set from dictionary
        
        Args:
            data: Rule set dictionary, formatted as:
                {
                    "rules": [
                        {"field": "model", "operator": "eq", "value": "gpt-4"}
                    ],
                    "logic": "AND"
                }
        
        Returns:
            Optional[RuleSet]: Rule set, or None if data is empty
        """
        if not data:
            return None
        
        rules_data = data.get("rules", [])
        rules = [Rule.from_dict(r) for r in rules_data]
        logic = data.get("logic", "AND").upper()
        
        return cls(rules=rules, logic=logic)
    
    def is_empty(self) -> bool:
        """Check if rule set is empty"""
        return len(self.rules) == 0


@dataclass
class CandidateProvider:
    """
    Candidate Provider

    Candidate provider information output after rule engine matching.

    Attributes:
        provider_id: Provider ID
        provider_name: Provider Name
        base_url: Provider Base URL
        protocol: Provider Protocol (openai/anthropic)
        api_key: Provider API Key
        target_model: Target Model Name (Actual model corresponding to this provider)
        priority: Priority (Lower value means higher priority)
        weight: Weight (Used for weighted selection)
        billing_mode: Billing mode (token_flat/token_tiered/per_request)
        input_price: Provider input token price override (USD per 1M tokens)
        output_price: Provider output token price override (USD per 1M tokens)
        per_request_price: Per-request price (USD)
        tiered_pricing: Tiered pricing configuration
        model_input_price: Model fallback input price (USD per 1M tokens)
        model_output_price: Model fallback output price (USD per 1M tokens)
    """

    provider_id: int
    provider_name: str
    base_url: str
    protocol: str
    api_key: Optional[str]
    target_model: str
    extra_headers: Optional[dict[str, str]] = None
    proxy_enabled: bool = False
    proxy_url: Optional[str] = None
    priority: int = 0
    weight: int = 1
    billing_mode: Optional[str] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    per_request_price: Optional[float] = None
    tiered_pricing: Optional[list[Any]] = None
    model_input_price: Optional[float] = None
    model_output_price: Optional[float] = None
