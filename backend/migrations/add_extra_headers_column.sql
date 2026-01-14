-- Add extra_headers column to service_providers table

-- For SQLite
ALTER TABLE service_providers ADD COLUMN extra_headers JSON DEFAULT NULL;

-- For PostgreSQL (uncomment if using PostgreSQL)
-- ALTER TABLE service_providers ADD COLUMN extra_headers JSONB DEFAULT NULL;
