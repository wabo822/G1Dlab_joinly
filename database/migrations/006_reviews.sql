\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE reviews (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id bigint NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    author_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment text NOT NULL CHECK (char_length(btrim(comment)) BETWEEN 1 AND 2000),
    hidden boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, author_id)
);
CREATE INDEX reviews_event_visible_idx ON reviews (event_id) WHERE NOT hidden;
CREATE TRIGGER reviews_updated BEFORE UPDATE ON reviews FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON reviews TO joinly_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO joinly_app;
INSERT INTO schema_migrations (version) VALUES ('006_reviews');
COMMIT;
