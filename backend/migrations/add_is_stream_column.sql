-- Add is_stream column to request_logs table
-- Run this migration if you have an existing database

-- For SQLite
ALTER TABLE request_logs ADD COLUMN is_stream BOOLEAN NOT NULL DEFAULT 0;

-- For PostgreSQL (uncomment if using PostgreSQL)
-- ALTER TABLE request_logs ADD COLUMN is_stream BOOLEAN NOT NULL DEFAULT FALSE;
