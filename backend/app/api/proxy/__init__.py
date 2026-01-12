"""
Proxy API Module Initialization
"""

from app.api.proxy.openai import router as openai_router
from app.api.proxy.anthropic import router as anthropic_router

__all__ = [
    "openai_router",
    "anthropic_router",
]