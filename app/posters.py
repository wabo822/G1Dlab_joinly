"""Share poster. French text uses Source Sans 3 (SIL Open Font License)."""
import io
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_M

from app.lifecycle import PARIS

ROOT = Path(__file__).resolve().parents[1]
FONT_REGULAR = ROOT / 'app' / 'fonts' / 'SourceSans3-Regular.ttf'
FONT_BOLD = ROOT / 'app' / 'fonts' / 'SourceSans3-Bold.ttf'
MONTHS = ('janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.')


def _font(path, size):
    if path.is_file():
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _wrap(draw, text, font, width):
    words = (text or '').split()
    if not words:
        return []
    lines, current = [], words[0]
    for word in words[1:]:
        trial = f'{current} {word}'
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:5]


def _price(cents):
    cents = int(cents or 0)
    if cents <= 0:
        return 'Gratuit'
    euros, centimes = divmod(cents, 100)
    return f'{euros},{centimes:02d} €' if centimes else f'{euros} €'


def render_poster(event, qr_target, cover_file=None):
    width, height = 1080, 1350
    image = Image.new('RGB', (width, height), '#111738')
    draw = ImageDraw.Draw(image)
    for y in range(480):
        ratio = y / 480
        draw.line([(0, y), (width, y)], fill=(
            int(17 + (109 - 17) * ratio),
            int(23 + (69 - 23) * ratio),
            int(56 + (232 - 56) * ratio),
        ))
    if cover_file and Path(cover_file).is_file():
        try:
            cover = Image.open(cover_file).convert('RGB')
            cover = cover.resize((1000, 460))
            image.paste(cover, (40, 40))
        except Exception:
            pass
    bold = _font(FONT_BOLD, 58)
    regular = _font(FONT_REGULAR, 32)
    y = 540
    local = event['starts_at'].astimezone(PARIS) if event.get('starts_at') else None
    when = f'{local.day} {MONTHS[local.month - 1]} {local.year} · {local.strftime("%H:%M")}' if local else ''
    for line in _wrap(draw, event.get('title') or 'Activité', bold, 980):
        draw.text((48, y), line, font=bold, fill='white')
        y += 70
    for line in (when, event.get('location') or '', _price(event.get('price_cents'))):
        if line:
            draw.text((48, y), line[:90], font=regular, fill='#d9e2ff')
            y += 46
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=6, border=1)
    qr.add_data(qr_target)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color='#111738', back_color='white').convert('RGB').resize((220, 220))
    image.paste(qr_image, (width - 280, height - 300))
    draw.text((48, height - 220), 'Joinly', font=bold, fill='white')
    draw.text((48, height - 140), 'Réservez votre place', font=regular, fill='#c9d4f5')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()
