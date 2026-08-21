CREATE INDEX IF NOT EXISTS idx_model_mappings_alias_target
    ON model_mappings (alias_target_model);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_model_mappings_alias_target'
    ) THEN
        ALTER TABLE model_mappings
        ADD CONSTRAINT fk_model_mappings_alias_target
        FOREIGN KEY (alias_target_model)
        REFERENCES model_mappings(requested_model)
        ON DELETE RESTRICT;
    END IF;
END $$;

CREATE OR REPLACE FUNCTION enforce_model_alias_integrity()
RETURNS trigger AS $$
DECLARE
    target_type VARCHAR(50);
    target_found BOOLEAN := FALSE;
BEGIN
    IF NEW.model_type = 'alias' THEN
        IF TG_OP = 'UPDATE' AND EXISTS (
            SELECT 1 FROM model_mappings AS alias
            WHERE alias.model_type = 'alias'
              AND alias.alias_target_model = OLD.requested_model
        ) THEN
            RAISE EXCEPTION 'model_referenced_by_alias';
        END IF;
        SELECT TRUE, model_type INTO target_found, target_type
        FROM model_mappings
        WHERE requested_model = NEW.alias_target_model
        FOR KEY SHARE;
        IF NOT target_found OR target_type = 'alias' THEN
            RAISE EXCEPTION 'invalid_alias_target';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_model_alias_integrity ON model_mappings;
CREATE TRIGGER trg_model_alias_integrity
BEFORE INSERT OR UPDATE OF model_type, alias_target_model
ON model_mappings
FOR EACH ROW EXECUTE FUNCTION enforce_model_alias_integrity();
