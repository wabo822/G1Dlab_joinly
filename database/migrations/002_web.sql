\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE web_sessions (
 token_hash text PRIMARY KEY,
 user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX web_sessions_user_idx ON web_sessions(user_id);
CREATE TABLE contact_requests (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL,
 email text NOT NULL,
 subject text NOT NULL,
 message text NOT NULL,
 resolved boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE rate_limits (
 key text PRIMARY KEY,
 attempts integer NOT NULL,
 expires_at timestamptz NOT NULL
);
CREATE TABLE password_resets (
 token_hash text PRIMARY KEY,
 user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL
);
GRANT SELECT, INSERT, UPDATE, DELETE ON web_sessions, contact_requests, rate_limits, password_resets TO joinly_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO joinly_app;
INSERT INTO schema_migrations(version) VALUES ('002_web');
COMMIT;
