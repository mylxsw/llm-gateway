-- Add cache billing columns to model_mappings
ALTER TABLE model_mappings ADD COLUMN cache_billing_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE model_mappings ADD COLUMN cached_input_price NUMERIC(12, 4);
ALTER TABLE model_mappings ADD COLUMN cached_output_price NUMERIC(12, 4);

-- Add cache billing columns to model_mapping_providers
ALTER TABLE model_mapping_providers ADD COLUMN cache_billing_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE model_mapping_providers ADD COLUMN cached_input_price NUMERIC(12, 4);
ALTER TABLE model_mapping_providers ADD COLUMN cached_output_price NUMERIC(12, 4);

-- Add cached cost columns to request_logs
ALTER TABLE request_logs ADD COLUMN cached_input_cost NUMERIC(12, 4);
ALTER TABLE request_logs ADD COLUMN cached_output_cost NUMERIC(12, 4);
