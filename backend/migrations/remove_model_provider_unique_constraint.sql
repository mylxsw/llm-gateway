-- Remove unique constraint on (requested_model, provider_id)

-- PostgreSQL
-- ALTER TABLE model_mapping_providers DROP CONSTRAINT IF EXISTS uq_model_provider;

-- SQLite (rebuild table without the unique constraint)
PRAGMA foreign_keys=off;

CREATE TABLE model_mapping_providers_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_model VARCHAR(100) NOT NULL,
    provider_id INTEGER NOT NULL,
    target_model_name VARCHAR(100) NOT NULL,
    provider_rules JSON,
    input_price NUMERIC(12, 4),
    output_price NUMERIC(12, 4),
    billing_mode VARCHAR(50),
    per_request_price NUMERIC(12, 4),
    tiered_pricing JSON,
    priority INTEGER DEFAULT 0,
    weight INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY(requested_model) REFERENCES model_mappings(requested_model) ON DELETE CASCADE,
    FOREIGN KEY(provider_id) REFERENCES service_providers(id) ON DELETE CASCADE
);

INSERT INTO model_mapping_providers_new (
    id,
    requested_model,
    provider_id,
    target_model_name,
    provider_rules,
    input_price,
    output_price,
    billing_mode,
    per_request_price,
    tiered_pricing,
    priority,
    weight,
    is_active,
    created_at,
    updated_at
)
SELECT
    id,
    requested_model,
    provider_id,
    target_model_name,
    provider_rules,
    input_price,
    output_price,
    billing_mode,
    per_request_price,
    tiered_pricing,
    priority,
    weight,
    is_active,
    created_at,
    updated_at
FROM model_mapping_providers;

DROP TABLE model_mapping_providers;
ALTER TABLE model_mapping_providers_new RENAME TO model_mapping_providers;

PRAGMA foreign_keys=on;
