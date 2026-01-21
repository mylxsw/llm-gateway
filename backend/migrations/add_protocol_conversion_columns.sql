-- Add protocol conversion columns to request_logs table
-- These columns store converted request/response data for debugging and analysis
-- Run this migration if you have an existing database

-- For SQLite
ALTER TABLE request_logs ADD COLUMN request_protocol VARCHAR(50) DEFAULT NULL;
ALTER TABLE request_logs ADD COLUMN supplier_protocol VARCHAR(50) DEFAULT NULL;
ALTER TABLE request_logs ADD COLUMN converted_request_body JSON DEFAULT NULL;
ALTER TABLE request_logs ADD COLUMN upstream_response_body TEXT DEFAULT NULL;

-- For PostgreSQL (uncomment if using PostgreSQL)
-- ALTER TABLE request_logs ADD COLUMN request_protocol VARCHAR(50) DEFAULT NULL;
-- ALTER TABLE request_logs ADD COLUMN supplier_protocol VARCHAR(50) DEFAULT NULL;
-- ALTER TABLE request_logs ADD COLUMN converted_request_body JSONB DEFAULT NULL;
-- ALTER TABLE request_logs ADD COLUMN upstream_response_body TEXT DEFAULT NULL;
