"""Download a resumable cover library: 13 photos per category.

Unsplash and Pexels search APIs answer 401 without a key in this environment,
so this script uses the Wikimedia Commons API (real photographs, author and
license included). It stays under 40 API calls per rolling hour — margin under
the 50/hour cap — and sleeps until the next window instead of stopping while
any category still has fewer than 13 photos.

Progress and credits are cached in instance/cover-fetch.json. A restart
continues from the files already saved.

Run from the repository root: .venv/bin/python scripts/fetch_covers.py
"""
import html
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'app' / 'static' / 'covers'
CACHE = ROOT / 'instance' / 'cover-fetch.json'
CREDITS = ROOT / 'docs' / 'image-credits.md'
API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = 'JoinlyCoverFetch/1.0 (ISEP student project; https://isep.wangjiahan.com; noreply@wangjiahan.com)'
TARGET = 13
WIDTH, HEIGHT = 1200, 675
MAX_BYTES = 150_000
HOURLY_BUDGET = 40
WINDOW_SECONDS = 3600
PER_SEARCH = 40

QUERIES = {
    'nature': ['nature landscape forest photograph', 'forêt paysage nature'],
    'sport': ['outdoor sport athletics photograph', 'sport stade athlète'],
    'arts': ['art museum painting gallery photograph', 'musée tableau exposition'],
    'jeux': [
        'people playing cards photograph',
        'chess players photograph',
        'board game table friends photograph',
        'jeu de société joueurs',
    ],
    'cuisine': ['cooking food kitchen meal photograph', 'cuisine plat repas'],
    'musique': ['live music concert instrument photograph', 'concert musique instrument'],
    'photo': ['camera photographer photography photograph', 'appareil photo photographe'],
    'bienetre': ['wellness spa relaxation photograph', 'bien-être détente'],
    'langues': [
        'friends conversation cafe photograph',
        'conversation langues café',
        'language class classroom students photograph',
        'people talking coffee terrace photograph',
        'discussion group workshop photograph',
    ],
    'benevolat': ['volunteers community helping photograph', 'bénévolat volontaires', 'charity volunteers food bank photograph'],
    'football': ['football soccer match stadium photograph', 'match de football'],
    'pique-nique': ['picnic blanket park food photograph', 'pique-nique parc', 'outdoor picnic basket photograph'],
    'randonnee': ['hiking trail mountain photograph', 'randonnée sentier montagne'],
    'lecture': ['reading book library photograph', 'lecture bibliothèque livre'],
    'jeux-video': [
        'nintendo playstation xbox controller photograph',
        'arcade video game photograph',
        'person playing video game controller',
    ],
    'yoga': ['yoga pose outdoor photograph', 'yoga posture', 'yoga class studio photograph'],
    'tech': [
        'laptop computer desk photograph',
        'software developer computer photograph',
        'ordinateur portable bureau',
    ],
    'theatre': ['theater stage performance photograph', 'théâtre scène spectacle', 'theatre actors curtain photograph'],
}


def log(message):
    print(message, flush=True)


def plain(value):
    text = re.sub(r'<[^>]+>', ' ', value or '')
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def license_ok(name):
    label = (name or '').strip()
    upper = label.upper()
    if any(token in upper for token in ('NC', 'ND', 'NONCOMMERCIAL', 'NO DERIV')):
        return False
    return upper.startswith(('CC0', 'CC BY', 'PUBLIC DOMAIN')) or upper in {'PDM', 'CC PDM'}


def load_state():
    if CACHE.is_file():
        return json.loads(CACHE.read_text())
    return {'source': 'wikimedia-commons', 'api_calls': [], 'categories': {}}


def save_state(state):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    temporary.replace(CACHE)


def request(url, timeout=60):
    call = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(call, timeout=timeout) as response:
        return response.read(), response.headers


def api_call(state, params):
    now = time.time()
    state['api_calls'] = [stamp for stamp in state['api_calls'] if now - stamp < WINDOW_SECONDS]
    if len(state['api_calls']) >= HOURLY_BUDGET:
        wait = WINDOW_SECONDS - (now - state['api_calls'][0]) + 5
        log(f'Budget horaire atteint ({HOURLY_BUDGET}). Attente de {int(wait)} s avant la fenêtre suivante.')
        save_state(state)
        time.sleep(wait)
        return api_call(state, params)
    query = urllib.parse.urlencode(params)
    try:
        body, headers = request(f'{API}?{query}')
    except urllib.error.HTTPError as error:
        if error.code == 429:
            wait = int(error.headers.get('Retry-After') or WINDOW_SECONDS)
            log(f'Wikimedia 429. Attente de {wait} s.')
            save_state(state)
            time.sleep(wait)
            return api_call(state, params)
        raise
    state['api_calls'].append(time.time())
    save_state(state)
    remaining = headers.get('X-RateLimit-Remaining')
    if remaining:
        log(f'API remaining header: {remaining}')
    return json.loads(body.decode())


def search(state, phrase, offset=0):
    payload = api_call(state, {
        'action': 'query',
        'format': 'json',
        'generator': 'search',
        'gsrsearch': f'{phrase} filetype:bitmap',
        'gsrnamespace': '6',
        'gsrlimit': str(PER_SEARCH),
        'gsroffset': str(offset),
        'prop': 'imageinfo',
        'iiprop': 'url|mime|size|extmetadata',
        'iiurlwidth': '1600',
    })
    pages = (payload.get('query') or {}).get('pages') or {}
    rows = sorted(pages.values(), key=lambda page: page.get('index', 0))
    continue_at = ((payload.get('continue') or {}).get('gsroffset'))
    return rows, continue_at


def candidate(page, used_ids):
    if page.get('pageid') in used_ids:
        return None
    title = page.get('title') or ''
    lowered = title.lower()
    if any(word in lowered for word in (
        'logo', 'icon', 'map', 'diagram', 'flag', 'coat of arms', 'scan', 'svg',
        'lenormand', 'cartomancie', 'estampe', 'tarot', 'guantanamo', 'captive', 'detainee',
    )):
        return None
    info = (page.get('imageinfo') or [None])[0] or {}
    if info.get('mime') not in ('image/jpeg', 'image/png', 'image/webp'):
        return None
    thumb = info.get('thumburl')
    if not thumb or info.get('thumbwidth', 0) < 800:
        return None
    meta = info.get('extmetadata') or {}
    license_name = plain((meta.get('LicenseShortName') or {}).get('value'))
    if not license_ok(license_name):
        return None
    author = plain((meta.get('Artist') or {}).get('value'))[:180]
    lowered_author = author.lower()
    if not author or 'unknown' in lowered_author or '[null' in lowered_author or 'anonymous' in lowered_author:
        return None
    landscape = 0 if info.get('thumbwidth', 0) >= info.get('thumbheight', 1) else 1
    return {
        'pageid': page['pageid'],
        'title': title,
        'author': author,
        'license': license_name,
        'license_url': plain((meta.get('LicenseUrl') or {}).get('value')),
        'source_url': info.get('descriptionurl') or '',
        'file_url': thumb,
        'landscape': landscape,
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


def download(url):
    last_error = None
    for attempt in range(3):
        try:
            body, _headers = request(url, timeout=90)
            return body
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
            time.sleep(2 + attempt * 3)
    raise last_error


def collect(state, slug):
    stored = state['categories'].setdefault(slug, {'photos': []})
    used = {photo['pageid'] for photo in stored['photos']}
    used |= {
        photo['pageid']
        for other, block in state['categories'].items()
        if other != slug
        for photo in block.get('photos', [])
    }
    folder = OUTPUT / slug
    folder.mkdir(parents=True, exist_ok=True)
    for phrase in QUERIES[slug]:
        offset = 0
        while len(stored['photos']) < TARGET:
            rows, next_offset = search(state, phrase, offset)
            found = [item for item in (candidate(page, used) for page in rows) if item]
            found.sort(key=lambda item: item['landscape'])
            for item in found:
                if len(stored['photos']) >= TARGET:
                    break
                number = len(stored['photos']) + 1
                filename = f'{number:02d}.webp'
                destination = folder / filename
                try:
                    payload = encode(download(item['file_url']))
                except Exception as error:
                    log(f'{slug}: ignore {item["title"]}: {error}')
                    used.add(item['pageid'])
                    continue
                destination.write_bytes(payload)
                item['saved'] = filename
                item.pop('landscape', None)
                stored['photos'].append(item)
                used.add(item['pageid'])
                save_state(state)
                log(f'{slug} {filename} ({len(payload)} bytes) {item["author"]}')
                time.sleep(0.4)
            if len(stored['photos']) >= TARGET or not next_offset or not rows:
                break
            next_offset = int(next_offset)
            if next_offset <= offset:
                break
            offset = next_offset
        if len(stored['photos']) >= TARGET:
            break
    if len(stored['photos']) < TARGET:
        log(f'{slug} still short: {len(stored["photos"])}/{TARGET}')


def short_author(author):
    author = author.split(" I'd ")[0].split(' if you ')[0]
    return author[:120].strip(' .')


def write_credits(state):
    lines = [
        '# Crédits des images de couverture',
        '',
        'Chaque catégorie a 13 photographies distinctes, recadrées en 1200×675 WebP',
        '(moins de 150 Ko). Les API de recherche Unsplash et Pexels répondent',
        '« authorization required » sans clé dans cet environnement : les fichiers',
        'viennent de Wikimedia Commons, avec l’URL source, l’auteur et la licence',
        'renvoyés par l’API. Le script `scripts/fetch_covers.py` reprend là où il',
        's’est arrêté grâce à `instance/cover-fetch.json`.',
        '',
        '| Fichier | Catégorie | Source | Auteur | Licence |',
        '| --- | --- | --- | --- | --- |',
    ]
    for slug, block in state['categories'].items():
        for photo in block['photos']:
            source = photo['source_url'].replace('|', '%7C')
            author = short_author(photo['author']).replace('|', '/')
            lines.append(
                f'| `app/static/covers/{slug}/{photo["saved"]}` | {slug} | {source} | {author} | {photo["license"]} |'
            )
    lines.append('')
    CREDITS.write_text('\n'.join(lines))


def main():
    state = load_state()
    for slug in QUERIES:
        done = len(state.get('categories', {}).get(slug, {}).get('photos', []))
        if done >= TARGET and all((OUTPUT / slug / f'{index:02d}.webp').is_file() for index in range(1, TARGET + 1)):
            log(f'{slug}: déjà {done} photos')
            continue
        log(f'{slug}: reprise à {done}')
        collect(state, slug)
    missing = [slug for slug in QUERIES if len(state['categories'].get(slug, {}).get('photos', [])) < TARGET]
    if missing:
        raise SystemExit('Catégories incomplètes : ' + ', '.join(missing))
    write_credits(state)
    log('Bibliothèque complète.')


if __name__ == '__main__':
    main()
