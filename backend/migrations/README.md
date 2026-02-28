# Database Migrations

This directory contains manual SQL migration scripts for the database schema.

## Running Migrations

### SQLite

```bash
sqlite3 your_database.db < migrations/add_is_stream_column.sql
```

### PostgreSQL

```bash
psql -U username -d database_name -f migrations/add_is_stream_column.sql
```

## Migration Files

- `add_is_stream_column.sql` - Adds the `is_stream` boolean field to the `request_logs` table to indicate whether a request is a stream request.
- `add_extra_headers_column.sql` - Adds the `extra_headers` JSON field to the `service_providers` table for custom headers.
- `add_provider_options_column.sql` - Adds the `provider_options` JSON field to the `service_providers` table for provider options.
- `add_protocol_conversion_columns.sql` - Adds protocol conversion tracking columns to `request_logs` for debugging and analysis:
  - `request_protocol` - Client request protocol (openai/anthropic)
  - `supplier_protocol` - Upstream supplier protocol (openai/anthropic)
  - `converted_request_body` - Request body after protocol conversion
  - `upstream_response_body` - Original upstream response before protocol conversion
- `remove_model_provider_unique_constraint.sql` - Drops the unique constraint on `(requested_model, provider_id)` to allow duplicate provider mappings per model.

## Data Migrations

### Encrypt API Keys (`encrypt_api_keys.py`)

This Python script encrypts all plaintext API keys stored in the `service_providers` table.

**Background**: API keys were previously stored in plaintext, which is a security risk. This migration encrypts them using AES-256-GCM.

#### Prerequisites

1. Install dependencies:
   ```bash
   cd backend
   uv sync
   ```

2. Generate an encryption key (RECOMMENDED for production):
   ```bash
   python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

3. Set the encryption key as an environment variable:
   ```bash
   export ENCRYPTION_KEY="your-generated-key-here"
   ```

   **IMPORTANT**: Save this key securely! If lost, all encrypted API keys will become unreadable.

#### Running the Migration

1. **Dry Run** (preview changes without making them):
   ```bash
   cd backend
   python migrations/encrypt_api_keys.py --dry-run
   ```

2. **Actual Migration**:
   ```bash
   cd backend
   python migrations/encrypt_api_keys.py
   ```

3. **With Verbose Logging**:
   ```bash
   python migrations/encrypt_api_keys.py --verbose
   ```

#### What the Migration Does

1. Reads all providers from the database
2. Identifies API keys that are not yet encrypted (don't have the `enc:` prefix)
3. Encrypts each plaintext API key using AES-256-GCM
4. Updates the database with encrypted values
5. Provides a summary of changes

#### Safety Features

- **Idempotent**: Can be run multiple times safely (skips already encrypted keys)
- **Dry Run Mode**: Preview changes before applying
- **Backward Compatible**: The model's property getter handles both encrypted and plaintext values
- **Error Handling**: Logs errors but continues processing other providers

#### After Migration

1. Verify the migration was successful by checking a few providers
2. Update your `.env` file or deployment configuration to include `ENCRYPTION_KEY`
3. Restart your application to use the new encryption system

#### Troubleshooting

**Problem**: "Failed to decrypt API key" errors after migration

**Solution**: Ensure the `ENCRYPTION_KEY` environment variable is set to the same key used during migration.

**Problem**: Migration shows 0 providers encrypted

**Solution**: This is normal if all API keys are already encrypted or all are empty. Use `--verbose` to see details.

**Problem**: Want to roll back the migration

**Solution**: Restore from your database backup. The encryption is one-way without the original key.
