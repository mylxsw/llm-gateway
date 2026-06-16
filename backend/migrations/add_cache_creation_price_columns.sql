-- Add cache_creation_input_price (cache WRITE price) columns to model_mappings
-- and model_mapping_providers. Distinguishes the write-side cache price from
-- the existing cached_input_price (cache READ price).
ALTER TABLE model_mappings ADD COLUMN cache_creation_input_price NUMERIC(12, 4);
ALTER TABLE model_mapping_providers ADD COLUMN cache_creation_input_price NUMERIC(12, 4);
