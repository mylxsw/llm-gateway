"""
Data Sanitization Module

Sanitizes sensitive information (such as authorization headers)
to ensure logs do not contain plain text sensitive data.
"""

import re
from typing import Any


def sanitize_authorization(value: str) -> str:
    """
    Sanitize authorization field value
    
    Masks API Keys and other sensitive information, keeping a prefix and some characters for identification.
    
    Args:
        value: Original authorization value, e.g., "Bearer sk-xxxxxxxxxxxx"
    
    Returns:
        str: Sanitized value, e.g., "Bearer sk-***...***"
    
    Examples:
        >>> sanitize_authorization("Bearer sk-1234567890abcdef")
        'Bearer sk-12***...***ef'
        >>> sanitize_authorization("lgw-abcdefghijklmnop")
        'lgw-ab***...***op'
    """
    if not value:
        return value
    
    # Handle Bearer prefix
    prefix = ""
    token = value
    if value.lower().startswith("bearer "):
        prefix = "Bearer "
        token = value[7:]
    
    # If token is too short, mask directly
    if len(token) <= 8:
        return f"{prefix}***"
    
    # Keep first 4 and last 2 characters, mask middle
    return f"{prefix}{token[:4]}***...***{token[-2:]}"


def sanitize_headers(headers: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize request headers
    
    Sanitizes sensitive fields in request headers. Currently handles:
    - authorization
    - x-api-key
    - api-key
    
    Args:
        headers: Original headers dictionary
    
    Returns:
        dict: Sanitized headers dictionary (new dictionary, original data not modified)
    
    Examples:
        >>> headers = {"authorization": "Bearer sk-xxx", "content-type": "application/json"}
        >>> sanitize_headers(headers)
        {'authorization': 'Bearer sk-***...***', 'content-type': 'application/json'}
    """
    if not headers:
        return {}
    
    # Fields to sanitize (lowercase)
    sensitive_fields = {"authorization", "x-api-key", "api-key"}
    
    # Create new dictionary to avoid modifying original data
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in sensitive_fields and isinstance(value, str):
            sanitized[key] = sanitize_authorization(value)
        else:
            sanitized[key] = value
    
    return sanitized


def sanitize_api_key_display(key_value: str) -> str:
    """
    Sanitize API Key Display
    
    Used for masking API Key in list views.
    
    Args:
        key_value: Full API Key value
    
    Returns:
        str: Sanitized display value
    
    Examples:
        >>> sanitize_api_key_display("lgw-abcdefghijklmnopqrstuvwxyz")
        'lgw-abcd***...***yz'
    """
    return sanitize_authorization(key_value)