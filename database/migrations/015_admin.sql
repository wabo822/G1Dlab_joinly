\set ON_ERROR_STOP on
BEGIN;
DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name FROM pg_constraint
    WHERE conrelid = 'users'::regclass AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%status%';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE users DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;
ALTER TABLE users ADD CONSTRAINT users_status_check
    CHECK (status IN ('active', 'suspended', 'banned'));
ALTER TABLE events ADD COLUMN pinned boolean NOT NULL DEFAULT false;

CREATE TABLE site_settings (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    site_name text NOT NULL DEFAULT 'Joinly',
    banner text NOT NULL DEFAULT '',
    booking_cutoff_minutes integer NOT NULL DEFAULT 0 CHECK (booking_cutoff_minutes BETWEEN 0 AND 10080),
    default_cancellation_policy text NOT NULL DEFAULT 'flexible'
        CHECK (default_cancellation_policy IN ('flexible', 'moderate', 'strict')),
    heat_recent_weight integer NOT NULL DEFAULT 10 CHECK (heat_recent_weight BETWEEN 0 AND 1000),
    heat_fill_weight integer NOT NULL DEFAULT 1 CHECK (heat_fill_weight BETWEEN 0 AND 1000),
    heat_view_cap integer NOT NULL DEFAULT 400 CHECK (heat_view_cap BETWEEN 0 AND 100000),
    updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO site_settings (id) VALUES (1);

CREATE TABLE audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint REFERENCES users(id) ON DELETE SET NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id text,
    detail text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_created_idx ON audit_log (created_at DESC);

CREATE TABLE organizer_requests (
    user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    message text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'refused')),
    created_at timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON site_settings, audit_log, organizer_requests TO joinly_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO joinly_app;

DO $$
DECLARE
    constraint_name text;
BEGIN
    SELECT conname INTO constraint_name FROM pg_constraint
    WHERE conrelid = 'notifications'::regclass AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%kind%';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE notifications DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;
ALTER TABLE notifications ADD CONSTRAINT notifications_kind_check CHECK (kind IN (
    'booking_confirmed', 'event_changed', 'event_cancelled', 'reminder',
    'new_activity', 'new_review', 'broadcast', 'organizer_request'
));

INSERT INTO schema_migrations (version) VALUES ('015_admin');
COMMIT;
