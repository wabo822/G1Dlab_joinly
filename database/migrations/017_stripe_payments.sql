\set ON_ERROR_STOP on
BEGIN;
-- Price stays in events.price_cents (euro cents). Currency is EUR only.
ALTER TABLE events ADD COLUMN currency text NOT NULL DEFAULT 'EUR';
ALTER TABLE events DROP CONSTRAINT IF EXISTS events_currency_check;
ALTER TABLE events ADD CONSTRAINT events_currency_check CHECK (currency = 'EUR');

-- Allow a short unpaid hold in addition to confirmed and cancelled.
DO $$
DECLARE
    constraint_name text;
BEGIN
    FOR constraint_name IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'reservations'::regclass AND contype = 'c'
          AND pg_get_constraintdef(oid) ILIKE '%status%'
          AND pg_get_constraintdef(oid) NOT ILIKE '%refund%'
          AND pg_get_constraintdef(oid) NOT ILIKE '%payment_status%'
    LOOP
        EXECUTE format('ALTER TABLE reservations DROP CONSTRAINT %I', constraint_name);
    END LOOP;
END $$;

ALTER TABLE reservations ADD CONSTRAINT reservations_status_check
    CHECK (status IN ('pending', 'confirmed', 'cancelled'));
ALTER TABLE reservations ADD CONSTRAINT reservations_status_pair_check CHECK (
    (status IN ('pending', 'confirmed') AND cancelled_at IS NULL)
    OR (status = 'cancelled' AND cancelled_at IS NOT NULL AND cancelled_at >= reserved_at)
);

DROP INDEX IF EXISTS reservations_active_unique;
CREATE UNIQUE INDEX reservations_active_unique
    ON reservations (member_id, event_id)
    WHERE status IN ('pending', 'confirmed');

ALTER TABLE reservations ADD COLUMN payment_status text NOT NULL DEFAULT 'none';
ALTER TABLE reservations ADD CONSTRAINT reservations_payment_status_check
    CHECK (payment_status IN ('none', 'pending', 'paid', 'refunded', 'cancelled'));
ALTER TABLE reservations ADD COLUMN stripe_checkout_session_id text;
ALTER TABLE reservations ADD COLUMN stripe_payment_intent_id text;
ALTER TABLE reservations ADD COLUMN amount_cents integer;
ALTER TABLE reservations ADD CONSTRAINT reservations_amount_cents_check
    CHECK (amount_cents IS NULL OR (amount_cents >= 0 AND amount_cents <= 500000));
ALTER TABLE reservations ADD COLUMN hold_expires_at timestamptz;

CREATE UNIQUE INDEX reservations_checkout_session_unique
    ON reservations (stripe_checkout_session_id)
    WHERE stripe_checkout_session_id IS NOT NULL;

ALTER TABLE reservations DROP CONSTRAINT IF EXISTS reservations_refund_status_check;
ALTER TABLE reservations ADD CONSTRAINT reservations_refund_status_check
    CHECK (refund_status IN ('none', 'simulated', 'manual', 'stripe'));

INSERT INTO schema_migrations (version) VALUES ('017_stripe_payments');
COMMIT;
