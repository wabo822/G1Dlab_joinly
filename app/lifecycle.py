"""Computed activity lifecycle. Nothing here is stored or advanced by a cron job."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo('Europe/Paris')
POLICIES = ('flexible', 'moderate', 'strict')
POLICY_LABELS = {
    'flexible': 'Flexible : annulation gratuite jusqu’à 24 h avant le début. Ensuite, le remboursement simulé est de 0 €.',
    'moderate': 'Modérée : remboursement simulé intégral jusqu’à 72 h avant le début, sinon 50 %.',
    'strict': 'Stricte : aucun remboursement simulé.',
}


def event_end(event):
    """Instant at which the activity is finished, in absolute time.

    `ends_at` is required by the schema and entered in Europe/Paris. If a row
    ever had no end, the fallback is the end of the start day in Europe/Paris
    (23:59:59), not a background job.
    """
    ends = event.get('ends_at') if event else None
    if ends is not None:
        return ends
    start = event.get('starts_at') if event else None
    if start is None:
        return None
    local = start.astimezone(PARIS)
    return datetime(local.year, local.month, local.day, 23, 59, 59, tzinfo=PARIS)


def is_finished(event, now=None):
    now = now or datetime.now(timezone.utc)
    end = event_end(event)
    return bool(end and end <= now)


def booking_block(event, now=None, cutoff_minutes=0, available=None):
    """Return a reason code when booking must be refused, otherwise None."""
    now = now or datetime.now(timezone.utc)
    if event.get('status') == 'cancelled':
        return 'cancelled'
    if event.get('status') != 'published':
        return 'unpublished'
    if is_finished(event, now):
        return 'finished'
    cutoff = max(0, int(cutoff_minutes or 0))
    if now >= event['starts_at'] - timedelta(minutes=cutoff):
        return 'cutoff'
    if available is not None and available <= 0:
        return 'full'
    return None


def phase_label(event, now=None, cutoff_minutes=0):
    now = now or datetime.now(timezone.utc)
    if event.get('status') == 'cancelled':
        return 'Annulée'
    if event.get('status') == 'draft':
        return 'Brouillon'
    if is_finished(event, now):
        return 'Terminé'
    cutoff = max(0, int(cutoff_minutes or 0))
    if now >= event['starts_at'] - timedelta(minutes=cutoff):
        return 'Inscriptions closes'
    return 'À venir'


def refund_cents(event, now=None):
    """Simulated refund for an attendee cancellation. 0 after the start."""
    price = int(event.get('price_cents') or 0)
    if price <= 0:
        return 0
    now = now or datetime.now(timezone.utc)
    if event['starts_at'] <= now:
        return 0
    hours = (event['starts_at'] - now).total_seconds() / 3600
    policy = event.get('cancellation_policy') or 'flexible'
    if policy == 'strict':
        return 0
    if policy == 'moderate':
        return price if hours >= 72 else price // 2
    if hours >= 24:
        return price
    return 0
