"""In-app notifications and optional SMTP mail.

Delivery failures are logged and never raised to the caller. Without SMTP_HOST
and MAIL_FROM, the message is logged and stored in dev_outbox.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

EMAIL_KINDS = {'booking_confirmed', 'event_changed', 'event_cancelled', 'reminder'}


def deliver(app, query, recipient, subject, plain):
    try:
        host = os.environ.get('SMTP_HOST', '').strip()
        sender = os.environ.get('MAIL_FROM', '').strip()
        if not host or not sender:
            app.logger.warning('SMTP not configured. To %s | %s | %s', recipient, subject, plain)
            query(
                'INSERT INTO dev_outbox(recipient, subject, body) VALUES (%s, %s, %s)',
                (recipient, subject, plain),
            )
            return False
        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = sender
        message['To'] = recipient
        message.set_content(plain)
        with smtplib.SMTP(host, int(os.environ.get('SMTP_PORT', '587')), timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if os.environ.get('SMTP_USER'):
                smtp.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASSWORD', ''))
            smtp.send_message(message)
        return True
    except Exception:
        app.logger.exception('Email delivery failed')
        return False


def notify(app, query, user_id, kind, title, body, link=None, dedupe_key=None, email=None):
    try:
        if dedupe_key:
            created = query(
                '''INSERT INTO notifications(user_id, kind, title, body, link, dedupe_key)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id, dedupe_key) DO NOTHING RETURNING id''',
                (user_id, kind, title, body[:2000], link, dedupe_key),
                True,
            )
        else:
            created = query(
                '''INSERT INTO notifications(user_id, kind, title, body, link)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id''',
                (user_id, kind, title, body[:2000], link),
                True,
            )
        if created and email and kind in EMAIL_KINDS:
            deliver(app, query, email, title, body)
        return bool(created)
    except Exception:
        app.logger.exception('Notification failed')
        return False


def send_reminders(app, query, db):
    payloads = []
    with db().transaction():
        rows = query(
            '''SELECT r.id AS reservation_id, r.member_id, u.email, e.id AS event_id, e.title, e.location
               FROM reservations r
               JOIN events e ON e.id = r.event_id
               JOIN users u ON u.id = r.member_id
               WHERE r.status = 'confirmed' AND r.reminder_sent_at IS NULL
                 AND e.status = 'published'
                 AND e.starts_at > now() AND e.starts_at <= now() + interval '24 hours'
               FOR UPDATE OF r SKIP LOCKED'''
        )
        for row in rows:
            marked = query(
                '''UPDATE reservations SET reminder_sent_at = clock_timestamp()
                   WHERE id = %s AND reminder_sent_at IS NULL RETURNING id''',
                (row['reservation_id'],),
                True,
            )
            if not marked:
                continue
            query(
                '''INSERT INTO notifications(user_id, kind, title, body, link, dedupe_key)
                   VALUES (%s, 'reminder', %s, %s, '/notifications', %s)
                   ON CONFLICT (user_id, dedupe_key) DO NOTHING''',
                (
                    row['member_id'],
                    'Rappel : c’est bientôt',
                    f'« {row["title"]} » commence dans moins de 24 h. {row["location"]}',
                    f'reminder:{row["reservation_id"]}',
                ),
            )
            payloads.append(row)
    for row in payloads:
        deliver(
            app, query, row['email'], 'Rappel Joinly — dans moins de 24 h',
            f'« {row["title"]} » commence dans moins de 24 h.\n{row["location"]}',
        )
    return len(payloads)
