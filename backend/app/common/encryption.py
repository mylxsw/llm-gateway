"""
Encryption Service Module

Provides AES-256-GCM encryption for sensitive data like API keys.
"""

import base64
import logging
import os
import secrets
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

# AES-256 key length (32 bytes)
KEY_LENGTH = 32

# Nonce length for GCM (12 bytes is recommended)
NONCE_LENGTH = 12

# Prefix for encrypted values to identify them
ENCRYPTION_PREFIX = "enc:"


class EncryptionError(Exception):
    """Encryption/Decryption error"""
    pass


class EncryptionService:
    """
    Encryption Service

    Uses AES-256-GCM for encryption, providing both confidentiality and integrity.
    The encryption key can be provided via environment variable or auto-generated.
    """

    _instance: Optional["EncryptionService"] = None
    _key: Optional[bytes] = None

    def __new__(cls) -> "EncryptionService":
        """Singleton pattern to ensure only one instance exists"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize encryption service with key"""
        if self._key is None:
            self._key = self._get_or_create_key()

    def _get_or_create_key(self) -> bytes:
        """
        Get encryption key from environment or create a new one

        Returns:
            bytes: 32-byte encryption key

        Warning:
            If ENCRYPTION_KEY is not set, a key will be generated.
            This key will change on restart, making previously encrypted data unreadable.
            Always set ENCRYPTION_KEY in production!
        """
        env_key = os.environ.get("ENCRYPTION_KEY")

        if env_key:
            # Key from environment - decode from base64
            try:
                key = base64.urlsafe_b64decode(env_key)
                if len(key) != KEY_LENGTH:
                    raise ValueError(
                        f"Invalid ENCRYPTION_KEY length: expected {KEY_LENGTH} bytes, "
                        f"got {len(key)}"
                    )
                logger.info("Encryption key loaded from environment variable")
                return key
            except Exception as e:
                logger.error(f"Failed to decode ENCRYPTION_KEY: {e}")
                raise EncryptionError(
                    f"Invalid ENCRYPTION_KEY format: {e}"
                ) from e
        else:
            # Generate a new key (not recommended for production)
            key = secrets.token_bytes(KEY_LENGTH)
            encoded_key = base64.urlsafe_b64encode(key).decode("utf-8")

            logger.warning(
                "=" * 70 + "\n"
                "WARNING: ENCRYPTION_KEY not set! A temporary key has been generated.\n"
                "This key will change on restart, making previously encrypted data unreadable.\n"
                "\n"
                "For production, set the following environment variable:\n"
                f"ENCRYPTION_KEY={encoded_key}\n"
                "\n"
                "Store this key securely! It cannot be recovered if lost.\n"
                + "=" * 70
            )
            return key

    @property
    def key(self) -> bytes:
        """Get the encryption key"""
        if self._key is None:
            self._key = self._get_or_create_key()
        return self._key

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string

        Args:
            plaintext: String to encrypt

        Returns:
            str: Base64-encoded ciphertext with prefix "enc:"

        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            return plaintext

        try:
            # Generate random nonce
            nonce = secrets.token_bytes(NONCE_LENGTH)

            # Create AESGCM cipher
            aesgcm = AESGCM(self.key)

            # Encrypt (plaintext must be bytes)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

            # Combine nonce + ciphertext and encode
            combined = nonce + ciphertext
            encoded = base64.urlsafe_b64encode(combined).decode("utf-8")

            return f"{ENCRYPTION_PREFIX}{encoded}"

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}") from e

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a ciphertext string

        Args:
            ciphertext: Encrypted string (with "enc:" prefix) or plaintext

        Returns:
            str: Decrypted plaintext

        Raises:
            EncryptionError: If decryption fails or data is corrupted

        Note:
            If the input doesn't have the "enc:" prefix, it's returned as-is.
            This allows for backward compatibility with unencrypted data.
        """
        if not ciphertext:
            return ciphertext

        # If not encrypted (no prefix), return as-is for backward compatibility
        if not ciphertext.startswith(ENCRYPTION_PREFIX):
            return ciphertext

        try:
            # Remove prefix and decode
            encoded = ciphertext[len(ENCRYPTION_PREFIX):]
            combined = base64.urlsafe_b64decode(encoded)

            # Extract nonce and ciphertext
            nonce = combined[:NONCE_LENGTH]
            actual_ciphertext = combined[NONCE_LENGTH:]

            # Create AESGCM cipher
            aesgcm = AESGCM(self.key)

            # Decrypt
            plaintext = aesgcm.decrypt(nonce, actual_ciphertext, None)

            return plaintext.decode("utf-8")

        except InvalidTag:
            logger.error("Decryption failed: invalid authentication tag (data may be corrupted or tampered)")
            raise EncryptionError(
                "Failed to decrypt data: invalid or corrupted ciphertext"
            )
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt data: {e}") from e

    def is_encrypted(self, value: Optional[str]) -> bool:
        """
        Check if a value is encrypted

        Args:
            value: Value to check

        Returns:
            bool: True if value appears to be encrypted
        """
        if not value:
            return False
        return value.startswith(ENCRYPTION_PREFIX)


# Global encryption service instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get the global encryption service instance

    Returns:
        EncryptionService: Singleton encryption service
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt(plaintext: str) -> str:
    """
    Convenience function to encrypt data

    Args:
        plaintext: String to encrypt

    Returns:
        str: Encrypted string
    """
    return get_encryption_service().encrypt(plaintext)


def decrypt(ciphertext: str) -> str:
    """
    Convenience function to decrypt data

    Args:
        ciphertext: Encrypted string

    Returns:
        str: Decrypted string
    """
    return get_encryption_service().decrypt(ciphertext)


def is_encrypted(value: Optional[str]) -> bool:
    """
    Convenience function to check if a value is encrypted

    Args:
        value: Value to check

    Returns:
        bool: True if encrypted
    """
    return get_encryption_service().is_encrypted(value)
