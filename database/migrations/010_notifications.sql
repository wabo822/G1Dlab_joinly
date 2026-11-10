\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE notifications (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind text NOT NULL CHECK (kind IN (
        'booking_confirmed', 'event_changed', 'event_cancelled',
        'reminder', 'new_activity', 'new_review'
    )),
    title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 180),
    body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
    link text CHECK (link IS NULL OR char_length(link) <= 300),
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    dedupe_key text,
    UNIQUE (user_id, dedupe_key)
);
CREATE INDEX notifications_user_idx ON notifications (user_id, created_at DESC);
ALTER TABLE reservations ADD COLUMN reminder_sent_at timestamptz;
CREATE TABLE dev_outbox (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipient text NOT NULL,
    subject text NOT NULL,
    body text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON notifications, dev_outbox TO joinly_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO joinly_app;
INSERT INTO schema_migrations (version) VALUES ('010_notifications');
COMMIT;
