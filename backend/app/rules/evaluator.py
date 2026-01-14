"""
Rule Evaluator Module

Provides the core logic for rule evaluation.
"""

import re
from typing import Any, Optional

from app.rules.context import RuleContext
from app.rules.models import Rule, RuleSet


class RuleEvaluator:
    """
    Rule Evaluator
    
    Responsible for evaluating the matching status of single rules and rule sets.
    
    Supported operators:
    - eq: Equal
    - ne: Not Equal
    - gt: Greater Than
    - gte: Greater Than or Equal
    - lt: Less Than
    - lte: Less Than or Equal
    - contains: Contains (string)
    - not_contains: Not Contains (string)
    - regex: Regular Expression Match
    - in: In List
    - not_in: Not In List
    - exists: Field Exists
    """
    
    def evaluate_rule(self, rule: Rule, context: RuleContext) -> bool:
        """
        Evaluate a single rule
        
        Args:
            rule: Rule
            context: Rule context
        
        Returns:
            bool: Whether the rule matches
        """
        # Get field value
        actual_value = context.get_value(rule.field)
        expected_value = rule.value
        operator = rule.operator.lower()
        
        # Evaluate based on operator
        try:
            if operator == "eq":
                return self._evaluate_eq(actual_value, expected_value)
            elif operator == "ne":
                return self._evaluate_ne(actual_value, expected_value)
            elif operator == "gt":
                return self._evaluate_gt(actual_value, expected_value)
            elif operator == "gte":
                return self._evaluate_gte(actual_value, expected_value)
            elif operator == "lt":
                return self._evaluate_lt(actual_value, expected_value)
            elif operator == "lte":
                return self._evaluate_lte(actual_value, expected_value)
            elif operator == "contains":
                return self._evaluate_contains(actual_value, expected_value)
            elif operator == "not_contains":
                return self._evaluate_not_contains(actual_value, expected_value)
            elif operator == "regex":
                return self._evaluate_regex(actual_value, expected_value)
            elif operator == "in":
                return self._evaluate_in(actual_value, expected_value)
            elif operator == "not_in":
                return self._evaluate_not_in(actual_value, expected_value)
            elif operator == "exists":
                return self._evaluate_exists(actual_value, expected_value)
            else:
                # Unknown operator, default not match
                return False
        except Exception:
            # Evaluation error, default not match
            return False
    
    def evaluate_ruleset(
        self, ruleset: Optional[RuleSet], context: RuleContext
    ) -> bool:
        """
        Evaluate a rule set
        
        Args:
            ruleset: Rule set
            context: Rule context
        
        Returns:
            bool: Whether the rule set matches
        """
        # Empty rule set passes by default
        if ruleset is None or ruleset.is_empty():
            return True
        
        results = [self.evaluate_rule(rule, context) for rule in ruleset.rules]
        
        if ruleset.logic == "OR":
            return any(results)
        else:  # AND (default)
            return all(results)
    
    # ============ Operator Implementation ============
    
    def _evaluate_eq(self, actual: Any, expected: Any) -> bool:
        """Equal"""
        return actual == expected
    
    def _evaluate_ne(self, actual: Any, expected: Any) -> bool:
        """Not Equal"""
        return actual != expected
    
    def _evaluate_gt(self, actual: Any, expected: Any) -> bool:
        """Greater Than"""
        if actual is None:
            return False
        return actual > expected
    
    def _evaluate_gte(self, actual: Any, expected: Any) -> bool:
        """Greater Than or Equal"""
        if actual is None:
            return False
        return actual >= expected
    
    def _evaluate_lt(self, actual: Any, expected: Any) -> bool:
        """Less Than"""
        if actual is None:
            return False
        return actual < expected
    
    def _evaluate_lte(self, actual: Any, expected: Any) -> bool:
        """Less Than or Equal"""
        if actual is None:
            return False
        return actual <= expected
    
    def _evaluate_contains(self, actual: Any, expected: Any) -> bool:
        """Contains (string)"""
        if actual is None or not isinstance(actual, str):
            return False
        return str(expected) in actual
    
    def _evaluate_not_contains(self, actual: Any, expected: Any) -> bool:
        """Not Contains (string)"""
        if actual is None or not isinstance(actual, str):
            return True
        return str(expected) not in actual
    
    def _evaluate_regex(self, actual: Any, expected: Any) -> bool:
        """Regular Expression Match"""
        if actual is None or not isinstance(actual, str):
            return False
        try:
            pattern = re.compile(str(expected))
            return bool(pattern.search(actual))
        except re.error:
            return False
    
    def _evaluate_in(self, actual: Any, expected: Any) -> bool:
        """In List"""
        if not isinstance(expected, (list, tuple)):
            return False
        return actual in expected
    
    def _evaluate_not_in(self, actual: Any, expected: Any) -> bool:
        """Not In List"""
        if not isinstance(expected, (list, tuple)):
            return True
        return actual not in expected
    
    def _evaluate_exists(self, actual: Any, expected: Any) -> bool:
        """Field Exists"""
        exists = actual is not None
        # When expected is True, check exists; when False, check not exists
        if expected:
            return exists
        return not exists