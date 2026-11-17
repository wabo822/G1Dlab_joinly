"""Stripe test-mode checkout. The Stripe API is mocked; signature checks use the library."""
import hashlib
import hmac
import json
import time

import psycopg
import pytest
import stripe
from psycopg.rows import dict_row

from app import create_app
from tests.test_app import CONFIRM, event, login, user

SECRET = 'sk_test_joinly'
WEBHOOK = 'whsec_test_joinly'
CHECKOUT = 'https://checkout.stripe.com/c/pay/cs_test_joinly'


class FakeSession:
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 'cs_test_joinly')
        self.url = kwargs.get('url', CHECKOUT)
        self.status = kwargs.get('status', 'open')
        self.payment_intent = kwargs.get('payment_intent', 'pi_test_joinly')


@pytest.fixture()
def app():
    application = create_app({
        'TESTING': True, 'DATABASE': 'joinly_test', 'SECRET_KEY': 'test-secret-not-for-deployment',
        'WTF_CSRF_ENABLED': False, 'STRIPE_SECRET_KEY': '', 'STRIPE_PUBLISHABLE_KEY': '',
        'STRIPE_WEBHOOK_SECRET': '',
    })
    with psycopg.connect(dbname='joinly_test', autocommit=True) as connection:
        connection.execute(
            'TRUNCATE users,events,categories,faqs,legal_pages,contact_requests,rate_limits,user_interests,dev_outbox CASCADE'
        )
    return application


@pytest.fixture()
def db(app):
    with psycopg.connect(dbname='joinly_test', row_factory=dict_row, autocommit=True) as connection:
        yield connection


def enable(app, secret=SECRET):
    app.config['STRIPE_SECRET_KEY'] = secret
    app.config['STRIPE_PUBLISHABLE_KEY'] = 'pk_test_joinly'
    app.config['STRIPE_WEBHOOK_SECRET'] = WEBHOOK


def sign(payload, secret=WEBHOOK):
    stamp = int(time.time())
    digest = hmac.new(secret.encode(), f'{stamp}.{payload}'.encode(), hashlib.sha256).hexdigest()
    return f't={stamp},v1={digest}'


def completed_event(reservation_id, amount=1250, session_id='cs_test_joinly'):
    return json.dumps({
        'id': 'evt_test_joinly',
        'object': 'event',
        'type': 'checkout.session.completed',
        'data': {'object': {
            'id': session_id,
            'object': 'checkout.session',
            'payment_status': 'paid',
            'payment_intent': 'pi_test_joinly',
            'client_reference_id': str(reservation_id),
            'amount_total': amount,
            'currency': 'eur',
            'metadata': {'reservation_id': str(reservation_id)},
        }},
    })


def post_webhook(client, payload, header):
    return client.post(
        '/stripe/webhook',
        data=payload,
        headers={'Stripe-Signature': header, 'Content-Type': 'application/json'},
    )


def test_free_booking_never_calls_stripe(app, db, monkeypatch):
    def boom(**kwargs):
        raise AssertionError('stripe called')

    monkeypatch.setattr(stripe.checkout.Session, 'create', boom)
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    user(db, 'guest@example.test')
    eid = event(db, owner, 3)
    client = login(app, 'guest@example.test')
    assert client.post(f'/activities/{eid}/reserve', data=CONFIRM).status_code == 302
    row = db.execute(
        "SELECT status, payment_status FROM reservations WHERE event_id=%s", (eid,),
    ).fetchone()
    assert row['status'] == 'confirmed' and row['payment_status'] == 'none'
    assert db.execute('SELECT count(*) AS n FROM tickets').fetchone()['n'] == 1


def test_paid_checkout_webhook_refund_and_guards(app, db, monkeypatch):
    created = []
    refunds = []

    def fake_create(**kwargs):
        created.append(kwargs)
        number = len(created)
        session_id = 'cs_test_joinly' if number == 1 else f'cs_test_joinly_{number}'
        url = CHECKOUT if number == 1 else f'{CHECKOUT}/{number}'
        return FakeSession(id=session_id, url=url)

    def fake_retrieve(session_id):
        return FakeSession(id=session_id)

    def fake_refund(**kwargs):
        refunds.append(kwargs)
        return {'id': 're_test_joinly'}

    monkeypatch.setattr(stripe.checkout.Session, 'create', fake_create)
    monkeypatch.setattr(stripe.checkout.Session, 'retrieve', fake_retrieve)
    monkeypatch.setattr(stripe.Refund, 'create', fake_refund)

    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    guest = user(db, 'payer@example.test')
    user(db, 'boss@example.test', ('member', 'admin'), interests=False)
    eid = event(db, owner, 2)
    db.execute(
        "UPDATE events SET title='Atelier payant', price_cents=1250, cancellation_policy='flexible', "
        "starts_at=now()+interval '3 days', ends_at=now()+interval '3 days 2 hours' WHERE id=%s",
        (eid,),
    )
    client = login(app, 'payer@example.test')

    # Live keys are refused before any Stripe call.
    enable(app, 'sk_live_forbidden')
    refused = client.get(f'/activities/{eid}/reserver')
    assert 'Seul le mode test Stripe est autorisé' in refused.text
    assert 'js.stripe.com' not in refused.headers['Content-Security-Policy']
    denied = client.post(f'/activities/{eid}/reserve', data=CONFIRM)
    assert denied.status_code == 400 and 'Paiement indisponible.' in denied.text
    assert created == []
    assert db.execute('SELECT count(*) AS n FROM reservations').fetchone()['n'] == 0

    enable(app)
    recap = client.get(f'/activities/{eid}/reserver')
    assert 'Mode test — aucun paiement réel' in recap.text
    assert 'J’ai vérifié ces informations' in recap.text
    assert 'name="card"' not in recap.text
    started = client.post(f'/activities/{eid}/reserve', data=CONFIRM)
    assert started.status_code == 302
    assert started.headers['Location'] == CHECKOUT
    assert created[0]['line_items'][0]['price_data']['currency'] == 'eur'
    assert created[0]['line_items'][0]['price_data']['unit_amount'] == 1250
    assert created[0]['success_url'].endswith('/paiement/succes?session_id={CHECKOUT_SESSION_ID}')
    hold = db.execute(
        '''SELECT id, status, payment_status, amount_cents, stripe_checkout_session_id, hold_expires_at
           FROM reservations WHERE event_id=%s''',
        (eid,),
    ).fetchone()
    assert hold['status'] == 'pending' and hold['payment_status'] == 'pending'
    assert hold['amount_cents'] == 1250 and hold['stripe_checkout_session_id'] == 'cs_test_joinly'
    assert hold['hold_expires_at'] is not None
    assert db.execute('SELECT count(*) AS n FROM tickets').fetchone()['n'] == 0

    again = client.post(f'/activities/{eid}/reserve', data=CONFIRM)
    assert again.status_code == 302 and again.headers['Location'] == CHECKOUT
    assert len(created) == 1
    assert db.execute('SELECT count(*) AS n FROM reservations WHERE event_id=%s', (eid,)).fetchone()['n'] == 1

    waiting = client.get('/paiement/succes?session_id=cs_test_joinly')
    assert 'Paiement en cours de vérification' in waiting.text
    assert 'Mode test — aucun paiement réel' in waiting.text
    assert db.execute("SELECT status FROM reservations WHERE id=%s", (hold['id'],)).fetchone()['status'] == 'pending'

    payload = completed_event(hold['id'])
    assert post_webhook(client, payload, 't=1,v1=deadbeef').status_code == 400
    assert db.execute("SELECT status FROM reservations WHERE id=%s", (hold['id'],)).fetchone()['status'] == 'pending'

    signed = post_webhook(client, payload, sign(payload))
    assert signed.status_code == 200
    paid = db.execute(
        '''SELECT r.status, r.payment_status, r.stripe_payment_intent_id, t.token
           FROM reservations r JOIN tickets t ON t.reservation_id=r.id WHERE r.id=%s''',
        (hold['id'],),
    ).fetchone()
    assert paid['status'] == 'confirmed' and paid['payment_status'] == 'paid'
    assert paid['stripe_payment_intent_id'] == 'pi_test_joinly'
    mail = db.execute(
        "SELECT subject, body FROM dev_outbox WHERE recipient='payer@example.test' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert mail['subject'] == 'Place confirmée'
    assert 'Mode test — aucun paiement réel' in mail['body']
    assert f"/billets/{paid['token']}" in mail['body']
    emails = db.execute(
        "SELECT count(*) AS n FROM dev_outbox WHERE recipient='payer@example.test'"
    ).fetchone()['n']

    app.config['WTF_CSRF_ENABLED'] = True
    assert post_webhook(client, payload, sign(payload)).status_code == 200
    app.config['WTF_CSRF_ENABLED'] = False
    assert db.execute('SELECT count(*) AS n FROM tickets WHERE reservation_id=%s', (hold['id'],)).fetchone()['n'] == 1
    assert db.execute(
        "SELECT count(*) AS n FROM dev_outbox WHERE recipient='payer@example.test'"
    ).fetchone()['n'] == emails

    ready = client.get('/paiement/succes?session_id=cs_test_joinly')
    assert 'Votre place est confirmée' in ready.text
    assert paid['token'] in ready.text

    organizer = login(app, 'owner@example.test')
    board = organizer.get('/organizer')
    assert 'Revenu encaissé' in board.text and '12,50 €' in board.text and 'Payé' in board.text
    office = login(app, 'boss@example.test').get('/admin')
    assert 'Revenu encaissé' in office.text and '12,50 €' in office.text
    listing = login(app, 'boss@example.test').get('/admin/reservations')
    assert 'Payé' in listing.text and '12,50 €' in listing.text

    assert client.post(f"/reservations/{hold['id']}/cancel").status_code == 302
    assert refunds and refunds[0]['payment_intent'] == 'pi_test_joinly' and refunds[0]['amount'] == 1250
    stored = db.execute(
        'SELECT status, payment_status, refund_status, refund_cents FROM reservations WHERE id=%s',
        (hold['id'],),
    ).fetchone()
    assert stored['status'] == 'cancelled' and stored['payment_status'] == 'refunded'
    assert stored['refund_status'] == 'stripe' and stored['refund_cents'] == 1250
    assert 'Remboursement de test' in db.execute(
        "SELECT body FROM dev_outbox WHERE recipient='payer@example.test' ORDER BY id DESC LIMIT 1"
    ).fetchone()['body']

    # A second paid seat expires when the hold passes, and the cancel return releases a new hold.
    other = event(db, owner, 1)
    db.execute("UPDATE events SET price_cents=800, title='Court' WHERE id=%s", (other,))
    fresh = client.post(f'/activities/{other}/reserve', data=CONFIRM)
    assert fresh.status_code == 302
    user(db, 'late@example.test')
    assert login(app, 'late@example.test').post(f'/activities/{other}/reserve', data=CONFIRM).status_code == 400
    pending = db.execute("SELECT id FROM reservations WHERE event_id=%s AND status='pending'", (other,)).fetchone()
    db.execute("UPDATE reservations SET hold_expires_at=now()-interval '1 minute' WHERE id=%s", (pending['id'],))
    assert client.get('/activities').status_code == 200
    released = db.execute('SELECT status, payment_status FROM reservations WHERE id=%s', (pending['id'],)).fetchone()
    assert released['status'] == 'cancelled' and released['payment_status'] == 'cancelled'

    assert client.post(f'/activities/{other}/reserve', data=CONFIRM).status_code == 302
    current = db.execute(
        "SELECT stripe_checkout_session_id FROM reservations WHERE event_id=%s AND status='pending'",
        (other,),
    ).fetchone()
    cancelled = client.get(f"/paiement/annule?session_id={current['stripe_checkout_session_id']}")
    assert cancelled.status_code == 200 and 'Paiement annulé' in cancelled.text
    assert 'Mode test — aucun paiement réel' in cancelled.text
    assert db.execute(
        "SELECT status FROM reservations WHERE stripe_checkout_session_id=%s",
        (current['stripe_checkout_session_id'],),
    ).fetchone()['status'] == 'cancelled'
    assert guest
