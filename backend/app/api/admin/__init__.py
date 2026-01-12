"""
Admin API Module Initialization
"""

from app.api.admin.providers import router as providers_router
from app.api.admin.models import router as models_router
from app.api.admin.api_keys import router as api_keys_router
from app.api.admin.logs import router as logs_router

__all__ = [
    "providers_router",
    "models_router",
    "api_keys_router",
    "logs_router",
]