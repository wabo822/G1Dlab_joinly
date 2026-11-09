\set ON_ERROR_STOP on
BEGIN;
DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'legal_pages'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%kind%';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE legal_pages DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;
ALTER TABLE legal_pages ADD CONSTRAINT legal_pages_kind_check
    CHECK (kind IN ('terms', 'legal_notice', 'privacy'));
INSERT INTO schema_migrations(version) VALUES ('003_privacy');
COMMIT;
