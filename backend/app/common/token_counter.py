"""
Token Counter Module

Provides Token counting implementations for different protocols (OpenAI, Anthropic).
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Optional

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class TokenCounter(ABC):
    """
    Token Counter Abstract Base Class
    
    Defines the standard interface for Token counting, with concrete implementations provided by subclasses.
    """
    
    @abstractmethod
    def count_tokens(self, text: str, model: str = "") -> int:
        """
        Count tokens in text
        
        Args:
            text: Text to count
            model: Model name (different models may use different tokenizers)
        
        Returns:
            int: Token count
        """
        pass
    
    @abstractmethod
    def count_messages(self, messages: list[dict[str, Any]], model: str = "") -> int:
        """
        Count tokens in a message list
        
        Args:
            messages: Message list, e.g., [{"role": "user", "content": "Hello"}]
            model: Model name
        
        Returns:
            int: Token count
        """
        pass


class OpenAITokenCounter(TokenCounter):
    """
    OpenAI Token Counter
    
    Uses tiktoken library for precise Token counting.
    Supports models like GPT-3.5, GPT-4.
    """
    
    # Default encoding
    DEFAULT_ENCODING = "cl100k_base"
    
    # Map models to encodings
    MODEL_ENCODING_MAP = {
        "gpt-4": "cl100k_base",
        "gpt-4-32k": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "text-embedding-ada-002": "cl100k_base",
        "text-davinci-003": "p50k_base",
    }
    
    def __init__(self):
        """Initialize Counter"""
        self._encodings: dict[str, Any] = {}
    
    def _get_encoding(self, model: str) -> Any:
        """
        Get encoder for model
        
        Args:
            model: Model name
        
        Returns:
            tiktoken encoder instance
        """
        if not TIKTOKEN_AVAILABLE:
            return None
        
        # Find encoding for model
        encoding_name = self.DEFAULT_ENCODING
        for model_prefix, enc_name in self.MODEL_ENCODING_MAP.items():
            if model.startswith(model_prefix):
                encoding_name = enc_name
                break
        
        # Cache encoder
        if encoding_name not in self._encodings:
            self._encodings[encoding_name] = tiktoken.get_encoding(encoding_name)
        
        return self._encodings[encoding_name]
    
    def count_tokens(self, text: str, model: str = "") -> int:
        """
        Count tokens in text
        
        Uses tiktoken for precise calculation. If tiktoken is unavailable,
        uses estimation (approx. 4 chars per token).
        
        Args:
            text: Text to count
            model: Model name
        
        Returns:
            int: Token count
        """
        if not text:
            return 0
        
        encoding = self._get_encoding(model)
        if encoding:
            return len(encoding.encode(text))
        
        # Fallback estimation: average 4 chars per token
        return len(text) // 4
    
    def count_messages(self, messages: list[dict[str, Any]], model: str = "") -> int:
        """
        Count tokens in a message list
        
        Calculates based on OpenAI message format, including role and content overhead.
        
        Args:
            messages: Message list
            model: Model name
        
        Returns:
            int: Token count
        """
        if not messages:
            return 0
        
        # Overhead per message
        tokens_per_message = 4  # <|start|>role<|separator|>content<|end|>
        tokens_per_name = -1  # If there's a name field
        
        total_tokens = 0
        for message in messages:
            total_tokens += tokens_per_message
            for key, value in message.items():
                if isinstance(value, str):
                    total_tokens += self.count_tokens(value, model)
                elif isinstance(value, list):
                    # Handle content as array (multimodal)
                    for item in value:
                        if isinstance(item, dict) and "text" in item:
                            total_tokens += self.count_tokens(item["text"], model)
                if key == "name":
                    total_tokens += tokens_per_name
        
        total_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>
        return total_tokens


class AnthropicTokenCounter(TokenCounter):
    """
    Anthropic Token Counter
    
    Anthropic uses its own tokenizer; providing estimation here.
    Ideally, integrate Anthropic's official tokenizer.
    """
    
    def count_tokens(self, text: str, model: str = "") -> int:
        """
        Count tokens in text
        
        Uses estimation method. Anthropic's tokenizer is similar to OpenAI's
        but implementation details may differ.
        
        Args:
            text: Text to count
            model: Model name
        
        Returns:
            int: Token count (Estimated)
        """
        if not text:
            return 0
        
        # Estimation: average 4 chars per token
        # TODO: Integrate Anthropic official tokenizer for precise counting
        return len(text) // 4
    
    def count_messages(self, messages: list[dict[str, Any]], model: str = "") -> int:
        """
        Count tokens in a message list
        
        Args:
            messages: Message list
            model: Model name
        
        Returns:
            int: Token count (Estimated)
        """
        if not messages:
            return 0
        
        total_tokens = 0
        for message in messages:
            # Anthropic message format
            role = message.get("role", "")
            content = message.get("content", "")
            
            total_tokens += self.count_tokens(role, model)
            
            if isinstance(content, str):
                total_tokens += self.count_tokens(content, model)
            elif isinstance(content, list):
                # Handle content as array
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        total_tokens += self.count_tokens(item["text"], model)
            
            # Message overhead
            total_tokens += 4
        
        return total_tokens


def get_token_counter(protocol: str) -> TokenCounter:
    """
    Get Token Counter for specified protocol
    
    Args:
        protocol: Protocol type, "openai" or "anthropic"
    
    Returns:
        TokenCounter: Corresponding counter instance
    """
    if protocol.lower() == "anthropic":
        return AnthropicTokenCounter()
    return OpenAITokenCounter()