"""
Rule Engine Unit Tests
"""

import pytest
from app.rules import RuleContext, TokenUsage, Rule, RuleSet, RuleEvaluator, RuleEngine
from app.domain.model import ModelMapping, ModelMappingProviderResponse
from app.domain.provider import Provider
from app.common.time import utc_now


class TestRuleContext:
    """Rule Context Tests"""
    
    def test_get_value_model(self):
        """Test getting model field"""
        context = RuleContext(current_model="gpt-4")
        assert context.get_value("model") == "gpt-4"
    
    def test_get_value_headers(self):
        """Test getting headers field"""
        context = RuleContext(
            current_model="gpt-4",
            headers={"x-priority": "high", "content-type": "application/json"},
        )
        assert context.get_value("headers.x-priority") == "high"
        assert context.get_value("headers.content-type") == "application/json"
    
    def test_get_value_body(self):
        """Test getting body field"""
        context = RuleContext(
            current_model="gpt-4",
            request_body={
                "model": "gpt-4",
                "temperature": 0.7,
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
            },
        )
        assert context.get_value("body.model") == "gpt-4"
        assert context.get_value("body.temperature") == 0.7
    
    def test_get_value_body_nested(self):
        """Test getting nested body field"""
        context = RuleContext(
            current_model="gpt-4",
            request_body={
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                ],
            },
        )
        assert context.get_value("body.messages[0].role") == "system"
        assert context.get_value("body.messages[1].content") == "Hello"
    
    def test_get_value_token_usage(self):
        """Test getting token_usage field"""
        context = RuleContext(
            current_model="gpt-4",
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        assert context.get_value("token_usage.input_tokens") == 100
        assert context.get_value("token_usage.output_tokens") == 50
        assert context.get_value("token_usage.total_tokens") == 150
    
    def test_get_value_not_found(self):
        """Test getting non-existent field"""
        context = RuleContext(current_model="gpt-4")
        assert context.get_value("headers.not-exist") is None
        assert context.get_value("body.not-exist") is None
        assert context.get_value("unknown.field") is None


class TestRuleEvaluator:
    """Rule Evaluator Tests"""
    
    def setup_method(self):
        """Setup before test"""
        self.evaluator = RuleEvaluator()
        self.context = RuleContext(
            current_model="gpt-4",
            headers={"x-priority": "high"},
            request_body={"temperature": 0.7, "max_tokens": 1000},
            token_usage=TokenUsage(input_tokens=500),
        )
    
    def test_eq_operator(self):
        """Test equal operator"""
        rule = Rule(field="model", operator="eq", value="gpt-4")
        assert self.evaluator.evaluate_rule(rule, self.context) is True
        
        rule = Rule(field="model", operator="eq", value="gpt-3.5")
        assert self.evaluator.evaluate_rule(rule, self.context) is False
    
    def test_ne_operator(self):
        """Test not equal operator"""
        rule = Rule(field="model", operator="ne", value="gpt-3.5")
        assert self.evaluator.evaluate_rule(rule, self.context) is True
    
    def test_gt_operator(self):
        """Test greater than operator"""
        rule = Rule(field="body.temperature", operator="gt", value=0.5)
        assert self.evaluator.evaluate_rule(rule, self.context) is True
        
        rule = Rule(field="body.temperature", operator="gt", value=0.7)
        assert self.evaluator.evaluate_rule(rule, self.context) is False
    
    def test_gte_operator(self):
        """Test greater than or equal operator"""
        rule = Rule(field="body.temperature", operator="gte", value=0.7)
        assert self.evaluator.evaluate_rule(rule, self.context) is True
    
    def test_lt_operator(self):
        """Test less than operator"""
        rule = Rule(field="token_usage.input_tokens", operator="lt", value=1000)
        assert self.evaluator.evaluate_rule(rule, self.context) is True
    
    def test_lte_operator(self):
        """Test less than or equal operator"""
        rule = Rule(field="token_usage.input_tokens", operator="lte", value=500)
        assert self.evaluator.evaluate_rule(rule, self.context) is True
    
    def test_contains_operator(self):
        """Test contains operator"""
        rule = Rule(field="headers.x-priority", operator="contains", value="hi")
        assert self.evaluator.evaluate_rule(rule, self.context) is True
    
    def test_in_operator(self):
        """Test in operator"""
        rule = Rule(field="model", operator="in", value=["gpt-4", "gpt-3.5"])
        assert self.evaluator.evaluate_rule(rule, self.context) is True
        
        rule = Rule(field="model", operator="in", value=["claude-3"])
        assert self.evaluator.evaluate_rule(rule, self.context) is False
    
    def test_exists_operator(self):
        """Test exists operator"""
        rule = Rule(field="headers.x-priority", operator="exists", value=True)
        assert self.evaluator.evaluate_rule(rule, self.context) is True
        
        rule = Rule(field="headers.not-exist", operator="exists", value=False)
        assert self.evaluator.evaluate_rule(rule, self.context) is True
    
    def test_regex_operator(self):
        """Test regex operator"""
        rule = Rule(field="model", operator="regex", value="gpt-\d")
        assert self.evaluator.evaluate_rule(rule, self.context) is True
    
    def test_evaluate_ruleset_and(self):
        """Test rule set AND logic"""
        ruleset = RuleSet(
            rules=[
                Rule(field="model", operator="eq", value="gpt-4"),
                Rule(field="headers.x-priority", operator="eq", value="high"),
            ],
            logic="AND",
        )
        assert self.evaluator.evaluate_ruleset(ruleset, self.context) is True
        
        ruleset = RuleSet(
            rules=[
                Rule(field="model", operator="eq", value="gpt-4"),
                Rule(field="headers.x-priority", operator="eq", value="low"),
            ],
            logic="AND",
        )
        assert self.evaluator.evaluate_ruleset(ruleset, self.context) is False
    
    def test_evaluate_ruleset_or(self):
        """Test rule set OR logic"""
        ruleset = RuleSet(
            rules=[
                Rule(field="model", operator="eq", value="gpt-3.5"),
                Rule(field="headers.x-priority", operator="eq", value="high"),
            ],
            logic="OR",
        )
        assert self.evaluator.evaluate_ruleset(ruleset, self.context) is True
    
    def test_evaluate_empty_ruleset(self):
        """Test empty rule set (default pass)"""
        assert self.evaluator.evaluate_ruleset(None, self.context) is True
        assert self.evaluator.evaluate_ruleset(RuleSet(rules=[]), self.context) is True


class TestRuleEngine:
    """Rule Engine Tests"""
    
    def setup_method(self):
        """Setup before test"""
        self.engine = RuleEngine()
        now = utc_now()
        
        # Mock Providers
        self.providers = {
            1: Provider(
                id=1,
                name="OpenAI",
                base_url="https://api.openai.com",
                protocol="openai",
                api_type="chat",
                api_key="sk-xxx",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            2: Provider(
                id=2,
                name="Azure",
                base_url="https://azure.openai.com",
                protocol="openai",
                api_type="chat",
                api_key="azure-xxx",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
        }
        
        # Mock Model Mapping
        self.model_mapping = ModelMapping(
            requested_model="gpt-4",
            strategy="round_robin",
            capabilities=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        
        # Mock Model-Provider Mappings
        self.provider_mappings = [
            ModelMappingProviderResponse(
                id=1,
                requested_model="gpt-4",
                provider_id=1,
                provider_name="OpenAI",
                target_model_name="gpt-4-0613",
                provider_rules=None,
                priority=1,
                weight=1,
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            ModelMappingProviderResponse(
                id=2,
                requested_model="gpt-4",
                provider_id=2,
                provider_name="Azure",
                target_model_name="gpt-4-azure",
                provider_rules=None,
                priority=2,
                weight=1,
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
        ]
    
    def test_evaluate_no_rules(self):
        """Test no rules matches all providers"""
        context = RuleContext(current_model="gpt-4")
        
        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )
        
        assert len(candidates) == 2
        assert candidates[0].provider_name == "OpenAI"
        assert candidates[0].target_model == "gpt-4-0613"
        assert candidates[1].provider_name == "Azure"
        assert candidates[1].target_model == "gpt-4-azure"
    
    def test_evaluate_with_provider_rules(self):
        """Test provider-level rule filtering"""
        context = RuleContext(
            current_model="gpt-4",
            token_usage=TokenUsage(input_tokens=5000),
        )
        
        # Set provider-level rule: OpenAI only accepts input_tokens < 4000
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "token_usage.input_tokens", "operator": "lt", "value": 4000}
            ]
        }
        
        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )
        
        # Only Azure passes
        assert len(candidates) == 1
        assert candidates[0].provider_name == "Azure"
    
    def test_evaluate_inactive_provider(self):
        """Test inactive provider filtering"""
        context = RuleContext(current_model="gpt-4")
        
        # Disable OpenAI
        self.providers[1].is_active = False
        
        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )
        
        assert len(candidates) == 1
        assert candidates[0].provider_name == "Azure"
    
    def test_evaluate_priority_sorting(self):
        """Test candidate providers sorted by priority"""
        context = RuleContext(current_model="gpt-4")
        
        # Swap priority
        self.provider_mappings[0].priority = 10
        self.provider_mappings[1].priority = 1
        
        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )
        
        # Azure (priority 1) should be first
        assert candidates[0].provider_name == "Azure"
        assert candidates[1].provider_name == "OpenAI"

    def test_evaluate_provider_rules_empty_matches_all(self):
        """Test that empty provider_rules matches all requests (default behavior)"""
        context = RuleContext(
            current_model="gpt-4",
            headers={"x-priority": "any-value"},
            request_body={"temperature": 0.9, "max_tokens": 5000},
        )

        # Both providers have no rules - should both match
        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        assert len(candidates) == 2

    def test_evaluate_provider_rules_and_logic(self):
        """Test provider rules with AND logic"""
        context = RuleContext(
            current_model="gpt-4",
            headers={"x-priority": "high"},
            request_body={"temperature": 0.3},
        )

        # Set OpenAI provider rule with AND logic: high priority AND low temperature
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "headers.x-priority", "operator": "eq", "value": "high"},
                {"field": "body.temperature", "operator": "lt", "value": 0.5},
            ],
            "logic": "AND"
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Both should match (OpenAI with AND rules, Azure with no rules)
        assert len(candidates) == 2
        assert any(c.provider_name == "OpenAI" for c in candidates)
        assert any(c.provider_name == "Azure" for c in candidates)

    def test_evaluate_provider_rules_and_logic_fails(self):
        """Test provider rules with AND logic when one condition fails"""
        context = RuleContext(
            current_model="gpt-4",
            headers={"x-priority": "high"},
            request_body={"temperature": 0.8},  # High temperature
        )

        # Set OpenAI provider rule: high priority AND low temperature (AND logic)
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "headers.x-priority", "operator": "eq", "value": "high"},
                {"field": "body.temperature", "operator": "lt", "value": 0.5},
            ],
            "logic": "AND"
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Only Azure should match (OpenAI AND condition fails due to temperature)
        assert len(candidates) == 1
        assert candidates[0].provider_name == "Azure"

    def test_evaluate_provider_rules_or_logic(self):
        """Test provider rules with OR logic"""
        context = RuleContext(
            current_model="gpt-4",
            headers={"x-priority": "low"},  # Not high
            request_body={"temperature": 0.3},  # But low temperature
        )

        # Set OpenAI provider rule with OR logic
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "headers.x-priority", "operator": "eq", "value": "high"},
                {"field": "body.temperature", "operator": "lt", "value": 0.5},
            ],
            "logic": "OR"
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Both should match (OpenAI OR passes due to temperature, Azure has no rules)
        assert len(candidates) == 2

    def test_evaluate_provider_rules_or_logic_all_fail(self):
        """Test provider rules with OR logic when all conditions fail"""
        context = RuleContext(
            current_model="gpt-4",
            headers={"x-priority": "low"},  # Not high
            request_body={"temperature": 0.8},  # Not low
        )

        # Set OpenAI provider rule with OR logic
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "headers.x-priority", "operator": "eq", "value": "high"},
                {"field": "body.temperature", "operator": "lt", "value": 0.5},
            ],
            "logic": "OR"
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Only Azure should match (OpenAI OR condition fails)
        assert len(candidates) == 1
        assert candidates[0].provider_name == "Azure"

    def test_evaluate_all_providers_fail_rules(self):
        """Test when all providers fail their rules"""
        context = RuleContext(
            current_model="gpt-4",
            headers={"x-priority": "low"},
        )

        # Set both providers to require high priority
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "headers.x-priority", "operator": "eq", "value": "high"}
            ]
        }
        self.provider_mappings[1].provider_rules = {
            "rules": [
                {"field": "headers.x-priority", "operator": "eq", "value": "high"}
            ]
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # No providers should match
        assert len(candidates) == 0

    def test_evaluate_provider_rules_with_model_field(self):
        """Test provider rules matching on model name"""
        context = RuleContext(current_model="gpt-4")

        # OpenAI only accepts gpt-4, Azure only accepts claude
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "model", "operator": "eq", "value": "gpt-4"}
            ]
        }
        self.provider_mappings[1].provider_rules = {
            "rules": [
                {"field": "model", "operator": "eq", "value": "claude-3"}
            ]
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Only OpenAI should match
        assert len(candidates) == 1
        assert candidates[0].provider_name == "OpenAI"

    def test_evaluate_inactive_mapping(self):
        """Test that inactive provider mappings are skipped"""
        context = RuleContext(current_model="gpt-4")

        # Disable OpenAI mapping
        self.provider_mappings[0].is_active = False

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Only Azure should be returned
        assert len(candidates) == 1
        assert candidates[0].provider_name == "Azure"

    def test_evaluate_provider_rules_contains_operator(self):
        """Test provider rules with contains operator"""
        context = RuleContext(
            current_model="gpt-4-turbo-preview",
            headers={},
        )

        # OpenAI accepts models containing "gpt"
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "model", "operator": "contains", "value": "gpt"}
            ]
        }
        # Azure accepts models containing "claude"
        self.provider_mappings[1].provider_rules = {
            "rules": [
                {"field": "model", "operator": "contains", "value": "claude"}
            ]
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Only OpenAI should match
        assert len(candidates) == 1
        assert candidates[0].provider_name == "OpenAI"

    def test_evaluate_provider_rules_in_operator(self):
        """Test provider rules with in operator"""
        context = RuleContext(
            current_model="gpt-4",
            headers={"x-region": "us-east"},
        )

        # OpenAI only serves certain regions
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "headers.x-region", "operator": "in", "value": ["us-east", "us-west"]}
            ]
        }
        # Azure only serves EU regions
        self.provider_mappings[1].provider_rules = {
            "rules": [
                {"field": "headers.x-region", "operator": "in", "value": ["eu-west", "eu-central"]}
            ]
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Only OpenAI should match
        assert len(candidates) == 1
        assert candidates[0].provider_name == "OpenAI"

    def test_evaluate_provider_rules_regex_operator(self):
        """Test provider rules with regex operator"""
        context = RuleContext(
            current_model="gpt-4-0125-preview",
            headers={},
        )

        # OpenAI accepts models matching gpt-4-* pattern
        self.provider_mappings[0].provider_rules = {
            "rules": [
                {"field": "model", "operator": "regex", "value": r"gpt-4-\d+"}
            ]
        }
        # Azure only accepts specific model
        self.provider_mappings[1].provider_rules = {
            "rules": [
                {"field": "model", "operator": "eq", "value": "gpt-4"}
            ]
        }

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Only OpenAI should match (regex matches)
        assert len(candidates) == 1
        assert candidates[0].provider_name == "OpenAI"

    def test_evaluate_provider_missing_from_dict(self):
        """Test that missing provider in providers dict is handled gracefully"""
        context = RuleContext(current_model="gpt-4")

        # Remove Azure from providers dict
        del self.providers[2]

        candidates = self.engine.evaluate_sync(
            context=context,
            model_mapping=self.model_mapping,
            provider_mappings=self.provider_mappings,
            providers=self.providers,
        )

        # Only OpenAI should be returned
        assert len(candidates) == 1
        assert candidates[0].provider_name == "OpenAI"
