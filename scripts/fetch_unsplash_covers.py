"""Replace category covers with Unsplash photos.

Reads UNSPLASH_ACCESS_KEY from the environment. The key is never written to
the repository. Demo applications are limited to 50 requests per hour: this
script keeps at least 3 of those unused and, when the window is spent, sleeps
until the next hour instead of stopping while a category still needs photos.

Each saved photo triggers its links.download_location endpoint once. Image
bytes then come from the URL that endpoint returns. Progress is cached in
instance/unsplash-covers.json so a restart continues.

Run from the repository root:

    UNSPLASH_ACCESS_KEY=... .venv/bin/python scripts/fetch_unsplash_covers.py
"""
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'app' / 'static' / 'covers'
STAGING = ROOT / 'instance' / 'unsplash-staging'
CACHE = ROOT / 'instance' / 'unsplash-covers.json'
CREDITS_JSON = OUTPUT / 'credits.json'
CREDITS_MD = ROOT / 'docs' / 'image-credits.md'
API = 'https://api.unsplash.com/search/photos'
UTM = {'utm_source': 'joinly_isep', 'utm_medium': 'referral'}
TARGET = 13
MINIMUM = 12
WIDTH, HEIGHT = 1200, 675
MAX_BYTES = 150_000
REMAINING_FLOOR = 3
USER_AGENT = 'JoinlyUnsplash/1.0 (ISEP student project; https://isep.wangjiahan.com)'

QUERIES = {
    'nature': ['forest landscape', 'mountain lake nature'],
    'sport': ['athletics sport outdoor', 'running track stadium'],
    'arts': ['art museum gallery', 'painting studio artist'],
    'jeux': ['friends playing board game', 'people playing cards'],
    'cuisine': ['cooking food kitchen', 'homemade meal table'],
    'musique': ['live music concert', 'musician guitar stage'],
    'photo': ['photographer with camera', 'camera photography'],
    'bienetre': ['wellness spa calm', 'meditation quiet'],
    'langues': ['friends talking cafe', 'language class students'],
    'benevolat': ['volunteers helping community', 'charity volunteers'],
    'football': ['soccer match football', 'football players stadium'],
    'pique-nique': ['picnic blanket park', 'outdoor picnic food'],
    'randonnee': ['hiking trail mountains', 'hiker mountain path'],
    'lecture': ['reading a book', 'library books reading'],
    'jeux-video': ['video game controller', 'friends playing video games'],
    'yoga': ['yoga pose outdoor', 'yoga class studio'],
    'tech': ['laptop on a desk', 'developer computer workspace'],
    'theatre': ['theater stage performance', 'actors on stage'],
}


def log(message):
    print(message, flush=True)


def with_utm(url):
    parts = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    query.update(UTM)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), ''))


def load_state():
    if CACHE.is_file():
        return json.loads(CACHE.read_text(encoding='utf-8'))
    return {'remaining': None, 'window_started': None, 'skipped': [], 'categories': {}}


def save_state(state):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(CACHE)


def sleep_window(state):
    started = state.get('window_started') or time.time()
    deadline = started + 3660
    while True:
        remaining_wait = int(deadline - time.time())
        if remaining_wait <= 0:
            break
        chunk = min(30, remaining_wait)
        log(f'Budget horaire atteint. Prochaine fenêtre dans {remaining_wait} s.')
        save_state(state)
        time.sleep(chunk)
    state['remaining'] = None
    state['window_started'] = None
    save_state(state)


def api_json(state, url):
    key = os.environ.get('UNSPLASH_ACCESS_KEY', '').strip()
    if not key:
        raise SystemExit('UNSPLASH_ACCESS_KEY manquant dans l’environnement.')
    headers = {
        'Authorization': f'Client-ID {key}',
        'Accept-Version': 'v1',
        'Accept': 'application/json',
        'User-Agent': USER_AGENT,
    }
    while True:
        if state.get('remaining') is not None and int(state['remaining']) <= REMAINING_FLOOR:
            sleep_window(state)
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                state['remaining'] = int(response.headers.get('X-Ratelimit-Remaining', '0'))
                if state.get('window_started') is None:
                    state['window_started'] = time.time()
                payload = json.loads(response.read().decode())
                save_state(state)
                log(f'API restante : {state["remaining"]}')
                return payload
        except urllib.error.HTTPError as error:
            if error.code in (403, 429):
                log(f'Unsplash HTTP {error.code}. Fenêtre suivante.')
                state['remaining'] = 0
                if state.get('window_started') is None:
                    state['window_started'] = time.time()
                sleep_window(state)
                continue
            raise


def search(state, phrase, page):
    query = urllib.parse.urlencode({
        'query': phrase,
        'page': page,
        'per_page': 30,
        'orientation': 'landscape',
        'content_filter': 'high',
    })
    payload = api_json(state, f'{API}?{query}')
    return payload.get('results') or []


def candidate(photo, used):
    if not photo or photo.get('id') in used:
        return None
    user = photo.get('user') or {}
    name = (user.get('name') or '').strip()
    links = photo.get('links') or {}
    profile = ((user.get('links') or {}).get('html') or '').strip()
    photo_page = (links.get('html') or '').strip()
    download_at = (links.get('download_location') or '').strip()
    if not (name and profile and photo_page and download_at):
        return None
    if photo.get('width', 0) < 800:
        return None
    return {
        'id': photo['id'],
        'photographer': name[:120],
        'profile_url': with_utm(profile),
        'photo_url': with_utm(photo_page),
        'download_location': download_at,
    }


def encode(data):
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')
    ratio = WIDTH / HEIGHT
    width, height = image.size
    if width / height > ratio:
        kept = int(height * ratio)
        left = (width - kept) // 2
        image = image.crop((left, 0, left + kept, height))
    else:
        kept = int(width / ratio)
        top = max(0, (height - kept) // 2)
        image = image.crop((0, top, width, top + kept))
    for edge in (WIDTH, 1040, 900):
        framed = image.resize((edge, int(edge * HEIGHT / WIDTH)), Image.Resampling.LANCZOS)
        for quality in (74, 62, 50, 38, 28):
            buffer = io.BytesIO()
            framed.save(buffer, 'WEBP', quality=quality, method=6)
            if buffer.tell() <= MAX_BYTES:
                return buffer.getvalue()
    raise RuntimeError('encoded image stays above 150KB')


def download_bytes(url):
    separator = '&' if '?' in url else '?'
    sized = f'{url}{separator}w=1600&h=900&fit=crop&q=70'
    last = None
    for target in (sized, url):
        request = urllib.request.Request(target, headers={'User-Agent': USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            last = error
    raise last


def used_ids(state):
    taken = set(state.get('skipped') or [])
    for block in state['categories'].values():
        taken.update(photo['id'] for photo in block.get('photos', []))
    return taken


def store_photo(state, slug, item):
    tracked = api_json(state, item['download_location'])
    url = tracked.get('url')
    if not url:
        state.setdefault('skipped', []).append(item['id'])
        save_state(state)
        return False
    folder = STAGING / slug
    folder.mkdir(parents=True, exist_ok=True)
    number = len(state['categories'][slug]['photos']) + 1
    filename = f'{number:02d}.webp'
    try:
        payload = encode(download_bytes(url))
    except Exception as error:
        log(f'{slug}: ignore {item["id"]}: {error}')
        state.setdefault('skipped', []).append(item['id'])
        save_state(state)
        return False
    (folder / filename).write_bytes(payload)
    state['categories'][slug]['photos'].append({
        'id': item['id'],
        'saved': filename,
        'photographer': item['photographer'],
        'profile_url': item['profile_url'],
        'photo_url': item['photo_url'],
    })
    save_state(state)
    log(f'{slug} {filename} ({len(payload)} octets) {item["photographer"]}')
    return True


def publish(slug, photos):
    folder = OUTPUT / slug
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob('*.webp'):
        old.unlink()
    for photo in photos:
        source = STAGING / slug / photo['saved']
        (folder / photo['saved']).write_bytes(source.read_bytes())


def write_credits(state):
    document = {}
    lines = [
        '# Crédits des images de couverture',
        '',
        'Les photographies ci-dessous viennent d’Unsplash. Chaque téléchargement',
        'a déclenché une fois `links.download_location`. Les fichiers sont hébergés',
        'dans le dépôt (1200×675 WebP, moins de 150 Ko). Les liens portent',
        '`utm_source=joinly_isep&utm_medium=referral`.',
        '',
        'La clé d’API n’est pas dans le dépôt : `scripts/fetch_unsplash_covers.py`',
        'la lit dans `UNSPLASH_ACCESS_KEY`.',
        '',
        '| Fichier | Catégorie | Photographe | Profil | Photo |',
        '| --- | --- | --- | --- | --- |',
    ]
    for slug in QUERIES:
        block = state['categories'].get(slug) or {}
        if not block.get('published'):
            continue
        for photo in block['photos']:
            path = f'covers/{slug}/{photo["saved"]}'
            document[path] = {
                'photographer': photo['photographer'],
                'profile_url': photo['profile_url'],
                'photo_url': photo['photo_url'],
            }
            lines.append(
                f'| `app/static/{path}` | {slug} | {photo["photographer"].replace("|", "/")} | {photo["profile_url"]} | {photo["photo_url"]} |'
            )
    missing = [slug for slug in QUERIES if not (state['categories'].get(slug) or {}).get('published')]
    if missing:
        lines.extend(['', 'Catégories pas encore remplacées : ' + ', '.join(missing) + '.', ''])
    CREDITS_JSON.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    CREDITS_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def fill(state, slug):
    stored = state['categories'].setdefault(slug, {'photos': [], 'published': False})
    if stored.get('published') and len(stored['photos']) >= MINIMUM:
        if all((OUTPUT / slug / photo['saved']).is_file() for photo in stored['photos']):
            log(f'{slug}: déjà {len(stored["photos"])} photos')
            return
        publish(slug, stored['photos'])
        log(f'{slug}: fichiers réécrits')
        return
    taken = used_ids(state)
    for phrase in QUERIES[slug]:
        if len(stored['photos']) >= TARGET:
            break
        for page in (1, 2):
            if len(stored['photos']) >= TARGET:
                break
            rows = search(state, phrase, page)
            found = [item for item in (candidate(photo, taken) for photo in rows) if item]
            if not found:
                break
            for item in found:
                if len(stored['photos']) >= TARGET:
                    break
                taken.add(item['id'])
                store_photo(state, slug, item)
                taken = used_ids(state)
    if len(stored['photos']) >= MINIMUM:
        publish(slug, stored['photos'])
        stored['published'] = True
        save_state(state)
        write_credits(state)
        log(f'{slug}: publié ({len(stored["photos"])})')
    else:
        log(f'{slug}: seulement {len(stored["photos"])} photos, illustrations conservées')


def main():
    state = load_state()
    for slug in QUERIES:
        fill(state, slug)
    missing = [slug for slug in QUERIES if not (state['categories'].get(slug) or {}).get('published')]
    if missing:
        raise SystemExit('Incomplet : ' + ', '.join(missing))
    write_credits(state)
    log('Bibliothèque Unsplash complète.')


if __name__ == '__main__':
    main()
