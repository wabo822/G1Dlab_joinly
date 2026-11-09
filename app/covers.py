"""Category cover library and deterministic assignment.

Custom uploads are stored on the event. When `cover_image` is empty, the
picture is chosen from the activity's category library with a stable hash of
the activity id. A category change therefore follows the new library. In a
listing, a one-step shift avoids showing the same library file on two
neighboring cards when another file exists.
"""
import hashlib
import io
import re
import secrets
from pathlib import Path

from PIL import Image
from flask import url_for

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'app' / 'static' / 'covers'
SLUGS = {
    'Nature & plein air': 'nature',
    'Sport': 'sport',
    'Arts & culture': 'arts',
    'Jeux & rencontres': 'jeux',
    'Cuisine': 'cuisine',
    'Musique': 'musique',
    'Photo & vidéo': 'photo',
    'Bien-être': 'bienetre',
    'Langues & échanges': 'langues',
    'Bénévolat': 'benevolat',
    'Football': 'football',
    'Pique-nique': 'pique-nique',
    'Randonnée': 'randonnee',
    'Lecture': 'lecture',
    'Jeux vidéo': 'jeux-video',
    'Yoga': 'yoga',
    'Tech': 'tech',
    'Théâtre': 'theatre',
}
LIBRARY_RE = re.compile(r'^covers/[a-z0-9-]+/[0-9]{2}\.webp$')
UPLOAD_RE = re.compile(r'^e[0-9]+-[a-f0-9]{16}\.webp$')


def category_slug(name):
    return SLUGS.get(name or '', '')


def library_files(category_name):
    slug = category_slug(category_name)
    folder = LIBRARY / slug
    if not folder.is_dir():
        return []
    return sorted(path.name for path in folder.glob('*.webp'))


def auto_cover_index(event_id, count):
    if count <= 0:
        raise ValueError('empty library')
    digest = hashlib.sha256(str(int(event_id)).encode()).digest()
    return int.from_bytes(digest[:8], 'big') % count


def pick_auto(event_id, files, shift=0):
    if not files:
        return None
    index = (auto_cover_index(event_id, len(files)) + shift) % len(files)
    return files[index]


def pick_list(entries):
    """entries: (event_id, files, custom_or_none). Returns chosen filenames or custom values."""
    previous = None
    chosen = []
    for event_id, files, custom in entries:
        if custom:
            chosen.append(custom)
            previous = custom
            continue
        path = pick_auto(event_id, files, 0)
        if path and path == previous and files and len(files) > 1:
            path = pick_auto(event_id, files, 1)
        chosen.append(path)
        previous = path
    return chosen


def auto_cover_static(event_id, category_name, shift=0):
    slug = category_slug(category_name)
    files = library_files(category_name)
    name = pick_auto(event_id, files, shift)
    if not slug or not name:
        return None
    return f'covers/{slug}/{name}'


def is_library_path(value):
    if not value or not LIBRARY_RE.fullmatch(value):
        return False
    full = (ROOT / 'app' / 'static' / value).resolve()
    root = LIBRARY.resolve()
    return full.is_file() and root in full.parents


def sniff_image(data):
    if data.startswith(b'\xff\xd8\xff'):
        return True
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
    return len(data) >= 12 and data.startswith(b'RIFF') and data[8:12] == b'WEBP'


def upload_dir(app):
    return Path(app.config['UPLOAD_DIR']).resolve()


def delete_upload(app, name):
    if not name or not UPLOAD_RE.fullmatch(str(name)):
        return
    directory = upload_dir(app)
    path = (directory / name).resolve()
    if path.parent == directory and path.is_file():
        path.unlink()


def save_upload(app, event_id, storage, previous=None):
    data = storage.read(int(app.config['COVER_MAX_BYTES']) + 1)
    if len(data) > int(app.config['COVER_MAX_BYTES']):
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
    image.thumbnail((1200, 675))
    name = f'e{int(event_id)}-{secrets.token_hex(8)}.webp'
    directory = upload_dir(app)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / name
    image.save(destination, 'WEBP', quality=80)
    if previous and previous != name:
        delete_upload(app, previous)
    return name


def href_for(event, static_path):
    if not static_path:
        return None
    if str(static_path).startswith('covers/'):
        return url_for('static', filename=static_path)
    return url_for('media', filename=static_path)


def decorate(events):
    """Set cover_href and cover_static on each event dict. Neighbor shift is list-local."""
    previous = None
    for event in events:
        custom = event.get('cover_image')
        if custom:
            event['cover_static'] = custom if str(custom).startswith('covers/') else None
            event['cover_href'] = href_for(event, custom)
            previous = custom
            continue
        files = library_files(event.get('category'))
        name = pick_auto(event.get('id'), files, 0)
        slug = category_slug(event.get('category'))
        path = f'covers/{slug}/{name}' if slug and name else None
        if path and path == previous and len(files) > 1:
            name = pick_auto(event.get('id'), files, 1)
            path = f'covers/{slug}/{name}'
        event['cover_static'] = path
        event['cover_href'] = href_for(event, path) if path else None
        previous = path
    return events


def library_tree():
    groups = []
    for name, slug in SLUGS.items():
        files = library_files(name)
        groups.append({
            'name': name,
            'slug': slug,
            'files': [{'name': filename, 'path': f'covers/{slug}/{filename}'} for filename in files],
        })
    return groups
