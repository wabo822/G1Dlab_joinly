\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE tickets (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reservation_id bigint NOT NULL UNIQUE REFERENCES reservations(id) ON DELETE CASCADE,
    token text NOT NULL UNIQUE CHECK (char_length(token) BETWEEN 32 AND 200),
    code text NOT NULL UNIQUE CHECK (code ~ '^JOIN-[A-Z0-9]{4}-[A-Z0-9]{2}$'),
    checked_in_at timestamptz,
    checked_in_by bigint REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tickets_code_idx ON tickets (code);

DO $$
DECLARE
    reservation_row record;
    new_code text;
    new_token text;
    tries integer;
BEGIN
    FOR reservation_row IN
        SELECT id FROM reservations r
        WHERE NOT EXISTS (SELECT 1 FROM tickets t WHERE t.reservation_id = r.id)
    LOOP
        tries := 0;
        LOOP
            tries := tries + 1;
            new_token := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
            new_code := 'JOIN-' || upper(substr(md5(reservation_row.id::text || tries::text || random()::text), 1, 4))
                || '-' || upper(substr(md5(random()::text || reservation_row.id::text || tries::text), 1, 2));
            BEGIN
                INSERT INTO tickets (reservation_id, token, code)
                VALUES (reservation_row.id, new_token, new_code);
                EXIT;
            EXCEPTION WHEN unique_violation THEN
                IF tries > 8 THEN
                    RAISE;
                END IF;
            END;
        END LOOP;
    END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON tickets TO joinly_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO joinly_app;
INSERT INTO schema_migrations (version) VALUES ('012_tickets');
COMMIT;
