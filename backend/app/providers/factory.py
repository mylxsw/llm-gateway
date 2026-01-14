"""
Provider Client Factory Module

Creates corresponding provider clients based on protocol type.
"""

from app.providers.base import ProviderClient
from app.providers.openai_client import OpenAIClient
from app.providers.anthropic_client import AnthropicClient


# Client cache
_clients: dict[str, ProviderClient] = {}


def get_provider_client(protocol: str) -> ProviderClient:
    """
    Get provider client for the specified protocol
    
    Uses caching to avoid repeated client instantiation.
    
    Args:
        protocol: Protocol type, "openai" or "anthropic"
    
    Returns:
        ProviderClient: Corresponding client instance
    
    Raises:
        ValueError: Unsupported protocol type
    """
    protocol = protocol.lower()
    
    if protocol not in _clients:
        if protocol == "openai":
            _clients[protocol] = OpenAIClient()
        elif protocol == "anthropic":
            _clients[protocol] = AnthropicClient()
        else:
            raise ValueError(f"Unsupported protocol: {protocol}")
    
    return _clients[protocol]