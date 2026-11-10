\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE events ADD COLUMN cover_image text;
ALTER TABLE events ADD CONSTRAINT events_cover_image_check CHECK (
    cover_image IS NULL
    OR cover_image ~ '^covers/[a-z0-9-]+/[0-9]{2}\.webp$'
    OR cover_image ~ '^e[0-9]+-[a-f0-9]{16}\.webp$'
);
INSERT INTO schema_migrations (version) VALUES ('008_covers');
COMMIT;
