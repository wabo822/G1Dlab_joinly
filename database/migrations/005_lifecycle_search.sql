\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE events ADD COLUMN city text NOT NULL DEFAULT '';
ALTER TABLE events ADD CONSTRAINT events_city_check CHECK (char_length(city) <= 80);
INSERT INTO schema_migrations (version) VALUES ('005_lifecycle_search');
COMMIT;
