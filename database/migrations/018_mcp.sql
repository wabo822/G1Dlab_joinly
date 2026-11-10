BEGIN;
CREATE TABLE mcp_tokens (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 token_hash text NOT NULL UNIQUE,
 credential_hash text NOT NULL,
 label text NOT NULL CHECK (char_length(label) BETWEEN 1 AND 80),
 scopes text[] NOT NULL DEFAULT '{public:read}',
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '30 days',
 revoked_at timestamptz,
 last_used_at timestamptz
);
CREATE INDEX mcp_tokens_user ON mcp_tokens(user_id);
CREATE TABLE assistant_booking_requests (
 id uuid PRIMARY KEY,
 user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 event_id bigint NOT NULL REFERENCES events(id) ON DELETE CASCADE,
 token_id bigint REFERENCES mcp_tokens(id) ON DELETE CASCADE,
 snapshot jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '15 minutes',
 reservation_id bigint REFERENCES reservations(id) ON DELETE CASCADE
);
CREATE INDEX assistant_booking_requests_user ON assistant_booking_requests(user_id, created_at);
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON mcp_tokens,assistant_booking_requests TO joinly_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO joinly_app;
INSERT INTO schema_migrations(version) VALUES ('018_mcp');
COMMIT;
