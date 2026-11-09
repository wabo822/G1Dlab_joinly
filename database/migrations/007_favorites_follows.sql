\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE favorites (
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_id bigint NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_id)
);
CREATE INDEX favorites_event_idx ON favorites (event_id);
CREATE TABLE organizer_follows (
    follower_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organizer_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (follower_id, organizer_id),
    CHECK (follower_id <> organizer_id)
);
CREATE INDEX organizer_follows_organizer_idx ON organizer_follows (organizer_id);
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON favorites, organizer_follows TO joinly_app;
INSERT INTO schema_migrations (version) VALUES ('007_favorites_follows');
COMMIT;
