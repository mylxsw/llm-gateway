"""
Rule Context Module

Defines the context data structure required for rule engine execution.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TokenUsage:
    """
    Token Usage Data Class
    
    Records Token consumption for the request.
    """
    
    # Input Token Count
    input_tokens: int = 0
    # Output Token Count (Usually not yet produced during rule evaluation)
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        """Get total Token count"""
        return self.input_tokens + self.output_tokens


@dataclass
class RuleContext:
    """
    Rule Engine Context
    
    Contains all input data required for rule evaluation:
    - current_model: Current requested model name
    - headers: Request headers (structured object)
    - request_body: Request body (structured object)
    - token_usage: Token consumption statistics
    """
    
    # Current requested model name (requested_model)
    current_model: str
    # Request headers
    headers: dict[str, str] = field(default_factory=dict)
    # Request body
    request_body: dict[str, Any] = field(default_factory=dict)
    # Token usage
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    
    def get_value(self, field_path: str) -> Optional[Any]:
        """
        Get value by field path
        
        Supports the following path formats:
        - "model" -> current_model
        - "headers.x-priority" -> headers["x-priority"]
        - "body.temperature" -> request_body["temperature"]
        - "body.messages[0].role" -> request_body["messages"][0]["role"]
        - "token_usage.input_tokens" -> token_usage.input_tokens
        
        Args:
            field_path: Field path
        
        Returns:
            Optional[Any]: Field value, or None if not found
        """
        if not field_path:
            return None
        
        parts = field_path.split(".")
        root = parts[0].lower()
        
        # Handle root fields
        if root == "model":
            return self.current_model
        elif root == "headers":
            return self._get_nested_value(self.headers, parts[1:])
        elif root == "body":
            return self._get_nested_value(self.request_body, parts[1:])
        elif root == "token_usage":
            return self._get_token_usage_value(parts[1:])
        
        return None
    
    def _get_nested_value(self, obj: Any, path: list[str]) -> Optional[Any]:
        """
        Get value from nested object
        
        Supports dictionary key and array index access.
        
        Args:
            obj: Current object
            path: Remaining path parts
        
        Returns:
            Optional[Any]: Value or None
        """
        if not path:
            return obj
        
        current = path[0]
        remaining = path[1:]
        
        # Handle array index, e.g., "messages[0]"
        if "[" in current and current.endswith("]"):
            key = current[:current.index("[")]
            index_str = current[current.index("[") + 1:-1]
            
            try:
                index = int(index_str)
                if isinstance(obj, dict) and key in obj:
                    arr = obj[key]
                    if isinstance(arr, list) and 0 <= index < len(arr):
                        return self._get_nested_value(arr[index], remaining)
            except (ValueError, IndexError):
                pass
            return None
        
        # Handle normal key
        if isinstance(obj, dict) and current in obj:
            return self._get_nested_value(obj[current], remaining)
        
        return None
    
    def _get_token_usage_value(self, path: list[str]) -> Optional[Any]:
        """Get value from token_usage"""
        if not path:
            return self.token_usage
        
        field_name = path[0]
        if field_name == "input_tokens":
            return self.token_usage.input_tokens
        elif field_name == "output_tokens":
            return self.token_usage.output_tokens
        elif field_name == "total_tokens":
            return self.token_usage.total_tokens
        
        return None