"""Stripe Checkout in test mode only.

A secret key that does not start with sk_test_ never reaches Stripe.
Missing keys leave paid booking unavailable; the rest of the app still runs.
"""
import stripe

HOLD_MINUTES = 30
LABELS = {
    'none': '',
    'pending': 'Paiement en attente',
    'paid': 'Payé',
    'refunded': 'Remboursé',
    'cancelled': 'Paiement annulé',
}


def secret_key(app):
    return (app.config.get('STRIPE_SECRET_KEY') or '').strip()


def webhook_secret(app):
    return (app.config.get('STRIPE_WEBHOOK_SECRET') or '').strip()


def block_reason(app):
    """'refused' for a non-test secret, 'missing' when checkout cannot start, else None."""
    secret = secret_key(app)
    if secret and not secret.startswith('sk_test_'):
        return 'refused'
    if not secret.startswith('sk_test_') or not webhook_secret(app):
        return 'missing'
    return None


def ready(app):
    return block_reason(app) is None


def _configure(app):
    if not ready(app):
        raise RuntimeError('paiement indisponible')
    stripe.api_key = secret_key(app)


def create_checkout(app, **kwargs):
    _configure(app)
    return stripe.checkout.Session.create(**kwargs)


def retrieve_checkout(app, session_id):
    _configure(app)
    return stripe.checkout.Session.retrieve(session_id)


def refund(app, payment_intent, amount, idempotency_key):
    _configure(app)
    return stripe.Refund.create(
        payment_intent=payment_intent,
        amount=int(amount),
        idempotency_key=idempotency_key,
    )


def construct_event(app, payload, signature):
    secret = webhook_secret(app)
    if not secret:
        raise stripe.SignatureVerificationError('Webhook secret missing', signature or '')
    return stripe.Webhook.construct_event(payload, signature or '', secret)
