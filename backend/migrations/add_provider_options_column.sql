-- Add provider_options column to service_providers table

-- For SQLite
ALTER TABLE service_providers ADD COLUMN provider_options JSON DEFAULT NULL;

-- For PostgreSQL (uncomment if using PostgreSQL)
-- ALTER TABLE service_providers ADD COLUMN provider_options JSONB DEFAULT NULL;
