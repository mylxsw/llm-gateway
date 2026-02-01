-- Migration: Create key_value_store table
-- Description: Add KV store table with expiration support

CREATE TABLE IF NOT EXISTS key_value_store (
    key VARCHAR(255) PRIMARY KEY NOT NULL,
    value TEXT NOT NULL,
    expires_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kv_expires_at ON key_value_store(expires_at);
