"""
Base Repository Interface Module

Defines the generic interface for data access, decoupling business logic from specific database implementations.
"""

from abc import ABC
from typing import Generic, TypeVar, Optional, List

# Define generic type variable
T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Base Repository Interface
    
    Defines standard CRUD operations.
    """
    pass