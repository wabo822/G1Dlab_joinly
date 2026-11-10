\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE users ADD COLUMN google_sub text;
ALTER TABLE users ADD CONSTRAINT users_google_sub_check
    CHECK (google_sub IS NULL OR char_length(google_sub) BETWEEN 1 AND 255);
CREATE UNIQUE INDEX users_google_sub_unique ON users (google_sub) WHERE google_sub IS NOT NULL;
INSERT INTO schema_migrations (version) VALUES ('014_google');
COMMIT;
