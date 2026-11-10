"""Booking rules shared by the website and confirmed assistant requests."""
from werkzeug.exceptions import NotFound
from app.lifecycle import booking_block
from app.tickets import issue_ticket

BLOCK_MESSAGES = {
 'finished': 'Cette activité est terminée.', 'cutoff': 'Les inscriptions sont closes.',
 'full': 'Cette activité n’a plus de place disponible ou les inscriptions sont fermées.',
 'cancelled': 'Cette activité est annulée.',
 'unpublished': 'Cette activité n’a plus de place disponible ou les inscriptions sont fermées.',
}


def snapshot(event):
    return {key: str(event[key]) for key in
            ('title', 'starts_at', 'ends_at', 'location', 'price_cents', 'cancellation_policy')}


def create_booking(conn, user_id, event_id, cutoff, paid, expected=None, idempotent=False):
    """Caller owns the transaction. Lock the event before checking or inserting."""
    event = conn.execute('SELECT * FROM events WHERE id=%s FOR UPDATE', (event_id,)).fetchone()
    if not event:
        raise NotFound()
    if expected is not None and snapshot(event) != expected:
        raise ValueError('Les informations ont changé. Demandez une nouvelle proposition à l’assistant.')
    if idempotent:
        old = conn.execute("SELECT id FROM reservations WHERE event_id=%s AND member_id=%s AND status='confirmed'",
                           (event_id, user_id)).fetchone()
        if old:
            return event, issue_ticket(conn, old['id']), False
    count = conn.execute("SELECT count(*) AS n FROM reservations WHERE event_id=%s AND status='confirmed'",
                         (event_id,)).fetchone()['n']
    reason = booking_block(event, cutoff_minutes=cutoff, available=event['capacity'] - count)
    if reason:
        raise ValueError(BLOCK_MESSAGES[reason])
    if event['price_cents'] > 0 and not paid:
        raise ValueError('Cette activité est payante : confirmez le paiement simulé avant de réserver.')
    booking = conn.execute('INSERT INTO reservations(member_id,event_id) VALUES (%s,%s) RETURNING id',
                           (user_id, event_id)).fetchone()
    return event, issue_ticket(conn, booking['id']), True
