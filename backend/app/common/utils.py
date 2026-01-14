"""
Utility Functions Module

Provides common utility functions, such as API Key generation, Trace ID generation, etc.
"""

import json
import secrets
import uuid
from typing import Any, Optional

from app.config import get_settings


def generate_api_key(
    prefix: Optional[str] = None,
    length: Optional[int] = None
) -> str:
    """
    Generate Random API Key
    
    Uses secrets module to generate a cryptographically secure random token.
    
    Args:
        prefix: Key prefix, defaults to API_KEY_PREFIX in configuration
        length: Key length (excluding prefix), defaults to API_KEY_LENGTH in configuration
    
    Returns:
        str: Generated API Key, e.g., "lgw-xxxxxxxxxxxx"
    
    Example:
        >>> generate_api_key()
        'lgw-a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'
    """
    settings = get_settings()
    prefix = prefix or settings.API_KEY_PREFIX
    length = length or settings.API_KEY_LENGTH
    
    # Use secrets.token_hex to generate secure random string
    # token_hex returns hex string, length is double the bytes
    random_part = secrets.token_hex(length // 2)
    
    return f"{prefix}{random_part}"


def generate_trace_id() -> str:
    """
    Generate Request Trace ID
    
    Uses UUID4 to generate a unique trace identifier for correlating logs of the same request.
    
    Returns:
        str: UUID format trace ID
    
    Example:
        >>> generate_trace_id()
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890'
    """
    return str(uuid.uuid4())


def extract_model_from_body(body: dict) -> Optional[str]:
    """
    Extract model name from request body
    
    Supports OpenAI and Anthropic format request bodies.
    
    Args:
        body: Request body dictionary
    
    Returns:
        Optional[str]: Model name, or None if not present
    """
    return body.get("model")


def replace_model_in_body(body: dict, target_model: str) -> dict:
    """
    Replace model name in request body
    
    Only modifies the model field, other fields remain unchanged.
    Returns a new dictionary, does not modify original data.
    
    Args:
        body: Original request body
        target_model: Target model name
    
    Returns:
        dict: Replaced request body (new dictionary)
    """
    new_body = body.copy()
    new_body["model"] = target_model
    return new_body


def mask_string(s: str, visible_start: int = 4, visible_end: int = 2) -> str:
    """
    Mask string
    
    Keeps a few characters at start and end, replaces middle with asterisks.
    
    Args:
        s: Original string
        visible_start: Number of characters to keep at start
        visible_end: Number of characters to keep at end
    
    Returns:
        str: Masked string
    
    Example:
        >>> mask_string("abcdefghijklmnop")
        'abcd***...***op'
    """
    if len(s) <= visible_start + visible_end:
        return "***"
    return f"{s[:visible_start]}***...***{s[-visible_end:]}"


def try_parse_json_object(text: str) -> Any:
    """
    Try parsing string as JSON object/array

    Only attempts parsing if the string looks like a JSON object/array (starts with { or [),
    otherwise returns the original string if parsing fails.
    """
    stripped = text.strip()
    if not stripped:
        return text
    if not (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    ):
        return text
    try:
        return json.loads(stripped)
    except Exception:
        return text