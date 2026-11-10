\set ON_ERROR_STOP on
BEGIN;
ALTER TABLE events ADD COLUMN cancellation_policy text NOT NULL DEFAULT 'flexible';
ALTER TABLE events ADD CONSTRAINT events_cancellation_policy_check
    CHECK (cancellation_policy IN ('flexible', 'moderate', 'strict'));
ALTER TABLE reservations ADD COLUMN refund_cents integer NOT NULL DEFAULT 0;
ALTER TABLE reservations ADD CONSTRAINT reservations_refund_cents_check
    CHECK (refund_cents >= 0 AND refund_cents <= 500000);
ALTER TABLE reservations ADD COLUMN refund_status text NOT NULL DEFAULT 'none';
ALTER TABLE reservations ADD CONSTRAINT reservations_refund_status_check
    CHECK (refund_status IN ('none', 'simulated', 'manual'));
ALTER TABLE reservations ADD COLUMN refunded_at timestamptz;
ALTER TABLE reservations ADD CONSTRAINT reservations_refund_pair_check CHECK (
    (refund_status = 'none' AND refunded_at IS NULL AND refund_cents = 0)
    OR (refund_status <> 'none' AND refunded_at IS NOT NULL)
);
INSERT INTO schema_migrations (version) VALUES ('013_cancellation_refunds');
COMMIT;
