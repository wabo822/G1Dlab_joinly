\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE events ADD COLUMN latitude numeric(9, 6);
ALTER TABLE events ADD COLUMN longitude numeric(9, 6);
ALTER TABLE events ADD CONSTRAINT events_coordinates_check CHECK (
    (latitude IS NULL AND longitude IS NULL)
    OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
);
INSERT INTO schema_migrations (version) VALUES ('009_coordinates');
COMMIT;
