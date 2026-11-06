\set ON_ERROR_STOP on
BEGIN;
DO $$
DECLARE
    u bigint;
    e bigint;
BEGIN
    INSERT INTO users (email, display_name, password_hash)
        VALUES ('constraint-test@example.invalid', 'Test', 'test-only-not-a-login') RETURNING id INTO u;
    BEGIN
        INSERT INTO users (email, display_name, password_hash)
            VALUES ('constraint-test@example.invalid', 'Duplicate', 'test');
        RAISE EXCEPTION 'Duplicate email was accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO events (organizer_id, title, location, starts_at, ends_at, capacity)
            VALUES (u, 'Invalid', 'Paris', now(), now() + interval '1 hour', 0);
        RAISE EXCEPTION 'Zero capacity was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    INSERT INTO events (organizer_id, title, location, starts_at, ends_at, capacity, status)
        VALUES (u, 'Test', 'Paris', now() + interval '1 day', now() + interval '2 days', 1, 'published') RETURNING id INTO e;
    INSERT INTO reservations (member_id, event_id) VALUES (u, e);
    BEGIN
        INSERT INTO reservations (member_id, event_id) VALUES (u, e);
        RAISE EXCEPTION 'Duplicate active reservation was accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    UPDATE reservations SET status = 'cancelled', cancelled_at = now() WHERE event_id = e;
    INSERT INTO reservations (member_id, event_id) VALUES (u, e);
    BEGIN
        DELETE FROM events WHERE id = e;
        RAISE EXCEPTION 'Event with reservation history was deleted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
END;
$$;
ROLLBACK;
