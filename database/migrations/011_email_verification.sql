\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE users ADD COLUMN email_verified_at timestamptz;
UPDATE users SET email_verified_at = COALESCE(created_at, now()) WHERE email_verified_at IS NULL;
CREATE TABLE email_verifications (
    user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    code_hash text NOT NULL,
    expires_at timestamptz NOT NULL,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0 AND attempts <= 20),
    last_sent_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON email_verifications TO joinly_app;
INSERT INTO schema_migrations (version) VALUES ('011_email_verification');
COMMIT;
