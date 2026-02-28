"""
Unit tests for URL security validator
"""

import pytest

from app.common.errors import ValidationError
from app.common.url_validator import (
    is_private_ip,
    validate_provider_url,
    validate_provider_url_loose,
    validate_provider_url_strict,
)


class TestPrivateIPDetection:
    """Tests for private IP detection"""

    def test_loopback_ipv4(self):
        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("127.0.0.100") is True

    def test_loopback_ipv6(self):
        assert is_private_ip("::1") is True

    def test_class_a_private(self):
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True

    def test_class_b_private(self):
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True

    def test_class_c_private(self):
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("192.168.100.50") is True

    def test_link_local(self):
        assert is_private_ip("169.254.1.1") is True

    def test_public_ip(self):
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
        assert is_private_ip("142.250.185.78") is False

    def test_invalid_ip(self):
        assert is_private_ip("invalid") is False
        assert is_private_ip("256.256.256.256") is False


class TestURLValidationLoose:
    """Tests for loose URL validation (only blocks private IPs)"""

    def test_valid_https_url(self):
        result = validate_provider_url_loose("https://api.openai.com/v1")
        assert result == "https://api.openai.com/v1"

    def test_valid_http_url(self):
        result = validate_provider_url_loose("http://example.com/api")
        assert result == "http://example.com/api"

    def test_empty_url(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_loose("")
        assert exc_info.value.code == "invalid_url"

    def test_invalid_scheme(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_loose("ftp://example.com")
        assert exc_info.value.code == "invalid_url_scheme"

    def test_file_scheme_blocked(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_loose("file:///etc/passwd")
        assert exc_info.value.code == "invalid_url_scheme"

    def test_localhost_blocked(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_loose("http://localhost:8080")
        # localhost resolves to 127.0.0.1, so it's caught by DNS resolution check
        assert exc_info.value.code in ("private_ip_not_allowed", "private_ip_resolution")

    def test_loopback_ip_blocked(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_loose("http://127.0.0.1:8080")
        assert exc_info.value.code == "private_ip_not_allowed"

    def test_private_ip_blocked(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_loose("http://192.168.1.1/api")
        assert exc_info.value.code == "private_ip_not_allowed"


class TestURLValidationStrict:
    """Tests for strict URL validation (whitelist only)"""

    def test_openai_allowed(self):
        result = validate_provider_url_strict("https://api.openai.com/v1")
        assert result == "https://api.openai.com/v1"

    def test_anthropic_allowed(self):
        result = validate_provider_url_strict("https://api.anthropic.com/v1")
        assert result == "https://api.anthropic.com/v1"

    def test_gemini_allowed(self):
        result = validate_provider_url_strict("https://generativelanguage.googleapis.com")
        assert result == "https://generativelanguage.googleapis.com"

    def test_deepseek_allowed(self):
        result = validate_provider_url_strict("https://api.deepseek.com")
        assert result == "https://api.deepseek.com"

    def test_unknown_domain_blocked(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_strict("https://unknown-api.example.com")
        assert exc_info.value.code == "url_domain_not_allowed"

    def test_localhost_blocked_in_strict(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_strict("http://localhost:8080")
        # Should fail domain whitelist check first
        assert exc_info.value.code in ("url_domain_not_allowed", "private_ip_not_allowed")


class TestURLValidationEdgeCases:
    """Tests for edge cases in URL validation"""

    def test_url_with_port(self):
        result = validate_provider_url_loose("https://api.example.com:8443/v1")
        assert result == "https://api.example.com:8443/v1"

    def test_url_with_path(self):
        result = validate_provider_url_loose("https://api.example.com/some/path/v1")
        assert result == "https://api.example.com/some/path/v1"

    def test_url_with_query(self):
        result = validate_provider_url_loose("https://api.example.com/v1?key=value")
        assert result == "https://api.example.com/v1?key=value"

    def test_url_with_fragment(self):
        result = validate_provider_url_loose("https://api.example.com/v1#fragment")
        assert result == "https://api.example.com/v1#fragment"

    def test_url_without_scheme(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_loose("api.example.com/v1")
        assert exc_info.value.code == "invalid_url_scheme"

    def test_ipv4_public(self):
        # Public IP should be allowed in loose mode
        result = validate_provider_url_loose("https://1.1.1.1/api")
        assert result == "https://1.1.1.1/api"

    def test_ipv4_private_blocked(self):
        with pytest.raises(ValidationError) as exc_info:
            validate_provider_url_loose("https://10.0.0.1/api")
        assert exc_info.value.code == "private_ip_not_allowed"
