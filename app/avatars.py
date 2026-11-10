"""Profile avatars: square WebP uploads and initials fallback."""
import io
import re
import secrets
from pathlib import Path

from PIL import Image

AVATAR_RE = re.compile(r'^a[0-9]+-[a-f0-9]{16}\.webp$')
MAX_BYTES = 2 * 1024 * 1024
SIZE = 256
COLORS = (
    '#2066fa', '#7046e8', '#c44b7a', '#c56a1a', '#1f7a4d',
    '#1954ca', '#8a4b12', '#3b4a8a', '#0e7c7b', '#9b2d4a',
)


def avatar_dir(app):
    path = Path(app.config['UPLOAD_DIR']).resolve() / 'avatars'
    path.mkdir(parents=True, exist_ok=True)
    return path


def initials(name):
    parts = [part for part in re.split(r'\s+', (name or '').strip()) if part]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def color(user_id):
    return COLORS[int(user_id or 0) % len(COLORS)]


def sniff_image(data):
    if data[:3] == b'\xff\xd8\xff':
        return True
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return True
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return True
    return False


def save_avatar(app, user_id, storage, previous=None):
    data = storage.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('L’image dépasse 2 Mo.')
    if len(data) < 12 or not sniff_image(data):
        raise ValueError('Format accepté : JPEG, PNG ou WebP.')
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        image = image.convert('RGB')
    except Exception as error:
        raise ValueError('Fichier image illisible.') from error
    if image.width > 8000 or image.height > 8000:
        raise ValueError('Image trop grande.')
    side = min(image.width, image.height)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    name = f'a{int(user_id)}-{secrets.token_hex(8)}.webp'
    directory = avatar_dir(app)
    destination = directory / name
    image.save(destination, 'WEBP', quality=82)
    delete_avatar(app, previous)
    return name


def delete_avatar(app, name):
    if not name or not AVATAR_RE.fullmatch(str(name)):
        return
    directory = avatar_dir(app)
    path = (directory / name).resolve()
    if path.parent == directory and path.is_file():
        path.unlink()
