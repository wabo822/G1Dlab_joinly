"""In-app notifications and optional SMTP mail.

Delivery failures are logged and never raised to the caller. Without SMTP_HOST
and MAIL_FROM, the message is logged and stored in dev_outbox.
"""
import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from zoneinfo import ZoneInfo

EMAIL_KINDS = {'booking_confirmed', 'event_changed', 'event_cancelled', 'reminder'}
PARIS = ZoneInfo('Europe/Paris')
MONTHS = ('janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.')


def deliver(app, query, recipient, subject, plain, html_body=None, inline_images=None):
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
        if html_body:
            message.add_alternative(html_body, subtype='html')
            if inline_images:
                html_part = message.get_payload()[-1]
                for cid, filename, data, subtype in inline_images:
                    html_part.add_related(
                        data, maintype='image', subtype=subtype, cid=cid, filename=filename,
                    )
        with smtplib.SMTP(host, int(os.environ.get('SMTP_PORT', '587')), timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if os.environ.get('SMTP_USER'):
                smtp.login(os.environ['SMTP_USER'], os.environ.get('SMTP_PASSWORD', ''))
            smtp.send_message(message)
        return True
    except Exception:
        app.logger.exception('Email delivery failed')
        return False


def notify(app, query, user_id, kind, title, body, link=None, dedupe_key=None, email=None,
           html_body=None, inline_images=None):
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
            deliver(app, query, email, title, body, html_body, inline_images)
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


def branded_html(title, paragraphs, code=None, extra_html=''):
    blocks = ''.join(f'<p style="margin:0 0 12px;line-height:1.5">{html.escape(p)}</p>' for p in paragraphs)
    code_html = ''
    if code:
        code_html = (
            '<p style="font-size:32px;letter-spacing:8px;font-weight:700;text-align:center;'
            f'background:#f4f5fa;border-radius:12px;padding:16px">{html.escape(code)}</p>'
        )
    return (
        '<!doctype html><html lang="fr"><body style="margin:0;background:#f4f5fa;font-family:Arial,sans-serif;color:#111738">'
        '<div style="max-width:560px;margin:24px auto;background:#fff;border-radius:18px;overflow:hidden">'
        '<div style="background:#111738;color:#fff;padding:22px 28px;font-weight:700">Joinly</div>'
        f'<div style="padding:28px"><h1 style="font-size:22px;margin:0 0 16px">{html.escape(title)}</h1>'
        f'{blocks}{code_html}{extra_html}'
        '<p style="color:#505873;font-size:13px">Projet étudiant Joinly · ISEP · G1D Lab.</p></div></div></body></html>'
    )


def format_when(value):
    if value is None:
        return ''
    local = value.astimezone(PARIS) if getattr(value, 'tzinfo', None) else value
    day = local.day
    month = MONTHS[local.month - 1]
    return f'{day} {month} {local.year} à {local.strftime("%H:%M")}'


def format_price(cents):
    cents = int(cents or 0)
    if cents <= 0:
        return 'Gratuit'
    return f'{cents // 100},{cents % 100:02d} €'


def booking_email(event, ticket, base_url):
    """Plain + HTML confirmation with an inline QR (CID) and a ticket link."""
    from app.tickets import payload_for, qr_png

    base = (base_url or '').rstrip('/')
    ticket_url = f'{base}/billets/{ticket["token"]}' if base else f'/billets/{ticket["token"]}'
    when = format_when(event.get('starts_at'))
    place = event.get('location') or ''
    title = event.get('title') or 'Activité'
    price = format_price(event.get('price_cents'))
    code = ticket['code']
    paid_note = (
        'Paiement simulé — projet étudiant : aucun montant n’a été débité.'
        if int(event.get('price_cents') or 0) > 0 else ''
    )
    plain_parts = [
        f'Votre inscription à « {title} » est confirmée.',
        f'Date : {when}' if when else '',
        f'Lieu : {place}' if place else '',
        f'Tarif : {price}',
        f'Billet {code}',
        f'Présentez ce code ou le QR à l’entrée. Voir le billet : {ticket_url}',
        paid_note,
    ]
    plain = '\n'.join(part for part in plain_parts if part)
    rows = [
        ('Activité', title),
        ('Date', when),
        ('Lieu', place),
        ('Tarif', price),
        ('Billet', code),
    ]
    table = (
        '<table style="width:100%;border-collapse:collapse;margin:0 0 20px">'
        + ''.join(
            '<tr>'
            f'<td style="padding:8px 0;color:#505873;width:120px;vertical-align:top">{html.escape(label)}</td>'
            f'<td style="padding:8px 0;font-weight:700">{html.escape(value)}</td>'
            '</tr>'
            for label, value in rows if value
        )
        + '</table>'
    )
    extra = (
        table
        + (f'<p style="margin:0 0 16px;color:#505873">{html.escape(paid_note)}</p>' if paid_note else '')
        + '<p style="text-align:center;margin:8px 0 4px"><img src="cid:ticket-qr" alt="QR du billet" width="220" height="220" style="display:block;margin:0 auto"></p>'
        + '<p style="text-align:center;color:#505873;font-size:13px;margin:0 0 20px">Présentez ce QR code à l’entrée.</p>'
        + '<p style="text-align:center;margin:0 0 8px">'
        f'<a href="{html.escape(ticket_url, quote=True)}" style="display:inline-block;background:#2066fa;color:#fff;text-decoration:none;padding:12px 22px;border-radius:999px;font-weight:700">Voir mon billet</a>'
        '</p>'
    )
    html_body = branded_html('Place confirmée', ['Votre inscription est confirmée. Conservez ce message ou ouvrez votre billet pour le contrôle à l’entrée.'], extra_html=extra)
    images = [('ticket-qr', 'billet-qr.png', qr_png(payload_for(ticket['token'], base)), 'png')]
    return plain, html_body, images


def start_verification(app, query, user_id, email):
    import hashlib
    import hmac
    import secrets
    from datetime import datetime, timedelta, timezone
    row = query('SELECT last_sent_at FROM email_verifications WHERE user_id=%s', (user_id,), True)
    if row and datetime.now(timezone.utc) - row['last_sent_at'] < timedelta(seconds=60):
        raise ValueError('Attendez 60 secondes avant de renvoyer le code.')
    code = f'{secrets.randbelow(1_000_000):06d}'
    digest = hmac.new(app.config['SECRET_KEY'].encode(), code.encode(), hashlib.sha256).hexdigest()
    query(
        '''INSERT INTO email_verifications(user_id, code_hash, expires_at, attempts, last_sent_at)
           VALUES (%s, %s, now() + interval '15 minutes', 0, now())
           ON CONFLICT (user_id) DO UPDATE SET code_hash=EXCLUDED.code_hash,
             expires_at=EXCLUDED.expires_at, attempts=0, last_sent_at=now()''',
        (user_id, digest),
    )
    if not (os.environ.get('SMTP_HOST') and os.environ.get('MAIL_FROM')):
        app.logger.warning('Verification code for %s: %s', email, code)
    plain = f'Votre code Joinly est {code}. Il expire dans 15 minutes.'
    deliver(
        app, query, email, 'Confirmez votre adresse Joinly', plain,
        branded_html('Confirmez votre adresse', ['Saisissez ce code sur Joinly. Il expire dans 15 minutes.'], code),
    )


def check_verification(app, query, user_id, code):
    import hashlib
    import hmac
    from datetime import datetime, timezone
    row = query('SELECT * FROM email_verifications WHERE user_id=%s', (user_id,), True)
    if not row or row['expires_at'] <= datetime.now(timezone.utc):
        raise ValueError('Ce code a expiré. Demandez un nouvel envoi.')
    if row['attempts'] >= 5:
        raise ValueError('Trop de tentatives. Demandez un nouveau code.')
    digest = hmac.new(app.config['SECRET_KEY'].encode(), code.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(row['code_hash'], digest):
        updated = query(
            '''UPDATE email_verifications SET attempts = attempts + 1
               WHERE user_id=%s AND attempts < 5 RETURNING attempts''',
            (user_id,), True,
        )
        if not updated:
            raise ValueError('Trop de tentatives. Demandez un nouveau code.')
        raise ValueError('Code incorrect.')
    query('UPDATE users SET email_verified_at=now() WHERE id=%s', (user_id,))
    query('DELETE FROM email_verifications WHERE user_id=%s', (user_id,))
