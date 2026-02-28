# API Key Encryption Implementation

This document describes the implementation of encrypted storage for third-party API keys.

## Overview

The `ServiceProvider.api_key` field now uses AES-256-GCM encryption to protect sensitive API keys stored in the database.

## Components

### 1. Encryption Service (`app/common/encryption.py`)

Core encryption service using AES-256-GCM:

- **Algorithm**: AES-256-GCM (provides both confidentiality and integrity)
- **Key Source**: Environment variable `ENCRYPTION_KEY` (base64-encoded 32-byte key)
- **Fallback**: Auto-generates a temporary key if `ENCRYPTION_KEY` is not set (with warning)

Key features:
- `encrypt(plaintext: str) -> str` - Encrypts and returns base64-encoded ciphertext with "enc:" prefix
- `decrypt(ciphertext: str) -> str` - Decrypts encrypted values, returns plaintext as-is for backward compatibility
- `is_encrypted(value: str) -> bool` - Checks if a value is encrypted

### 2. Model Encryption (`app/db/models.py`)

The `ServiceProvider` model has been updated with automatic encryption/decryption:

```python
# Setting API key - automatically encrypts
provider.api_key = "sk-plaintext-key"
# Internal storage: "enc:base64-encoded-ciphertext..."

# Getting API key - automatically decrypts
api_key = provider.api_key
# Returns: "sk-plaintext-key"
```

### 3. Configuration (`app/config.py`)

New configuration option:

```python
ENCRYPTION_KEY: str | None = None
```

Set via environment variable or `.env` file.

### 4. Data Migration (`migrations/encrypt_api_keys.py`)

Script to encrypt existing plaintext API keys:

```bash
# Generate encryption key
python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

# Set environment variable
export ENCRYPTION_KEY="your-generated-key-here"

# Preview changes (dry run)
python migrations/encrypt_api_keys.py --dry-run

# Run migration
python migrations/encrypt_api_keys.py
```

## Security Considerations

### Key Management

1. **Generate a secure key**: Use the provided command to generate a cryptographically secure key
2. **Store securely**: Save the key in a secure location (e.g., secrets manager, environment variables)
3. **Never commit**: Do not commit the encryption key to version control
4. **Key rotation**: Plan for key rotation (currently requires manual migration)

### Encryption Properties

- **Algorithm**: AES-256-GCM
- **Key Length**: 256 bits (32 bytes)
- **Nonce**: 12 bytes (randomly generated for each encryption)
- **Authentication**: GCM mode provides authenticated encryption

### Backward Compatibility

The system maintains backward compatibility with unencrypted API keys:

- Unencrypted values (no "enc:" prefix) are returned as-is by the decrypt function
- This allows gradual migration and testing
- The migration script skips already encrypted values

## Usage Examples

### Programmatic Usage

```python
from app.common.encryption import encrypt, decrypt, is_encrypted

# Encrypt a value
encrypted = encrypt("my-api-key")
# Result: "enc:Uw3YKQWvVgcw..."

# Decrypt a value
decrypted = decrypt(encrypted)
# Result: "my-api-key"

# Check if encrypted
if is_encrypted(value):
    print("Value is encrypted")
```

### Model Usage

```python
from app.db.models import ServiceProvider

# Create provider with API key
provider = ServiceProvider(
    name="openai",
    base_url="https://api.openai.com",
    protocol="openai",
    api_type="chat",
)
provider.api_key = "sk-openai-key-12345"

# API key is automatically encrypted in storage
print(provider._api_key)  # "enc:..."

# API key is automatically decrypted on access
print(provider.api_key)  # "sk-openai-key-12345"
```

### Environment Setup

```bash
# .env file
ENCRYPTION_KEY=HVx9vVfo5y-kkR39gDXiRIi3Mu-A1q8DGqGyrMjsAQs=
```

## Testing

Run the encryption tests:

```bash
# Unit tests for encryption service
pytest tests/unit/test_common/test_encryption.py -v

# Unit tests for model encryption
pytest tests/unit/test_models/test_service_provider_encryption.py -v
```

## Migration Guide

### For New Deployments

1. Generate an encryption key before deployment
2. Set `ENCRYPTION_KEY` environment variable
3. Deploy the application
4. All new API keys will be encrypted automatically

### For Existing Deployments

1. **Backup your database** before proceeding
2. Generate an encryption key
3. Set `ENCRYPTION_KEY` environment variable
4. Run migration script in dry-run mode to preview changes
5. Run migration script to encrypt existing keys
6. Restart the application
7. Verify that API keys work correctly

### Rollback Plan

If issues arise:

1. Restore database from backup
2. The model's decrypt function handles both encrypted and plaintext values
3. System will continue to work with restored plaintext keys

## Troubleshooting

### "Failed to decrypt API key" errors

**Cause**: Encryption key mismatch or corrupted data

**Solution**:
1. Verify `ENCRYPTION_KEY` is set correctly
2. Check that the key matches the one used for encryption
3. If key was changed, restore from backup or re-encrypt with new key

### "Invalid ENCRYPTION_KEY format" errors

**Cause**: Malformed encryption key

**Solution**:
1. Verify the key is base64-encoded
2. Verify the key decodes to exactly 32 bytes
3. Regenerate the key if necessary

### API keys not being encrypted

**Cause**: Using model field directly instead of property

**Solution**: Always use `provider.api_key` (property), not `provider._api_key` (internal field)

## Dependencies

- `cryptography>=42.0.0` - Provides AES-256-GCM encryption

## Future Improvements

Potential enhancements for future versions:

1. **Key rotation**: Add support for rotating encryption keys
2. **Key versioning**: Support multiple encryption keys for gradual rotation
3. **HSM integration**: Support hardware security modules for key storage
4. **Audit logging**: Log encryption/decryption operations for security auditing
