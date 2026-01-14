"""
Sanitizer Module Unit Tests
"""

import pytest
from app.common.sanitizer import (
    sanitize_authorization,
    sanitize_headers,
    sanitize_api_key_display,
)


class TestSanitizeAuthorization:
    """Authorization Sanitize Test"""
    
    def test_bearer_token(self):
        """Test Bearer token sanitization"""
        result = sanitize_authorization("Bearer sk-1234567890abcdef")
        assert result.startswith("Bearer sk-1")
        assert "***" in result
        assert result.endswith("ef")
    
    def test_plain_token(self):
        """Test plain token sanitization"""
        result = sanitize_authorization("lgw-abcdefghijklmnop")
        assert result.startswith("lgw-")
        assert "***" in result
    
    def test_short_token(self):
        """Test short token sanitization"""
        result = sanitize_authorization("short")
        assert result == "***"
    
    def test_empty_value(self):
        """Test empty value"""
        assert sanitize_authorization("") == ""
        assert sanitize_authorization(None) is None


class TestSanitizeHeaders:
    """Header Sanitize Test"""
    
    def test_sanitize_authorization_header(self):
        """Test authorization header sanitization"""
        headers = {
            "authorization": "Bearer sk-1234567890abcdef",
            "content-type": "application/json",
        }
        result = sanitize_headers(headers)
        
        assert "***" in result["authorization"]
        assert result["content-type"] == "application/json"
    
    def test_sanitize_x_api_key_header(self):
        """Test x-api-key header sanitization"""
        headers = {
            "x-api-key": "sk-1234567890abcdef",
            "user-agent": "test",
        }
        result = sanitize_headers(headers)
        
        assert "***" in result["x-api-key"]
        assert result["user-agent"] == "test"
    
    def test_not_modify_original(self):
        """Test original data is not modified"""
        headers = {
            "authorization": "Bearer sk-1234567890abcdef",
        }
        original = headers["authorization"]
        
        result = sanitize_headers(headers)
        
        assert headers["authorization"] == original
        assert result is not headers
    
    def test_empty_headers(self):
        """Test empty headers"""
        assert sanitize_headers({}) == {}
        assert sanitize_headers(None) == {}


class TestSanitizeApiKeyDisplay:
    """API Key Display Sanitize Test"""
    
    def test_sanitize_api_key(self):
        """Test API Key sanitization"""
        result = sanitize_api_key_display("lgw-abcdefghijklmnopqrstuvwxyz")
        assert result.startswith("lgw-")
        assert "***" in result