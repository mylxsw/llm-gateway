"""
Tests for ServiceProvider Model Encryption

Tests the automatic encryption/decryption of API keys in the ServiceProvider model.
"""

import pytest

from app.db.models import ServiceProvider
from app.common.encryption import is_encrypted, ENCRYPTION_PREFIX


class TestServiceProviderEncryption:
    """Test suite for ServiceProvider model encryption"""

    def test_set_api_key_encrypts_automatically(self):
        """Test that setting api_key automatically encrypts the value"""
        provider = ServiceProvider(
            name="test-provider",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        # Set the API key
        test_key = "sk-test-api-key-12345"
        provider.api_key = test_key

        # Internal storage should be encrypted
        assert provider._api_key is not None
        assert provider._api_key != test_key
        assert provider._api_key.startswith(ENCRYPTION_PREFIX)

    def test_get_api_key_decrypts_automatically(self):
        """Test that getting api_key automatically decrypts the value"""
        provider = ServiceProvider(
            name="test-provider",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        # Set and then get the API key
        test_key = "sk-test-api-key-12345"
        provider.api_key = test_key
        retrieved_key = provider.api_key

        # Retrieved value should be the original plaintext
        assert retrieved_key == test_key

    def test_set_none_api_key(self):
        """Test that setting None for api_key works correctly"""
        provider = ServiceProvider(
            name="test-provider",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        provider.api_key = None

        assert provider._api_key is None
        assert provider.api_key is None

    def test_set_empty_string_api_key(self):
        """Test that setting empty string for api_key results in None"""
        provider = ServiceProvider(
            name="test-provider",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        provider.api_key = ""

        assert provider._api_key is None
        assert provider.api_key is None

    def test_set_already_encrypted_value(self):
        """Test that setting an already encrypted value doesn't double-encrypt"""
        provider = ServiceProvider(
            name="test-provider",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        # Set a key and get the encrypted value
        provider.api_key = "test-key"
        encrypted = provider._api_key

        # Create a new provider and set the encrypted value directly
        provider2 = ServiceProvider(
            name="test-provider-2",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )
        provider2.api_key = encrypted

        # Should not double-encrypt
        assert provider2._api_key == encrypted

    def test_encryption_is_consistent(self):
        """Test that encryption produces consistent decryptable results"""
        provider1 = ServiceProvider(
            name="provider1",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )
        provider2 = ServiceProvider(
            name="provider2",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        test_key = "sk-same-key-for-both"

        provider1.api_key = test_key
        provider2.api_key = test_key

        # Both should decrypt to the same value
        assert provider1.api_key == test_key
        assert provider2.api_key == test_key

        # Note: encrypted values will be different due to random nonce
        assert provider1._api_key != provider2._api_key

    def test_long_api_key(self):
        """Test encrypting a long API key"""
        provider = ServiceProvider(
            name="test-provider",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        # Simulate a long API key
        long_key = "sk-" + "a" * 200
        provider.api_key = long_key

        assert provider.api_key == long_key

    def test_special_characters_in_api_key(self):
        """Test API key with special characters"""
        provider = ServiceProvider(
            name="test-provider",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        special_key = "sk-test_123!@#$%^&*()"
        provider.api_key = special_key

        assert provider.api_key == special_key

    def test_unicode_in_api_key(self):
        """Test API key with unicode characters"""
        provider = ServiceProvider(
            name="test-provider",
            base_url="https://api.example.com",
            protocol="openai",
            api_type="chat",
        )

        unicode_key = "sk-test-\u4e2d\u6587-key"
        provider.api_key = unicode_key

        assert provider.api_key == unicode_key
