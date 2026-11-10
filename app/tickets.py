"""Unguessable ticket tokens and short human codes."""
import io
import secrets

import qrcode
from qrcode.constants import ERROR_CORRECT_M

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def make_code():
    chars = ''.join(secrets.choice(ALPHABET) for _ in range(6))
    return f'JOIN-{chars[:4]}-{chars[4:]}'


def issue_ticket(conn, reservation_id):
    existing = conn.execute(
        'SELECT id, token, code, reservation_id, checked_in_at FROM tickets WHERE reservation_id=%s',
        (reservation_id,),
    ).fetchone()
    if existing:
        return existing
    token = secrets.token_urlsafe(32)
    code = make_code()
    return conn.execute(
        '''INSERT INTO tickets(reservation_id, token, code)
           VALUES (%s, %s, %s)
           RETURNING id, token, code, reservation_id, checked_in_at''',
        (reservation_id, token, code),
    ).fetchone()


def qr_png(payload):
    image = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=8, border=2)
    image.add_data(payload)
    image.make(fit=True)
    rendered = image.make_image(fill_color='#111738', back_color='white').convert('RGB')
    buffer = io.BytesIO()
    rendered.save(buffer, format='PNG')
    return buffer.getvalue()


def payload_for(token, base_url):
    base = (base_url or '').rstrip('/')
    if base:
        return f'{base}/controle?ticket={token}'
    return token
