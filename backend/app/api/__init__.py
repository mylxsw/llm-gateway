"""
API Router Module Initialization
"""

from app.api.deps import get_db, get_current_api_key

__all__ = [
    "get_db",
    "get_current_api_key",
]