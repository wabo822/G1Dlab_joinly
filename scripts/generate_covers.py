"""Fallback illustrations for the cover library.

The committed files are photographs from Wikimedia Commons, fetched by
`scripts/fetch_covers.py` (Unsplash and Pexels search APIs require a key).
Running this script overwrites those photographs with original drawings.
"""
import colorsys
from pathlib import Path
import random

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'app' / 'static' / 'covers'
COUNT = 13
WIDTH, HEIGHT = 1200, 675

CATEGORIES = {
    'nature': 138,
    'sport': 210,
    'arts': 278,
    'jeux': 28,
    'cuisine': 12,
    'musique': 322,
    'photo': 198,
    'bienetre': 168,
    'langues': 48,
    'benevolat': 92,
    'football': 126,
    'pique-nique': 42,
    'randonnee': 104,
    'lecture': 252,
    'jeux-video': 262,
    'yoga': 160,
    'tech': 222,
    'theatre': 338,
}


def rgb(hue, saturation, value):
    red, green, blue = colorsys.hsv_to_rgb(hue % 360 / 360, saturation, value)
    return tuple(int(channel * 255) for channel in (red, green, blue))


def gradient(hue, shift, vertical):
    small = Image.new('RGB', (2, 256) if vertical else (256, 2))
    pixels = small.load()
    start = rgb(hue + shift, 0.45, 0.95)
    end = rgb(hue + shift + 28, 0.55, 0.55)
    for index in range(256):
        ratio = index / 255
        color = tuple(int(start[channel] * (1 - ratio) + end[channel] * ratio) for channel in range(3))
        if vertical:
            pixels[0, index] = pixels[1, index] = color
        else:
            pixels[index, 0] = pixels[index, 1] = color
    return small.resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC)


def draw_motif(draw, slug, rng, color):
    if slug in ('football', 'sport'):
        draw.ellipse((860, 80, 1120, 340), outline=color, width=14)
        draw.line((990, 80, 990, 340), fill=color, width=8)
        draw.arc((860, 140, 1120, 280), 0, 180, fill=color, width=8)
    elif slug in ('musique', 'theatre'):
        draw.ellipse((900, 180, 980, 260), fill=color)
        draw.rectangle((968, 70, 986, 210), fill=color)
        draw.ellipse((1020, 210, 1100, 290), fill=color)
        draw.rectangle((1088, 90, 1106, 240), fill=color)
    elif slug in ('cuisine', 'pique-nique'):
        draw.ellipse((860, 90, 1140, 370), outline=color, width=16)
        draw.ellipse((940, 170, 1060, 290), fill=color)
    elif slug in ('lecture', 'langues'):
        draw.rounded_rectangle((880, 80, 1120, 360), radius=18, outline=color, width=14)
        draw.line((1000, 80, 1000, 360), fill=color, width=8)
    elif slug in ('photo', 'tech', 'jeux-video'):
        draw.rounded_rectangle((860, 100, 1140, 340), radius=28, outline=color, width=14)
        draw.ellipse((960, 150, 1060, 250), outline=color, width=12)
    elif slug in ('yoga', 'bienetre'):
        draw.arc((860, 40, 1160, 400), 200, 340, fill=color, width=16)
        draw.ellipse((980, 250, 1040, 310), fill=color)
    elif slug in ('randonnee', 'nature'):
        draw.polygon([(860, 360), (960, 140), (1080, 360)], outline=color)
        draw.polygon([(980, 360), (1100, 180), (1160, 360)], outline=color)
    else:
        draw.regular_polygon((1000, 210, 120), 6, rotation=rng.randint(0, 40), outline=color, width=12)


def render(slug, hue, index):
    rng = random.Random(f'{slug}-{index}')
    base = gradient(hue, index * 7, index % 2 == 0).convert('RGBA')
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    accent = rgb(hue + index * 9, 0.35, 1)
    accent_a = accent + (90,)
    strong = accent + (210,)
    for _ in range(6 + index % 4):
        radius = rng.randint(40, 180)
        x = rng.randint(-40, WIDTH)
        y = rng.randint(-40, 520)
        draw.ellipse((x, y, x + radius, y + radius * rng.choice((1, 1, 2))), fill=accent_a)
    if index % 3 == 0:
        draw.polygon([(0, 500), (WIDTH, 360), (WIDTH, HEIGHT), (0, HEIGHT)], fill=(255, 255, 255, 40))
    elif index % 3 == 1:
        for step in range(-200, WIDTH, 70):
            draw.line((step, 0, step + 280, HEIGHT), fill=(255, 255, 255, 35), width=18)
    else:
        draw.rounded_rectangle((70, 70, 430, 250), radius=40, fill=(255, 255, 255, 45))
    draw_motif(draw, slug, rng, strong)
    composed = Image.alpha_composite(base, overlay).convert('RGB')
    return composed


def main():
    credits = [
        '# Crédits des images de couverture',
        '',
        'Les 13 visuels de chacune des 18 catégories sont des **illustrations originales**',
        'générées pour Joinly (`scripts/generate_covers.py`), pas des photographies.',
        'Les API de recherche Unsplash et Pexels ont répondu « authorization required »',
        'sans clé : aucun fichier tiers n’a été téléchargé, pour ne pas inventer d’auteur',
        'ni de licence.',
        '',
        'Licence : œuvre originale du dépôt, utilisable avec le projet (domaine public CC0,',
        'dédiée par les auteurs du dépôt). Aucune source externe.',
        '',
        '| Fichier | Catégorie | Origine | Auteur | Licence |',
        '| --- | --- | --- | --- | --- |',
    ]
    for slug, hue in CATEGORIES.items():
        folder = OUTPUT / slug
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(1, COUNT + 1):
            path = folder / f'{index:02d}.webp'
            render(slug, hue, index).save(path, 'WEBP', quality=78, method=4)
            credits.append(
                f'| `app/static/covers/{slug}/{index:02d}.webp` | {slug} | illustration originale | Joinly | CC0 |'
            )
            print(path.relative_to(ROOT), path.stat().st_size)
    (ROOT / 'docs' / 'image-credits.md').write_text('\n'.join(credits) + '\n', encoding='utf-8')
    print('Wrote docs/image-credits.md')


if __name__ == '__main__':
    main()
