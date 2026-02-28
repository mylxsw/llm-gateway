"""
Tests for Encryption Service

Tests the encryption/decryption functionality for API keys and sensitive data.
"""

import os
import pytest
from unittest.mock import patch

from app.common.encryption import (
    EncryptionService,
    EncryptionError,
    encrypt,
    decrypt,
    is_encrypted,
    get_encryption_service,
    ENCRYPTION_PREFIX,
)


class TestEncryptionService:
    """Test suite for EncryptionService"""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly together"""
        service = EncryptionService()
        plaintext = "sk-test-api-key-12345"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext
        assert encrypted.startswith(ENCRYPTION_PREFIX)

    def test_encrypt_produces_different_ciphertext(self):
        """Test that encrypting the same value twice produces different ciphertext (due to random nonce)"""
        service = EncryptionService()
        plaintext = "test-key"

        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)

        # Different ciphertext due to random nonce
        assert encrypted1 != encrypted2
        # But both decrypt to the same value
        assert service.decrypt(encrypted1) == plaintext
        assert service.decrypt(encrypted2) == plaintext

    def test_encrypt_empty_string(self):
        """Test encrypting empty string returns empty string"""
        service = EncryptionService()

        result = service.encrypt("")

        assert result == ""

    def test_decrypt_empty_string(self):
        """Test decrypting empty string returns empty string"""
        service = EncryptionService()

        result = service.decrypt("")

        assert result == ""

    def test_decrypt_none(self):
        """Test decrypting None returns None"""
        service = EncryptionService()

        result = service.decrypt(None)  # type: ignore

        assert result is None

    def test_decrypt_unencrypted_value_returns_as_is(self):
        """Test that unencrypted values (without prefix) are returned as-is for backward compatibility"""
        service = EncryptionService()
        plaintext = "unencrypted-key"

        result = service.decrypt(plaintext)

        assert result == plaintext

    def test_is_encrypted_with_prefix(self):
        """Test is_encrypted returns True for encrypted values"""
        service = EncryptionService()
        encrypted = service.encrypt("test")

        assert service.is_encrypted(encrypted) is True

    def test_is_encrypted_without_prefix(self):
        """Test is_encrypted returns False for unencrypted values"""
        service = EncryptionService()

        assert service.is_encrypted("plain-text") is False
        assert service.is_encrypted("") is False
        assert service.is_encrypted(None) is False

    def test_singleton_pattern(self):
        """Test that get_encryption_service returns the same instance"""
        service1 = get_encryption_service()
        service2 = get_encryption_service()

        assert service1 is service2

    def test_custom_encryption_key(self):
        """Test using a custom encryption key from environment variable"""
        import base64
        import secrets

        # Generate a valid key
        test_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

        with patch.dict(os.environ, {"ENCRYPTION_KEY": test_key}):
            # Reset singleton
            EncryptionService._instance = None
            EncryptionService._key = None

            service = EncryptionService()
            plaintext = "test-key-with-custom-key"

            encrypted = service.encrypt(plaintext)
            decrypted = service.decrypt(encrypted)

            assert decrypted == plaintext

        # Cleanup: reset singleton
        EncryptionService._instance = None
        EncryptionService._key = None

    def test_invalid_encryption_key_length(self):
        """Test that invalid key length raises error"""
        with patch.dict(os.environ, {"ENCRYPTION_KEY": "invalid-key"}):
            # Reset singleton
            EncryptionService._instance = None
            EncryptionService._key = None

            with pytest.raises(EncryptionError, match="Invalid ENCRYPTION_KEY"):
                EncryptionService()

        # Cleanup: reset singleton
        EncryptionService._instance = None
        EncryptionService._key = None

    def test_decrypt_tampered_ciphertext_fails(self):
        """Test that decrypting tampered ciphertext fails"""
        service = EncryptionService()
        encrypted = service.encrypt("test-key")

        # Tamper with the ciphertext
        tampered = encrypted[:-5] + "XXXXX"

        with pytest.raises(EncryptionError, match="Failed to decrypt"):
            service.decrypt(tampered)


class TestConvenienceFunctions:
    """Test suite for convenience functions"""

    def test_encrypt_function(self):
        """Test the encrypt convenience function"""
        plaintext = "test-key"

        encrypted = encrypt(plaintext)
        decrypted = decrypt(encrypted)

        assert decrypted == plaintext

    def test_decrypt_function(self):
        """Test the decrypt convenience function"""
        plaintext = "test-key"
        encrypted = encrypt(plaintext)

        result = decrypt(encrypted)

        assert result == plaintext

    def test_is_encrypted_function(self):
        """Test the is_encrypted convenience function"""
        encrypted = encrypt("test")

        assert is_encrypted(encrypted) is True
        assert is_encrypted("plain-text") is False


class TestEdgeCases:
    """Test edge cases and special scenarios"""

    def test_long_api_key(self):
        """Test encrypting a long API key"""
        service = EncryptionService()
        # Simulate a long API key
        plaintext = "sk-" + "a" * 200

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_unicode_characters(self):
        """Test encrypting unicode characters"""
        service = EncryptionService()
        plaintext = "test-key-\u4e2d\u6587-\U0001F600"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_special_characters(self):
        """Test encrypting special characters"""
        service = EncryptionService()
        plaintext = "test-key-!@#$%^&*()_+-=[]{}|;':\",./<>?"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_newlines_and_spaces(self):
        """Test encrypting text with newlines and spaces"""
        service = EncryptionService()
        plaintext = "test\nkey\nwith\nnewlines and spaces"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext
