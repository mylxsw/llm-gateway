CREATE INDEX IF NOT EXISTS idx_model_mappings_alias_target
    ON model_mappings (alias_target_model);

CREATE TRIGGER IF NOT EXISTS trg_model_alias_validate_insert
BEFORE INSERT ON model_mappings
WHEN NEW.model_type = 'alias'
BEGIN
    SELECT CASE WHEN NEW.alias_target_model IS NULL
        OR NEW.alias_target_model = NEW.requested_model OR NOT EXISTS (
        SELECT 1 FROM model_mappings AS target
        WHERE target.requested_model = NEW.alias_target_model
          AND (target.model_type IS NULL OR target.model_type <> 'alias')
    ) THEN RAISE(ABORT, 'invalid_alias_target') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_model_alias_validate_update
BEFORE UPDATE OF model_type, alias_target_model ON model_mappings
WHEN NEW.model_type = 'alias'
BEGIN
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM model_mappings AS alias
        WHERE alias.model_type = 'alias'
          AND alias.alias_target_model = OLD.requested_model
    ) THEN RAISE(ABORT, 'model_referenced_by_alias') END;
    SELECT CASE WHEN NEW.alias_target_model IS NULL
        OR NEW.alias_target_model = NEW.requested_model OR NOT EXISTS (
        SELECT 1 FROM model_mappings AS target
        WHERE target.requested_model = NEW.alias_target_model
          AND (target.model_type IS NULL OR target.model_type <> 'alias')
    ) THEN RAISE(ABORT, 'invalid_alias_target') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_model_alias_restrict_delete
BEFORE DELETE ON model_mappings
WHEN EXISTS (
    SELECT 1 FROM model_mappings AS alias
    WHERE alias.model_type = 'alias'
      AND alias.alias_target_model = OLD.requested_model
)
BEGIN
    SELECT RAISE(ABORT, 'model_referenced_by_alias');
END;
