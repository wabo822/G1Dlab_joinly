import hashlib
import os
import re
import secrets
import smtplib
import ssl
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from urllib.parse import urlencode
from xml.sax.saxutils import escape as xml_escape
from zoneinfo import ZoneInfo

import click
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from flask import Flask, abort, current_app, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from flask_wtf.csrf import CSRFProtect, CSRFError
from markupsafe import Markup, escape as html_escape
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from app.legal_content import LEGAL_TEXTS
from app.lifecycle import POLICY_LABELS, booking_block, is_finished, refund_cents
from app import avatars, covers, notify
from app.charts import line_chart
from app import dashboards
from app.posters import render_poster
from app.tickets import issue_ticket, payload_for, qr_png

PARIS = ZoneInfo('Europe/Paris')
ROOT = Path(__file__).resolve().parents[1]
DUMMY_HASH = generate_password_hash('not-a-user-password')
MONTHS_FR = ('janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.')
LEGAL_TITLES = {
    'terms': 'Conditions d’utilisation',
    'legal_notice': 'Mentions légales',
    'privacy': 'Politique de confidentialité',
}
PUBLIC_PATHS = ('/', '/activities', '/classement', '/faq', '/contact', '/legal/terms', '/legal/legal_notice', '/legal/privacy')
MIN_INTERESTS = 3
INTEREST_FREE = {'mcp_endpoint', 'mcp_settings', 'assistant_chat', 'static', 'interests', 'logout', 'legal', 'privacy_redirect', 'robots', 'sitemap', 'favicon', 'health', 'media', 'media_avatar', 'poster', 'stop_impersonation', 'public_ticket', 'public_ticket_qr'}


def _env_cutoff():
    try:
        return max(0, int(os.environ.get('BOOKING_CUTOFF_MINUTES', '0') or 0))
    except ValueError:
        return 0


def create_app(config=None):
    load_dotenv(ROOT / '.env')
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        DATABASE=os.environ.get('PGDATABASE', 'joinly'),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
        MAX_CONTENT_LENGTH=3 * 1024 * 1024,
        UPLOAD_DIR=os.environ.get('JOINLY_UPLOAD_DIR', str(ROOT / 'instance' / 'uploads')),
        COVER_MAX_BYTES=2 * 1024 * 1024,
        TRUST_PROXY=os.environ.get('TRUST_PROXY', '0') == '1',
        TRUSTED_HOSTS=[host.strip() for host in os.environ.get('TRUSTED_HOSTS', '').split(',') if host.strip()] or None,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        WTF_CSRF_TIME_LIMIT=43200,
        PUBLIC_BASE_URL=os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/'),
        DEEPSEEK_API_KEY=os.environ.get('DEEPSEEK_API_KEY', '').strip(),
        DEEPSEEK_MODEL=os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash'),
        CHAT_DAILY_LIMIT=100,
        GOOGLE_CLIENT_ID=os.environ.get('GOOGLE_CLIENT_ID', '').strip(),
        GOOGLE_CLIENT_SECRET=os.environ.get('GOOGLE_CLIENT_SECRET', '').strip(),
    )
    if config:
        app.config.update(config)
    if not app.config['SECRET_KEY']:
        raise RuntimeError('Set SECRET_KEY in the server environment.')
    if app.config['TRUST_PROXY']:
        # Only enable behind the local Nginx proxy, which overwrites these headers.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)
    CSRFProtect(app)

    def db():
        if 'db' not in g:
            g.db = psycopg.connect(dbname=app.config['DATABASE'], row_factory=dict_row, autocommit=True)
        return g.db

    def query(sql, args=(), one=False):
        result = db().execute(sql, args)
        if result.description is None:
            return None
        return result.fetchone() if one else result.fetchall()

    @app.teardown_appcontext
    def close_db(error=None):
        if 'db' in g:
            g.db.close()

    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    @app.before_request
    def load_user():
        g.user = None
        g.roles = set()
        g.impersonator = None
        g.impersonating = False
        token = session.get('auth_token')
        if token:
            g.user = query('''SELECT u.id, u.email, u.display_name, u.status, u.email_verified_at, u.avatar_path FROM users u
                JOIN web_sessions s ON s.user_id=u.id
                WHERE s.token_hash=%s AND s.expires_at>now() AND u.status='active' ''', (digest(token),), True)
            if g.user:
                g.roles = {r['name'] for r in query('SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=%s', (g.user['id'],))}
                viewed = session.get('view_as')
                if viewed and 'admin' in g.roles:
                    target = query("SELECT id, email, display_name, status, email_verified_at, avatar_path FROM users WHERE id=%s AND status='active'", (int(viewed),), True)
                    if target and target['id'] != g.user['id']:
                        g.impersonator = g.user
                        g.user = target
                        g.roles = {r['name'] for r in query('SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=%s', (target['id'],))}
                        g.impersonating = True
                    else:
                        session.pop('view_as', None)
            else:
                session.clear()

    def interest_total(user_id):
        return query('SELECT count(*) AS n FROM user_interests WHERE user_id=%s', (user_id,), True)['n']

    @app.before_request
    def require_interests():
        if not g.user or 'admin' in g.roles or request.endpoint in INTEREST_FREE:
            return
        if interest_total(g.user['id']) < MIN_INTERESTS:
            return redirect(url_for('interests'))

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "img-src 'self' data: https://unpkg.com https://*.tile.openstreetmap.fr "
            "https://a.tile.openstreetmap.fr https://b.tile.openstreetmap.fr https://c.tile.openstreetmap.fr "
            "https://tile.openstreetmap.org https://a.tile.openstreetmap.org "
            "https://b.tile.openstreetmap.org https://c.tile.openstreetmap.org; "
            "style-src 'self' https://unpkg.com; script-src 'self' https://unpkg.com; "
            "worker-src 'self' blob:; media-src 'self' blob:; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        if request.path in ('/robots.txt', '/sitemap.xml'):
            response.headers['Cache-Control'] = 'public, max-age=3600'
        elif not request.path.startswith('/static/'):
            response.headers['Cache-Control'] = 'no-store'
        if app.config['SESSION_COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    def require(role=None):
        def decorator(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                if not g.user:
                    flash('Connectez-vous pour continuer.', 'info')
                    return redirect(url_for('login'))
                if role and role not in g.roles:
                    abort(403)
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    def text(name, maxlen=200, required=True):
        value = request.form.get(name, '').strip()
        if (required and not value) or len(value) > maxlen:
            raise ValueError(f'Champ « {name} » manquant ou trop long (maximum {maxlen}).')
        return value

    def email_value():
        email = text('email', 254).lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValueError('Adresse e-mail invalide.')
        return email

    def password_value():
        password = request.form.get('password', '')
        if not 12 <= len(password) <= 128:
            raise ValueError('Le mot de passe doit contenir entre 12 et 128 caractères.')
        return password

    def rate_limit(action, limit=10, minutes=15):
        # Store only a keyed digest, not a raw address. Reverse proxies must be configured explicitly.
        key = digest(app.config['SECRET_KEY'] + action + (request.remote_addr or 'local'))
        row = query('''INSERT INTO rate_limits(key,attempts,expires_at) VALUES (%s,1,now()+%s)
            ON CONFLICT(key) DO UPDATE SET
            attempts=CASE WHEN rate_limits.expires_at<now() THEN 1 ELSE rate_limits.attempts+1 END,
            expires_at=CASE WHEN rate_limits.expires_at<now() THEN EXCLUDED.expires_at ELSE rate_limits.expires_at END
            RETURNING attempts''', (key, timedelta(minutes=minutes)), True)
        if row['attempts'] > limit:
            abort(429)

    @app.errorhandler(ValueError)
    def invalid(error):
        return render_template('error.html', code=400, title='Vérifiez votre saisie', message=str(error)), 400

    @app.errorhandler(psycopg.errors.UniqueViolation)
    def duplicate(error):
        return render_template('error.html', code=409, title='Déjà enregistré', message='Cette adresse e-mail ou cette inscription existe déjà.'), 409

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template('error.html', code=400, title='Formulaire expiré', message='Rechargez la page et réessayez.'), 400

    error_pages = {
        403: ('Accès refusé', 'Vous ne pouvez pas accéder à cette page.'),
        404: ('Page introuvable', 'Cette adresse ne correspond à aucune page de Joinly.'),
        413: ('Envoi trop volumineux', 'Le formulaire envoyé est trop volumineux.'),
        429: ('Trop de tentatives', 'Trop de tentatives. Réessayez dans 15 minutes.'),
        500: ('Service momentanément indisponible', 'Une erreur est survenue. Réessayez dans un instant ou écrivez-nous si cela continue.'),
    }
    for code, (title, message) in error_pages.items():
        def handler(error, code=code, title=title, message=message):
            return render_template('error.html', code=code, title=title, message=message), code
        app.register_error_handler(code, handler)

    @app.template_filter('datefr')
    def datefr(value):
        return value.astimezone(PARIS).strftime('%d/%m/%Y à %H:%M') if value else ''

    @app.template_filter('inputdate')
    def inputdate(value):
        return value.astimezone(PARIS).strftime('%Y-%m-%dT%H:%M') if value else ''

    @app.template_filter('daynum')
    def daynum(value):
        return value.astimezone(PARIS).strftime('%d') if value else ''

    @app.template_filter('monthfr')
    def monthfr(value):
        return MONTHS_FR[value.astimezone(PARIS).month - 1] if value else ''

    @app.template_filter('timefr')
    def timefr(value):
        return value.astimezone(PARIS).strftime('%H:%M') if value else ''

    @app.template_filter('pricefr')
    def pricefr(cents):
        cents = int(cents or 0)
        if cents <= 0:
            return 'Gratuit'
        euros, centimes = divmod(cents, 100)
        if centimes:
            return f'{euros},{centimes:02d} €'
        return f'{euros} €'

    def money_cents(name='price'):
        raw = (request.form.get(name) or '').strip().replace(' ', '').replace('€', '').replace(',', '.')
        if not raw:
            raw = '0'
        try:
            value = Decimal(raw)
        except InvalidOperation:
            raise ValueError('Indiquez un prix en euros, par exemple 12,50. 0 signifie gratuit.')
        if value < 0 or value > Decimal('5000'):
            raise ValueError('Le prix doit être compris entre 0 et 5000 euros.')
        quantized = value.quantize(Decimal('0.01'))
        if quantized != value:
            raise ValueError('Le prix ne peut pas avoir plus de deux décimales.')
        return int(quantized * 100)

    def chosen_interest_ids(minimum):
        raw = request.form.getlist('interest_ids')
        if len(raw) > 20:
            raise ValueError('Vous pouvez sélectionner au plus 20 centres d’intérêt.')
        ids = []
        for value in raw:
            if not value.isdigit() or int(value) < 1:
                raise ValueError('Centre d’intérêt invalide.')
            ids.append(int(value))
        ids = list(dict.fromkeys(ids))
        if len(ids) < minimum:
            raise ValueError('Choisissez au moins 3 centres d’intérêt.')
        if ids:
            found = query('SELECT id FROM categories WHERE id = ANY(%s)', (ids,))
            if len(found) != len(ids):
                raise ValueError('Centre d’intérêt inconnu.')
        return ids

    def replace_interests(user_id, category_ids):
        names = [row['name'] for row in query('SELECT name FROM categories WHERE id = ANY(%s) ORDER BY name', (category_ids,))] if category_ids else []
        db().execute('DELETE FROM user_interests WHERE user_id=%s', (user_id,))
        if category_ids:
            db().execute(
                'INSERT INTO user_interests(user_id, category_id) SELECT %s, id FROM categories WHERE id = ANY(%s)',
                (user_id, category_ids),
            )
        db().execute(
            '''INSERT INTO member_preferences(user_id, interests) VALUES (%s, %s)
               ON CONFLICT (user_id) DO UPDATE SET interests=EXCLUDED.interests''',
            (user_id, names),
        )

    def slugify(value):
        normalized = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
        slug = re.sub(r'[^a-z0-9]+', '-', normalized.lower()).strip('-')
        return slug or 'section'

    @app.template_filter('legal_html')
    def legal_html(content):
        parts = []
        for block in re.split(r'\n\s*\n', (content or '').strip()):
            block = block.strip()
            if not block:
                continue
            if block.startswith('## '):
                heading, _, rest = block.partition('\n')
                title = heading[3:].strip()
                parts.append(Markup(f'<h2 id="{html_escape(slugify(title))}">{html_escape(title)}</h2>'))
                block = rest.strip()
                if not block:
                    continue
            lines = [html_escape(line) for line in block.split('\n')]
            parts.append(Markup('<p>{}</p>').format(Markup('<br>').join(lines)))
        return Markup('\n').join(parts)

    def public_base():
        return app.config.get('PUBLIC_BASE_URL') or request.url_root.rstrip('/')

    def cutoff_minutes():
        row = query('SELECT booking_cutoff_minutes FROM site_settings WHERE id=1', one=True)
        if row is not None:
            return max(0, int(row['booking_cutoff_minutes']))
        return max(0, int(app.config.get('BOOKING_CUTOFF_MINUTES') or 0))

    app.jinja_env.globals['avatar_initials'] = avatars.initials
    app.jinja_env.globals['avatar_color'] = avatars.color

    @app.context_processor
    def context():
        base = public_base()
        return {
            'now': datetime.now(timezone.utc),
            'public_base_url': base,
            'canonical_url': base + request.path,
            'og_image': base + url_for('static', filename='logo.png'),
            'legal_titles': LEGAL_TITLES,
            'booking_cutoff': timedelta(minutes=cutoff_minutes()),
            'unread': query(
                'SELECT count(*) AS n FROM notifications WHERE user_id=%s AND read_at IS NULL',
                (g.user['id'],), True,
            )['n'] if getattr(g, 'user', None) else 0,
            'policy_labels': POLICY_LABELS,
            'refund_preview': refund_cents,
            'avatar_initials': avatars.initials,
            'avatar_color': avatars.color,
            'google_enabled': bool(app.config.get('GOOGLE_CLIENT_ID') and app.config.get('GOOGLE_CLIENT_SECRET')),
            'settings': query('SELECT * FROM site_settings WHERE id=1', one=True),
        }

    event_select = '''SELECT e.*, u.display_name AS organizer, u.avatar_path AS organizer_avatar_path, c.name AS category, c.icon AS category_icon,
        e.capacity-(SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS available,
        (SELECT round(avg(rv.rating)::numeric, 1) FROM reviews rv WHERE rv.event_id=e.id AND NOT rv.hidden) AS rating_avg,
        (SELECT count(*) FROM reviews rv WHERE rv.event_id=e.id AND NOT rv.hidden) AS rating_count
        FROM events e JOIN users u ON u.id=e.organizer_id LEFT JOIN categories c ON c.id=e.category_id'''

    def ranked_events(limit=30):
        rows = query(
            event_select.replace('SELECT e.*,', '''SELECT e.*, (
                (SELECT count(*) FROM reservations r
                    WHERE r.event_id=e.id AND r.status='confirmed' AND r.reserved_at > now() - interval '30 days')
                    * (SELECT heat_recent_weight FROM site_settings WHERE id=1)
                + COALESCE((SELECT (count(*) FILTER (WHERE r.status='confirmed') * 100) / NULLIF(e.capacity, 0)
                    FROM reservations r WHERE r.event_id=e.id), 0)
                    * (SELECT heat_fill_weight FROM site_settings WHERE id=1)
                + LEAST(e.view_count, (SELECT heat_view_cap FROM site_settings WHERE id=1))
            ) AS heat,''', 1)
            + " WHERE e.status='published' AND e.ends_at>now() ORDER BY heat DESC, e.starts_at, e.id LIMIT %s",
            (limit,),
        )
        for index, row in enumerate(rows, 1):
            row['rank'] = index
        return covers.decorate(rows)

    def recommendations(limit=6):
        rows = []
        if g.user:
            rows = query(
                event_select + ''' WHERE e.status='published' AND e.ends_at>now()
                AND e.category_id IN (SELECT category_id FROM user_interests WHERE user_id=%s)
                ORDER BY ((SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') >= e.capacity),
                         e.starts_at, e.id
                LIMIT %s''',
                (g.user['id'], limit),
            )
        personal = bool(rows)
        if rows:
            return covers.decorate(rows), personal
        rows = query(
            event_select + ''' WHERE e.id IN (
                SELECT DISTINCT ON (category_id) id FROM events
                WHERE status='published' AND ends_at>now() AND category_id IS NOT NULL
                ORDER BY category_id, starts_at, id
            ) ORDER BY e.starts_at, e.id LIMIT %s''',
            (limit,),
        )
        if len(rows) < limit:
            chosen = [row['id'] for row in rows]
            clause = " AND NOT (e.id = ANY(%s))" if chosen else ''
            args = (chosen, limit - len(rows)) if chosen else (limit - len(rows),)
            more = query(
                event_select + f" WHERE e.status='published' AND e.ends_at>now(){clause} ORDER BY e.starts_at, e.id LIMIT %s",
                args,
            )
            rows.extend(more)
        return covers.decorate(rows), False

    def catalogue(limit=12, paginate=True):
        when = (request.args.get('when') or 'upcoming').strip()
        if when not in ('upcoming', 'past'):
            raise ValueError('Période de recherche invalide.')
        filters = ["e.status='published'", 'e.ends_at > now()' if when == 'upcoming' else 'e.ends_at <= now()']
        args = []
        for field, clause in (
            ('q', '(e.title ILIKE %s OR e.description ILIKE %s)'),
            ('location', 'e.location ILIKE %s'),
            ('city', 'e.city ILIKE %s'),
        ):
            value = request.args.get(field, '').strip()[:200]
            if value:
                filters.append(clause)
                args.extend([f'%{value}%'] * (2 if field == 'q' else 1))
        category = request.args.get('category', '')
        if category:
            if not category.isdigit() or not 1 <= int(category) <= 9223372036854775807:
                raise ValueError('Catégorie invalide.')
            filters.append('e.category_id=%s')
            args.append(int(category))
        for name, operator in [('from', '>='), ('to', '<')]:
            value = request.args.get(name)
            if value:
                try:
                    day = datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=PARIS)
                except ValueError:
                    raise ValueError('Date de recherche invalide.')
                if name == 'to':
                    day += timedelta(days=1)
                filters.append(f'e.starts_at {operator} %s')
                args.append(day)
        price = (request.args.get('price') or '').strip()
        if price == 'free':
            filters.append('e.price_cents = 0')
        elif price == 'paid':
            filters.append('e.price_cents > 0')
        elif price:
            raise ValueError('Filtre de prix invalide.')
        raw_max = (request.args.get('max') or '').strip().replace(' ', '').replace('€', '').replace(',', '.')
        if raw_max:
            try:
                parsed = Decimal(raw_max)
            except InvalidOperation:
                raise ValueError('Prix maximum invalide.')
            if parsed < 0 or parsed > Decimal('5000'):
                raise ValueError('Prix maximum invalide.')
            quantized = parsed.quantize(Decimal('0.01'))
            if quantized != parsed:
                raise ValueError('Le prix maximum ne peut pas avoir plus de deux décimales.')
            filters.append('e.price_cents <= %s')
            args.append(int(quantized * 100))
        sort = (request.args.get('sort') or 'date').strip()
        orders = {
            'date': 'e.starts_at DESC, e.id DESC' if when == 'past' else 'e.starts_at ASC, e.id ASC',
            'popularity': "(SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') DESC, e.starts_at ASC, e.id ASC",
            'rating': 'rating_avg DESC NULLS LAST, rating_count DESC, e.starts_at ASC, e.id ASC',
            'price': 'e.price_cents ASC, e.starts_at ASC, e.id ASC',
        }
        if sort not in orders:
            raise ValueError('Tri invalide.')
        page = 1
        if paginate:
            page = request.args.get('page', '1')
            if not str(page).isdigit() or not 1 <= int(page) <= 10000:
                raise ValueError('Page invalide.')
            page = int(page)
        where = ' WHERE ' + ' AND '.join(filters)
        total = query('SELECT count(*) AS n FROM events e' + where, tuple(args), True)['n']
        rows = query(
            event_select + where + f' ORDER BY {orders[sort]} LIMIT %s OFFSET %s',
            (*args, limit, (page - 1) * limit if paginate else 0),
        )
        covers.decorate(rows)
        pages = max(1, (total + limit - 1) // limit) if limit else 1
        return {'events': rows, 'total': total, 'page': page, 'pages': pages}

    def activity_page_url(number):
        params = {}
        for key in ('q', 'location', 'city', 'category', 'from', 'to', 'price', 'max', 'sort', 'when'):
            value = request.args.get(key, '').strip()
            if value:
                params[key] = value
        if number > 1:
            params['page'] = number
        return url_for('activities', **params)

    @app.get('/')
    def home():
        recommended, personal = recommendations()
        pinned = covers.decorate(query(
            event_select + " WHERE e.pinned AND e.status='published' AND e.ends_at>now() ORDER BY e.starts_at, e.id LIMIT 6"
        ))
        return render_template(
            'home.html', events=catalogue(6, paginate=False)['events'],
            recommended=recommended, personal=personal, trending=ranked_events(5), pinned=pinned,
        )

    @app.get('/classement')
    def classement():
        return render_template('classement.html', events=ranked_events(30))

    @app.get('/activities')
    def activities():
        found = catalogue()
        return render_template(
            'activities.html', events=found['events'], total=found['total'], page=found['page'], pages=found['pages'],
            prev_url=activity_page_url(found['page'] - 1) if found['page'] > 1 else None,
            next_url=activity_page_url(found['page'] + 1) if found['page'] < found['pages'] else None,
            categories=query('SELECT * FROM categories ORDER BY name'),
            cities=query("SELECT DISTINCT city FROM events WHERE status='published' AND btrim(city) <> '' ORDER BY city"),
        )

    @app.get('/activities/<int:event_id>')
    def detail(event_id):
        event = query(event_select + ' WHERE e.id=%s', (event_id,), True)
        if not event or (event['status'] == 'draft' and (not g.user or event['organizer_id'] != g.user['id'])):
            abort(404)
        if event['status'] == 'published':
            db().execute('UPDATE events SET view_count=view_count+1 WHERE id=%s', (event_id,))
            event['view_count'] += 1
        booking = query("SELECT * FROM reservations WHERE event_id=%s AND member_id=%s AND status='confirmed'", (event_id, g.user['id']), True) if g.user else None
        reviews = query(
            '''SELECT rv.*, u.display_name, u.avatar_path FROM reviews rv JOIN users u ON u.id=rv.author_id
               WHERE rv.event_id=%s AND (NOT rv.hidden OR rv.author_id=%s)
               ORDER BY rv.created_at DESC''',
            (event_id, g.user['id'] if g.user else 0),
        )
        mine = next((row for row in reviews if g.user and row['author_id'] == g.user['id']), None)
        can_review = bool(booking and event['status'] == 'published' and is_finished(event))
        favorited = following = False
        if g.user:
            favorited = bool(query('SELECT 1 FROM favorites WHERE user_id=%s AND event_id=%s', (g.user['id'], event_id), True))
            following = bool(query(
                'SELECT 1 FROM organizer_follows WHERE follower_id=%s AND organizer_id=%s',
                (g.user['id'], event['organizer_id']),
                True,
            ))
        covers.decorate([event])
        library = covers.library_tree() if g.user and 'admin' in g.roles else []
        share_url = public_base() + url_for('detail', event_id=event_id)
        share_image = public_base() + (event.get('cover_href') or url_for('static', filename='logo.png'))
        return render_template(
            'detail.html', event=event, booking=booking, reviews=reviews, mine=mine,
            can_review=can_review, favorited=favorited, following=following, library=library,
            share_url=share_url, share_image=share_image,
        )

    @app.post('/activities/<int:event_id>/avis')
    @require()
    def review(event_id):
        event = query('SELECT * FROM events WHERE id=%s', (event_id,), True)
        if not event or event['status'] != 'published':
            abort(404)
        if not is_finished(event):
            raise ValueError('Vous pourrez laisser un avis une fois l’activité terminée.')
        booking = query(
            "SELECT id FROM reservations WHERE event_id=%s AND member_id=%s AND status='confirmed'",
            (event_id, g.user['id']),
            True,
        )
        if not booking:
            raise ValueError('Seules les personnes dont l’inscription est confirmée peuvent laisser un avis.')
        try:
            rating = int(request.form.get('rating', ''))
        except ValueError:
            rating = 0
        comment = request.form.get('comment', '').strip()
        if rating not in range(1, 6) or not 1 <= len(comment) <= 2000:
            raise ValueError('Choisissez une note de 1 à 5 et un commentaire (2 000 caractères maximum).')
        existing = query('SELECT id FROM reviews WHERE event_id=%s AND author_id=%s', (event_id, g.user['id']), True)
        if existing:
            db().execute('UPDATE reviews SET rating=%s, comment=%s WHERE id=%s', (rating, comment, existing['id']))
            flash('Avis mis à jour.', 'success')
        else:
            db().execute(
                'INSERT INTO reviews(event_id, author_id, rating, comment) VALUES (%s, %s, %s, %s)',
                (event_id, g.user['id'], rating, comment),
            )
            organizer = query('SELECT id FROM users WHERE id=%s', (event['organizer_id'],), True)
            if organizer and organizer['id'] != g.user['id']:
                notify.notify(
                    app, query, organizer['id'], 'new_review', 'Nouvel avis',
                    f'Un participant a laissé un avis sur « {event["title"]} ».',
                    f'/activities/{event_id}', dedupe_key=f'review:{event_id}:{g.user["id"]}',
                )
            flash('Merci, votre avis est publié.', 'success')
        return redirect(url_for('detail', event_id=event_id))

    @app.post('/activities/<int:event_id>/favori')
    @require()
    def toggle_favorite(event_id):
        if not query("SELECT id FROM events WHERE id=%s AND status='published'", (event_id,), True):
            abort(404)
        existing = query('SELECT 1 FROM favorites WHERE user_id=%s AND event_id=%s', (g.user['id'], event_id), True)
        if existing:
            db().execute('DELETE FROM favorites WHERE user_id=%s AND event_id=%s', (g.user['id'], event_id))
            flash('Retiré de vos favoris.', 'success')
        else:
            db().execute('INSERT INTO favorites(user_id, event_id) VALUES (%s, %s)', (g.user['id'], event_id))
            flash('Ajouté à vos favoris.', 'success')
        return redirect(url_for('detail', event_id=event_id))

    @app.post('/organisateurs/<int:user_id>/suivre')
    @require()
    def toggle_follow(user_id):
        if user_id == g.user['id']:
            raise ValueError('Vous ne pouvez pas vous suivre vous-même.')
        organizer = query(
            '''SELECT u.id FROM users u
               JOIN user_roles ur ON ur.user_id=u.id
               JOIN roles r ON r.id=ur.role_id AND r.name='organizer'
               WHERE u.id=%s AND u.status='active' ''',
            (user_id,),
            True,
        )
        if not organizer:
            abort(404)
        existing = query(
            'SELECT 1 FROM organizer_follows WHERE follower_id=%s AND organizer_id=%s',
            (g.user['id'], user_id),
            True,
        )
        if existing:
            db().execute(
                'DELETE FROM organizer_follows WHERE follower_id=%s AND organizer_id=%s',
                (g.user['id'], user_id),
            )
            flash('Vous ne suivez plus cet organisateur.', 'success')
        else:
            db().execute(
                'INSERT INTO organizer_follows(follower_id, organizer_id) VALUES (%s, %s)',
                (g.user['id'], user_id),
            )
            flash('Organisateur suivi.', 'success')
        return redirect(url_for('organizer_public', user_id=user_id))

    @app.get('/organisateurs/<int:user_id>')
    def organizer_public(user_id):
        person = query(
            '''SELECT u.id, u.display_name, u.avatar_path,
                      (SELECT count(*) FROM organizer_follows f WHERE f.organizer_id=u.id) AS followers,
                      (SELECT round(avg(rv.rating)::numeric, 1) FROM reviews rv
                         JOIN events e ON e.id=rv.event_id
                        WHERE e.organizer_id=u.id AND NOT rv.hidden) AS rating_avg,
                      (SELECT count(*) FROM reviews rv JOIN events e ON e.id=rv.event_id
                        WHERE e.organizer_id=u.id AND NOT rv.hidden) AS rating_count
               FROM users u
               JOIN user_roles ur ON ur.user_id=u.id
               JOIN roles r ON r.id=ur.role_id AND r.name='organizer'
               WHERE u.id=%s AND u.status='active' ''',
            (user_id,),
            True,
        )
        if not person:
            abort(404)
        events = query(
            event_select + " WHERE e.organizer_id=%s AND e.status='published' ORDER BY e.starts_at DESC",
            (user_id,),
        )
        covers.decorate(events)
        following = bool(g.user and query(
            'SELECT 1 FROM organizer_follows WHERE follower_id=%s AND organizer_id=%s',
            (g.user['id'], user_id),
            True,
        ))
        return render_template('organizer_public.html', person=person, events=events, following=following)

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if request.method == 'POST':
            rate_limit('signup')
            email = email_value()
            name = text('display_name', 100)
            password = password_value()
            role = text('role')
            if role not in ('member', 'organizer'):
                abort(400)
            with db().transaction():
                user = query('INSERT INTO users(email,display_name,password_hash) VALUES (%s,%s,%s) RETURNING id', (email, name, generate_password_hash(password)), True)
                db().execute("INSERT INTO user_roles(user_id,role_id) SELECT %s,id FROM roles WHERE name='member' OR name=%s", (user['id'], role))
            notify.start_verification(app, query, user['id'], email)
            flash('Nous vous avons envoyé un code à 6 chiffres.', 'success')
            return redirect(url_for('verify_email', email=email))
        return render_template('auth.html', mode='signup')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            rate_limit('login')
            email = email_value()
            password = request.form.get('password', '')[:129]
            user = query('SELECT * FROM users WHERE email=%s', (email,), True)
            valid = check_password_hash(user['password_hash'] if user else DUMMY_HASH, password)
            if not user or not valid or user['status'] != 'active':
                flash('Identifiants incorrects ou compte indisponible.', 'error')
                return render_template('auth.html', mode='login'), 401
            if not user['email_verified_at']:
                flash('Confirmez votre adresse avec le code reçu par e-mail.', 'info')
                return redirect(url_for('verify_email', email=user['email']))
            token = secrets.token_urlsafe(32)
            session.clear()
            session.permanent = True
            session['auth_token'] = token
            db().execute('INSERT INTO web_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,now()+interval \'12 hours\')', (digest(token), user['id']))
            roles = {r['name'] for r in query('SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=%s', (user['id'],))}
            if 'admin' not in roles and interest_total(user['id']) < MIN_INTERESTS:
                flash('Choisissez au moins 3 centres d’intérêt pour continuer.', 'info')
                return redirect(url_for('interests'))
            return redirect(url_for('account'))
        return render_template('auth.html', mode='login')

    @app.route('/verifier-email', methods=['GET', 'POST'])
    def verify_email():
        if request.method == 'POST':
            rate_limit('verify-code', 10, 15)
            email = email_value()
            code = re.sub(r'\s+', '', request.form.get('code', ''))
            if not re.fullmatch(r'\d{6}', code):
                raise ValueError('Saisissez le code à 6 chiffres.')
            account = query("SELECT id, email_verified_at, status FROM users WHERE email=%s", (email,), True)
            if not account or account['status'] != 'active':
                raise ValueError('Code incorrect.')
            if account['email_verified_at']:
                flash('Cette adresse est déjà confirmée.', 'success')
                return redirect(url_for('login'))
            notify.check_verification(app, query, account['id'], code)
            token = secrets.token_urlsafe(32)
            session.clear()
            session.permanent = True
            session['auth_token'] = token
            db().execute('INSERT INTO web_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,now()+interval \'12 hours\')', (digest(token), account['id']))
            roles = {row['name'] for row in query('SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=%s', (account['id'],))}
            if 'admin' not in roles and interest_total(account['id']) < MIN_INTERESTS:
                return redirect(url_for('interests'))
            return redirect(url_for('home'))
        return render_template('auth.html', mode='verify', email=request.args.get('email', ''))

    @app.post('/verifier-email/renvoyer')
    def resend_verification():
        rate_limit('verify-resend', 5, 15)
        email = email_value()
        account = query("SELECT id, email_verified_at, status FROM users WHERE email=%s", (email,), True)
        if account and account['status'] == 'active' and not account['email_verified_at']:
            notify.start_verification(app, query, account['id'], email)
        flash('Si un compte non confirmé correspond à cette adresse, un nouveau code a été envoyé.', 'success')
        return redirect(url_for('verify_email', email=email))

    def google_ready():
        return bool(app.config.get('GOOGLE_CLIENT_ID') and app.config.get('GOOGLE_CLIENT_SECRET'))

    def default_google_userinfo():
        from authlib.integrations.requests_client import OAuth2Session
        redirect_uri = public_base() + url_for('google_callback')
        nonce = session.get('google_nonce')
        client = OAuth2Session(
            app.config['GOOGLE_CLIENT_ID'], app.config['GOOGLE_CLIENT_SECRET'],
            scope='openid email profile', redirect_uri=redirect_uri,
            state=session.get('google_state'), nonce=nonce,
        )
        token = client.fetch_token('https://oauth2.googleapis.com/token', code=request.args.get('code', ''))
        claims = client.parse_id_token(token, nonce=nonce) if token.get('id_token') else {}
        info = token.get('userinfo') or client.get('https://openidconnect.googleapis.com/v1/userinfo').json()
        info['sub'] = info.get('sub') or claims.get('sub')
        info['nonce'] = claims.get('nonce')
        if 'email_verified' not in info and 'email_verified' in claims:
            info['email_verified'] = claims.get('email_verified')
        return info

    app.google_userinfo = default_google_userinfo

    def _same(left, right):
        import hmac
        raw_left, raw_right = str(left or '').encode(), str(right or '').encode()
        if not raw_left or len(raw_left) != len(raw_right):
            return False
        return hmac.compare_digest(raw_left, raw_right)

    @app.get('/auth/google')
    def google_start():
        if not google_ready():
            abort(404)
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        session['google_state'] = state
        session['google_nonce'] = nonce
        redirect_uri = public_base() + url_for('google_callback')
        params = urlencode({
            'client_id': app.config['GOOGLE_CLIENT_ID'],
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'state': state,
            'nonce': nonce,
        })
        return redirect('https://accounts.google.com/o/oauth2/v2/auth?' + params)

    @app.get('/auth/google/callback')
    def google_callback():
        if not google_ready():
            abort(404)
        if not _same(request.args.get('state', ''), session.get('google_state')):
            abort(400)
        try:
            info = current_app.google_userinfo()
        except Exception:
            app.logger.exception('Google sign-in failed')
            flash('Connexion Google impossible pour le moment.', 'error')
            return redirect(url_for('login'))
        session.pop('google_state', None)
        nonce = session.pop('google_nonce', None)
        if not isinstance(info, dict) or not _same(info.get('nonce'), nonce):
            abort(400)
        if not info.get('email_verified') or not info.get('email') or not info.get('sub'):
            flash('Le compte Google ne fournit pas une adresse e-mail vérifiée.', 'error')
            return redirect(url_for('login'))
        email = str(info['email']).strip().lower()
        sub = str(info['sub'])[:255]
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            abort(400)
        by_sub = query('SELECT * FROM users WHERE google_sub=%s', (sub,), True)
        by_email = query('SELECT * FROM users WHERE email=%s', (email,), True)
        if by_sub and by_email and by_sub['id'] != by_email['id']:
            flash('Ce compte Google est déjà lié à une autre adresse.', 'error')
            return redirect(url_for('login'))
        account = by_sub or by_email
        if account and account['status'] != 'active':
            flash('Compte indisponible.', 'error')
            return redirect(url_for('login'))
        if account and account.get('google_sub') and account['google_sub'] != sub:
            flash('Cette adresse est déjà liée à un autre compte Google.', 'error')
            return redirect(url_for('login'))
        if account:
            db().execute(
                'UPDATE users SET google_sub=%s, email_verified_at=COALESCE(email_verified_at, now()) WHERE id=%s',
                (sub, account['id']),
            )
            user_id = account['id']
        else:
            name = (str(info.get('name') or email.split('@')[0])).strip()[:100] or email.split('@')[0]
            created = query(
                '''INSERT INTO users(email, display_name, password_hash, email_verified_at, google_sub)
                   VALUES (%s, %s, %s, now(), %s) RETURNING id''',
                (email, name, generate_password_hash(secrets.token_urlsafe(32)), sub), True,
            )
            db().execute("INSERT INTO user_roles(user_id, role_id) SELECT %s, id FROM roles WHERE name='member'", (created['id'],))
            user_id = created['id']
        token = secrets.token_urlsafe(32)
        session.clear()
        session.permanent = True
        session['auth_token'] = token
        db().execute("INSERT INTO web_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,now()+interval '12 hours')", (digest(token), user_id))
        if interest_total(user_id) < MIN_INTERESTS:
            return redirect(url_for('interests'))
        return redirect(url_for('home'))

    @app.post('/logout')
    def logout():
        if session.get('auth_token'):
            db().execute('DELETE FROM web_sessions WHERE token_hash=%s', (digest(session['auth_token']),))
        session.clear()
        return redirect(url_for('home'))

    @app.route('/interests', methods=['GET', 'POST'])
    @require()
    def interests():
        if request.method == 'POST':
            chosen = chosen_interest_ids(MIN_INTERESTS)
            with db().transaction():
                replace_interests(g.user['id'], chosen)
            flash('Centres d’intérêt enregistrés.', 'success')
            return redirect(url_for('home'))
        selected = {row['category_id'] for row in query('SELECT category_id FROM user_interests WHERE user_id=%s', (g.user['id'],))}
        return render_template(
            'interests.html', interest_minimum=MIN_INTERESTS, selected=selected,
            categories=query('SELECT id, name, icon FROM categories ORDER BY name'),
        )

    @app.route('/account', methods=['GET', 'POST'])
    @require()
    def account():
        minimum = 0 if 'admin' in g.roles else MIN_INTERESTS
        if request.method == 'POST':
            name = text('display_name', 100)
            chosen = chosen_interest_ids(minimum)
            with db().transaction():
                db().execute('UPDATE users SET display_name=%s WHERE id=%s', (name, g.user['id']))
                replace_interests(g.user['id'], chosen)
                db().execute('''INSERT INTO member_preferences(user_id,chosen_area,assistant_consent) VALUES (%s,%s,%s)
                    ON CONFLICT(user_id) DO UPDATE SET chosen_area=EXCLUDED.chosen_area, assistant_consent=EXCLUDED.assistant_consent''',
                    (g.user['id'], text('chosen_area', 150, False), 'assistant_consent' in request.form))
            flash('Profil enregistré.', 'success')
            return redirect(url_for('account'))
        prefs = query('SELECT * FROM member_preferences WHERE user_id=%s', (g.user['id'],), True)
        bookings = query('''SELECT r.*, e.title, e.starts_at, e.ends_at, e.location, e.status AS event_status,
            e.price_cents, e.cancellation_policy
            FROM reservations r JOIN events e ON e.id=r.event_id
            WHERE r.member_id=%s ORDER BY e.starts_at DESC''', (g.user['id'],))
        moment = datetime.now(timezone.utc)
        upcoming = [row for row in bookings if row['status'] == 'confirmed' and row['ends_at'] > moment]
        history = [row for row in bookings if row not in upcoming]
        favorites = query(
            event_select + ''' WHERE e.id IN (SELECT event_id FROM favorites WHERE user_id=%s)
               ORDER BY e.starts_at''',
            (g.user['id'],),
        )
        covers.decorate(favorites)
        followed = query(
            '''SELECT u.id, u.display_name, u.avatar_path,
                      (SELECT count(*) FROM organizer_follows f WHERE f.organizer_id=u.id) AS followers
               FROM organizer_follows mine
               JOIN users u ON u.id=mine.organizer_id
               WHERE mine.follower_id=%s ORDER BY u.display_name''',
            (g.user['id'],),
        )
        selected = {row['category_id'] for row in query('SELECT category_id FROM user_interests WHERE user_id=%s', (g.user['id'],))}
        return render_template(
            'account.html', preferences=prefs, bookings=upcoming, history=history, favorites=favorites,
            followed=followed, selected=selected, interest_minimum=minimum,
            categories=query('SELECT id, name, icon FROM categories ORDER BY name'),
        )

    @app.post('/account/avatar')
    @require()
    def account_avatar():
        if request.form.get('remove'):
            previous = g.user.get('avatar_path')
            db().execute('UPDATE users SET avatar_path=NULL WHERE id=%s', (g.user['id'],))
            avatars.delete_avatar(app, previous)
            flash('Photo de profil retirée.', 'success')
            return redirect(url_for('account'))
        uploaded = request.files.get('avatar') if request.files else None
        if not uploaded or not uploaded.filename:
            raise ValueError('Choisissez une image (JPEG, PNG ou WebP, 2 Mo maximum).')
        name = avatars.save_avatar(app, g.user['id'], uploaded, g.user.get('avatar_path'))
        db().execute('UPDATE users SET avatar_path=%s WHERE id=%s', (name, g.user['id']))
        flash('Photo de profil mise à jour.', 'success')
        return redirect(url_for('account'))

    @app.post('/account/security')
    @require()
    def account_security():
        rate_limit('account-security')
        user = query('SELECT password_hash FROM users WHERE id=%s', (g.user['id'],), True)
        if not check_password_hash(user['password_hash'], request.form.get('current_password', '')[:129]):
            raise ValueError('Le mot de passe actuel est incorrect.')
        email = email_value()
        password = request.form.get('password', '')
        hashed = generate_password_hash(password_value()) if password else user['password_hash']
        with db().transaction():
            db().execute('UPDATE users SET email=%s,password_hash=%s WHERE id=%s', (email, hashed, g.user['id']))
            db().execute('DELETE FROM web_sessions WHERE user_id=%s', (g.user['id'],))
            db().execute('DELETE FROM password_resets WHERE user_id=%s', (g.user['id'],))
        session.clear()
        flash('Identifiants mis à jour. Connectez-vous à nouveau.', 'success')
        return redirect(url_for('login'))

    @app.get('/activities/<int:event_id>/reserver')
    @require()
    def reserve_confirm(event_id):
        event = query(event_select + ' WHERE e.id=%s', (event_id,), True)
        if not event or (event['status'] == 'draft' and event['organizer_id'] != g.user['id'] and 'admin' not in g.roles):
            abort(404)
        booking = query(
            "SELECT * FROM reservations WHERE event_id=%s AND member_id=%s AND status='confirmed'",
            (event_id, g.user['id']), True,
        )
        messages = {
            'finished': 'Cette activité est terminée.',
            'cutoff': 'Les inscriptions sont closes.',
            'full': 'Cette activité n’a plus de place disponible ou les inscriptions sont fermées.',
            'cancelled': 'Cette activité est annulée.',
            'unpublished': 'Cette activité n’a plus de place disponible ou les inscriptions sont fermées.',
        }
        reason_code = booking_block(event, cutoff_minutes=cutoff_minutes(), available=event['available'])
        return render_template(
            'confirm.html', event=event, booking=booking,
            reservable=not reason_code, reason=messages.get(reason_code, ''),
        )

    def send_booking_notification(event, ticket, user):
        plain, html_body, images = notify.booking_email(event, ticket, public_base())
        notify.notify(
            app, query, user['id'], 'booking_confirmed', 'Place confirmée',
            plain, f'/billets/{ticket["token"]}', dedupe_key=f'booking:{ticket["reservation_id"]}', email=user['email'],
            html_body=html_body, inline_images=images,
        )

    @app.post('/activities/<int:event_id>/reserve')
    @require()
    def reserve(event_id):
        if request.form.get('confirm') != '1' or request.form.get('acknowledged') != '1':
            return redirect(url_for('reserve_confirm', event_id=event_id))
        from app.bookings import create_booking
        with db().transaction():
            event, ticket, created = create_booking(db(), g.user['id'], event_id, cutoff_minutes(),
                                                   request.form.get('payment_simulated') == '1')
        send_booking_notification(event, ticket, g.user)
        if event['price_cents'] > 0:
            flash('Paiement simulé confirmé. Votre place est réservée — aucun montant n’a été débité.', 'success')
        else:
            flash('Votre place est réservée ! Retrouvez-la dans votre espace.', 'success')
        return redirect(url_for('account'))

    @app.get('/activities/<int:event_id>/paiement')
    @require()
    def simulated_payment(event_id):
        event = query(event_select + ' WHERE e.id=%s', (event_id,), True)
        if not event or (event['status'] == 'draft' and event['organizer_id'] != g.user['id']):
            abort(404)
        if event['price_cents'] <= 0:
            return redirect(url_for('detail', event_id=event_id))
        return redirect(url_for('reserve_confirm', event_id=event_id))

    @app.post('/reservations/<int:booking_id>/cancel')
    @require()
    def cancel_booking(booking_id):
        with db().transaction():
            booking = query('SELECT * FROM reservations WHERE id=%s AND member_id=%s', (booking_id, g.user['id']), True)
            if not booking:
                abort(404)
            event = query('SELECT * FROM events WHERE id=%s FOR UPDATE', (booking['event_id'],), True)
            if event['starts_at'] <= datetime.now(timezone.utc):
                raise ValueError('Cette activité a déjà commencé.')
            cents = refund_cents(event)
            db().execute(
                '''UPDATE reservations SET status='cancelled', cancelled_at=clock_timestamp(),
                   refund_cents=%s, refund_status=%s,
                   refunded_at=CASE WHEN %s > 0 THEN clock_timestamp() ELSE NULL END
                   WHERE id=%s AND status='confirmed' ''',
                (cents, 'simulated' if cents else 'none', cents, booking_id),
            )
        euros = f'{cents // 100},{cents % 100:02d} €'
        notify.notify(
            app, query, g.user['id'], 'event_cancelled', 'Réservation annulée',
            f'Votre inscription à « {event["title"]} » est annulée. Remboursement simulé : {euros}.',
            '/account/billets', dedupe_key=f'refund:{booking_id}', email=g.user['email'],
        )
        organizer = query('SELECT id, email FROM users WHERE id=%s', (event['organizer_id'],), True)
        if organizer and organizer['id'] != g.user['id']:
            notify.notify(
                app, query, organizer['id'], 'event_changed', 'Une inscription a été annulée',
                f'{g.user["display_name"]} a annulé sa place pour « {event["title"]} ». Remboursement simulé : {euros}.',
                f'/organizer/{event["id"]}/participants', email=organizer['email'],
            )
        flash(f'Réservation annulée. Remboursement simulé : {euros}.', 'success')
        return redirect(url_for('account'))

    def _organizer_board():
        days = dashboards.period_days(request.args)
        return render_template('dashboard.html', **dashboards.organizer_payload(query, g.user['id'], days))

    @app.get('/organizer')
    @require('organizer')
    def organizer():
        return _organizer_board()

    @app.get('/organizer/tableau')
    @require('organizer')
    def organizer_dashboard():
        return _organizer_board()

    @app.get('/organizer/activites')
    @require('organizer')
    def organizer_activities():
        return render_template(
            'organizer_activities.html',
            events=query(event_select + ' WHERE e.organizer_id=%s ORDER BY e.starts_at DESC', (g.user['id'],)),
        )

    def event_data():
        try:
            starts = datetime.fromisoformat(text('starts_at')).replace(tzinfo=PARIS)
            ends = datetime.fromisoformat(text('ends_at')).replace(tzinfo=PARIS)
            capacity = int(text('capacity'))
            category_id = int(text('category_id'))
        except (ValueError, OverflowError):
            raise ValueError('Vérifiez les dates, la catégorie et le nombre de places.')
        for instant in (starts, ends):
            if instant.astimezone(timezone.utc).astimezone(PARIS).replace(tzinfo=None) != instant.replace(tzinfo=None):
                raise ValueError('Cette heure n’existe pas lors du changement d’heure.')
        if ends <= starts or not 1 <= capacity <= 100000 or not query('SELECT id FROM categories WHERE id=%s', (category_id,), True):
            raise ValueError('Dates, capacité ou catégorie invalides.')
        status = text('status')
        if status not in ('draft', 'published') or starts <= datetime.now(timezone.utc):
            raise ValueError('Choisissez un état valide et une date future.')
        payload = dict(title=text('title', 180), description=text('description', 10000), location=text('location', 200), starts_at=starts, ends_at=ends, capacity=capacity, category_id=category_id, status=status, price_cents=money_cents())
        if 'city' in request.form:
            city = request.form.get('city', '').strip()
            if len(city) > 80:
                raise ValueError('La ville est trop longue (80 caractères maximum).')
            payload['city'] = city
        if 'latitude' in request.form or 'longitude' in request.form:
            raw_lat = request.form.get('latitude', '').strip()
            raw_lng = request.form.get('longitude', '').strip()
            if not raw_lat and not raw_lng:
                payload['latitude'] = None
                payload['longitude'] = None
            else:
                try:
                    latitude = Decimal(raw_lat)
                    longitude = Decimal(raw_lng)
                except InvalidOperation:
                    raise ValueError('Indiquez une latitude et une longitude, par exemple 48.84622 et 2.33716.')
                if not (Decimal('-90') <= latitude <= Decimal('90') and Decimal('-180') <= longitude <= Decimal('180')):
                    raise ValueError('Coordonnées hors limites.')
                payload['latitude'] = latitude
                payload['longitude'] = longitude
        if 'cancellation_policy' in request.form:
            policy = request.form.get('cancellation_policy') or 'flexible'
            if policy not in POLICY_LABELS:
                raise ValueError('Politique d’annulation invalide.')
            payload['cancellation_policy'] = policy
        return payload

    @app.route('/organizer/new', methods=['GET', 'POST'])
    @app.route('/organizer/<int:event_id>/edit', methods=['GET', 'POST'])
    @require('organizer')
    def edit_event(event_id=None):
        event = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s', (event_id, g.user['id']), True) if event_id else None
        if event_id and not event:
            abort(404)
        if request.method == 'POST':
            data = event_data()
            previous = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s', (event_id, g.user['id']), True) if event_id else None
            with db().transaction():
                if event_id:
                    event = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s FOR UPDATE', (event_id, g.user['id']), True)
                    if is_finished(event):
                        raise ValueError('Une activité terminée ne peut plus changer de dates. Un administrateur peut les corriger.')
                    if event['status'] == 'cancelled' or event['starts_at'] <= datetime.now(timezone.utc):
                        raise ValueError('Une activité annulée ou commencée ne peut plus être modifiée.')
                    counts = query("SELECT count(*) AS total, count(*) FILTER (WHERE status='confirmed') AS active FROM reservations WHERE event_id=%s", (event_id,), True)
                    if counts['total'] and any(data[k] != event[k] for k in ('starts_at', 'ends_at', 'location')):
                        raise ValueError('Après une inscription, la date et le lieu ne peuvent plus changer. Annulez puis créez une nouvelle activité.')
                    if counts['total'] and data['status'] == 'draft':
                        raise ValueError('Une activité avec des inscriptions ne peut pas redevenir un brouillon.')
                    if data['capacity'] < counts['active']:
                        raise ValueError('La capacité ne peut pas être inférieure au nombre d’inscrits.')
                    assignments = ','.join(f'{k}=%s' for k in data)
                    db().execute(f'UPDATE events SET {assignments} WHERE id=%s', (*data.values(), event_id))
                else:
                    columns = ','.join(data)
                    placeholders = ','.join(['%s'] * len(data))
                    event_id = query(
                        f'INSERT INTO events(organizer_id,{columns}) VALUES (%s,{placeholders}) RETURNING id',
                        (g.user['id'], *data.values()),
                        True,
                    )['id']
                    event = {'cover_image': None}
                store_cover(event_id, event.get('cover_image') if event else None)
            if data['status'] == 'published' and (not previous or previous['status'] != 'published'):
                for follower in query(
                    '''SELECT follower_id FROM organizer_follows WHERE organizer_id=%s''',
                    (g.user['id'],),
                ):
                    notify.notify(
                        app, query, follower['follower_id'], 'new_activity', 'Nouvelle activité',
                        f'Une personne que vous suivez propose « {data["title"]} ».',
                        f'/activities/{event_id}', dedupe_key=f'new_activity:{event_id}',
                    )
            elif previous and data['status'] == 'published':
                watched = ('title', 'description', 'location', 'starts_at', 'ends_at', 'price_cents', 'capacity', 'city')
                if any(key in data and data[key] != previous.get(key) for key in watched):
                    for person in query(
                        '''SELECT u.id, u.email FROM reservations r JOIN users u ON u.id=r.member_id
                           WHERE r.event_id=%s AND r.status='confirmed' ''',
                        (event_id,),
                    ):
                        notify.notify(
                            app, query, person['id'], 'event_changed', 'Activité modifiée',
                            f'« {data["title"]} » a été mise à jour.',
                            f'/activities/{event_id}', email=person['email'],
                        )
            flash('Activité enregistrée.', 'success')
            return redirect(url_for('organizer_activities'))
        return render_template('event_form.html', event=event, categories=query('SELECT * FROM categories ORDER BY name'), library=covers.library_tree())

    def store_cover(event_id, previous):
        uploaded = request.files.get('cover') if request.files else None
        if uploaded and uploaded.filename:
            name = covers.save_upload(app, event_id, uploaded, previous)
            db().execute('UPDATE events SET cover_image=%s WHERE id=%s', (name, event_id))
            return
        choice = request.form.get('cover_choice', '')
        if choice == 'auto':
            db().execute('UPDATE events SET cover_image=NULL WHERE id=%s', (event_id,))
            covers.delete_upload(app, previous)
        elif choice and covers.is_library_path(choice):
            db().execute('UPDATE events SET cover_image=%s WHERE id=%s', (choice, event_id))
            if previous and not str(previous).startswith('covers/'):
                covers.delete_upload(app, previous)

    @app.post('/organizer/<int:event_id>/cancel')
    @require('organizer')
    def cancel_event(event_id):
        with db().transaction():
            event = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s FOR UPDATE', (event_id, g.user['id']), True)
            if not event:
                abort(404)
            if event['starts_at'] <= datetime.now(timezone.utc):
                raise ValueError('Cette activité a déjà commencé.')
            people = query(
                '''SELECT u.id, u.email, e.price_cents FROM reservations r
                   JOIN users u ON u.id=r.member_id JOIN events e ON e.id=r.event_id
                   WHERE r.event_id=%s AND r.status='confirmed' ''',
                (event_id,),
            )
            db().execute("UPDATE events SET status='cancelled' WHERE id=%s", (event_id,))
            for person in people:
                cents = int(person['price_cents'] or 0)
                db().execute(
                    '''UPDATE reservations SET status='cancelled', cancelled_at=clock_timestamp(),
                       refund_cents=%s, refund_status=%s,
                       refunded_at=CASE WHEN %s > 0 THEN clock_timestamp() ELSE NULL END
                       WHERE member_id=%s AND event_id=%s AND status='confirmed' ''',
                    (cents, 'simulated' if cents else 'none', cents, person['id'], event_id),
                )
        for person in people:
            euros = f'{int(person["price_cents"] or 0) // 100},{int(person["price_cents"] or 0) % 100:02d} €'
            notify.notify(
                app, query, person['id'], 'event_cancelled', 'Activité annulée',
                f'« {event["title"]} » est annulée. Remboursement simulé : {euros}. Votre billet n’est plus valable.',
                f'/activities/{event_id}', dedupe_key=f'cancelled:{event_id}:{person["id"]}', email=person['email'],
            )
        flash('Activité et inscriptions annulées.', 'success')
        return redirect(url_for('organizer_activities'))

    @app.get('/organizer/<int:event_id>/participants')
    @require('organizer')
    def participants(event_id):
        event = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s', (event_id, g.user['id']), True)
        if not event:
            abort(404)
        people = query(
            '''SELECT u.id, u.display_name, u.avatar_path, r.reserved_at, t.checked_in_at
               FROM reservations r JOIN users u ON u.id=r.member_id
               LEFT JOIN tickets t ON t.reservation_id=r.id
               WHERE r.event_id=%s AND r.status='confirmed' ORDER BY r.reserved_at''',
            (event_id,),
        )
        checked = sum(1 for person in people if person['checked_in_at'])
        return render_template('participants.html', event=event, people=people, checked=checked)

    @app.get('/faq')
    def faq():
        return render_template('faq.html', faqs=query('SELECT * FROM faqs WHERE published ORDER BY sort_order,id'))

    @app.get('/legal/<kind>')
    def legal(kind):
        if kind not in LEGAL_TITLES:
            abort(404)
        page = query('SELECT * FROM legal_pages WHERE kind=%s AND published_at IS NOT NULL ORDER BY version DESC LIMIT 1', (kind,), True)
        if page and any(marker in page['content'] for marker in (
            'Document de démonstration', 'à renseigner', 'restent à renseigner', 'Prototype pédagogique Joinly',
        )):
            page = None
        content = page['content'] if page else LEGAL_TEXTS[kind]
        return render_template('legal.html', page=page, kind=kind, content=content)

    @app.get('/privacy')
    def privacy_redirect():
        return redirect(url_for('legal', kind='privacy'), code=301)

    @app.get('/robots.txt')
    def robots():
        base = public_base()
        body = (
            'User-agent: *\n'
            'Allow: /\n'
            'Disallow: /admin\n'
            'Disallow: /account\n'
            'Disallow: /notifications\n'
            'Disallow: /organizer\n'
            'Disallow: /reset-password/\n'
            'Disallow: /billets/\n'
            '\n'
            f'Sitemap: {base}/sitemap.xml\n'
        )
        return app.response_class(body, mimetype='text/plain; charset=utf-8')

    @app.get('/sitemap.xml')
    def sitemap():
        base = public_base()
        urls = [base + path for path in PUBLIC_PATHS]
        for row in query("SELECT id FROM events WHERE status='published' ORDER BY id"):
            urls.append(base + url_for('detail', event_id=row['id']))
        for row in query(
            '''SELECT DISTINCT u.id FROM users u
               JOIN user_roles ur ON ur.user_id=u.id
               JOIN roles r ON r.id=ur.role_id AND r.name='organizer'
               JOIN events e ON e.organizer_id=u.id AND e.status='published'
               WHERE u.status='active' ORDER BY u.id'''
        ):
            urls.append(base + url_for('organizer_public', user_id=row['id']))
        body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for loc in urls:
            body.append(f'  <url><loc>{xml_escape(loc)}</loc></url>')
        body.append('</urlset>')
        return app.response_class('\n'.join(body) + '\n', mimetype='application/xml; charset=utf-8')

    @app.get('/notifications')
    @require()
    def notifications():
        items = query(
            'SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 80',
            (g.user['id'],),
        )
        return render_template('notifications.html', items=items)

    @app.post('/notifications/lu')
    @require()
    def read_notifications():
        db().execute(
            'UPDATE notifications SET read_at=COALESCE(read_at, now()) WHERE user_id=%s',
            (g.user['id'],),
        )
        return redirect(url_for('notifications'))

    @app.get('/account/billets')
    @require()
    def tickets_page():
        rows = query(
            '''SELECT r.id, r.status, e.title, e.starts_at, e.location, t.id AS ticket_id, t.code, t.token, t.checked_in_at
               FROM reservations r JOIN events e ON e.id=r.event_id
               LEFT JOIN tickets t ON t.reservation_id=r.id
               WHERE r.member_id=%s ORDER BY e.starts_at DESC''',
            (g.user['id'],),
        )
        return render_template('tickets.html', rows=rows)

    @app.get('/billets/<int:ticket_id>/qr.png')
    @require()
    def ticket_qr(ticket_id):
        row = query(
            '''SELECT t.token, r.member_id, e.organizer_id
               FROM tickets t JOIN reservations r ON r.id=t.reservation_id
               JOIN events e ON e.id=r.event_id WHERE t.id=%s''',
            (ticket_id,), True,
        )
        if not row:
            abort(404)
        if row['member_id'] != g.user['id'] and row['organizer_id'] != g.user['id'] and 'admin' not in g.roles:
            abort(403)
        return app.response_class(qr_png(payload_for(row['token'], public_base())), mimetype='image/png')

    @app.get('/billets/<token>')
    def public_ticket(token):
        token = (token or '').strip()
        if len(token) < 32 or len(token) > 200:
            abort(404)
        row = query(
            "SELECT t.id, t.token, t.code, t.checked_in_at, r.status AS reservation_status,"
            " e.title, e.starts_at, e.location, e.price_cents, u.display_name AS organizer"
            " FROM tickets t"
            " JOIN reservations r ON r.id = t.reservation_id"
            " JOIN events e ON e.id = r.event_id"
            " JOIN users u ON u.id = e.organizer_id"
            " WHERE t.token=%s",
            (token,), True,
        )
        if not row:
            abort(404)
        return render_template(
            'ticket_public.html', ticket=row, event=row, organizer=row['organizer'],
            cancelled=row['reservation_status'] != 'confirmed',
        )

    @app.get('/billets/<token>/qr.png')
    def public_ticket_qr(token):
        token = (token or '').strip()
        if len(token) < 32 or len(token) > 200:
            abort(404)
        row = query(
            "SELECT t.token, r.status FROM tickets t"
            " JOIN reservations r ON r.id = t.reservation_id WHERE t.token=%s",
            (token,), True,
        )
        if not row or row['status'] != 'confirmed':
            abort(404)
        return app.response_class(qr_png(payload_for(row['token'], public_base())), mimetype='image/png')

    @app.route('/organizer/<int:event_id>/controle', methods=['GET', 'POST'])
    @require()
    def checkin(event_id):
        event = query('SELECT * FROM events WHERE id=%s', (event_id,), True)
        if not event:
            abort(404)
        allowed = ('admin' in g.roles) or ('organizer' in g.roles and event['organizer_id'] == g.user['id'])
        if not allowed:
            abort(403)
        result = None
        if request.method == 'POST' and request.form.get('undo'):
            ticket_id = request.form.get('ticket_id', '')
            if str(ticket_id).isdigit():
                db().execute(
                    '''UPDATE tickets SET checked_in_at=NULL, checked_in_by=NULL
                       WHERE id=%s AND reservation_id IN (SELECT id FROM reservations WHERE event_id=%s)''',
                    (int(ticket_id), event_id),
                )
            return redirect(url_for('checkin', event_id=event_id))
        if request.method == 'POST':
            raw = (request.form.get('code') or '').strip()
            if 'ticket=' in raw:
                raw = raw.split('ticket=', 1)[1].split('&', 1)[0]
            raw = raw[:200]
            with db().transaction():
                row = query(
                    '''SELECT t.id, t.checked_in_at, r.status AS reservation_status, r.event_id, u.display_name
                       FROM tickets t
                       JOIN reservations r ON r.id=t.reservation_id
                       JOIN users u ON u.id=r.member_id
                       WHERE t.token=%s OR upper(t.code)=upper(%s)
                       FOR UPDATE OF t''',
                    (raw, raw), True,
                )
                if not row:
                    result = {'kind': 'unknown', 'text': 'Billet inconnu.'}
                elif row['event_id'] != event_id:
                    result = {'kind': 'wrong', 'text': 'Ce billet n’est pas valable pour cette activité.'}
                elif row['reservation_status'] != 'confirmed':
                    result = {'kind': 'cancelled', 'text': 'Billet annulé.'}
                elif row['checked_in_at']:
                    result = {'kind': 'used', 'text': 'Déjà contrôlé.', 'name': row['display_name'], 'when': row['checked_in_at']}
                else:
                    checked = query(
                        '''UPDATE tickets SET checked_in_at=clock_timestamp(), checked_in_by=%s
                           WHERE id=%s AND checked_in_at IS NULL RETURNING checked_in_at''',
                        (g.user['id'], row['id']), True,
                    )
                    result = {'kind': 'ok', 'text': 'Entrée enregistrée.', 'name': row['display_name'], 'when': checked['checked_in_at'], 'ticket_id': row['id']}
        stats = query(
            '''SELECT count(*) FILTER (WHERE r.status='confirmed') AS confirmed,
                      count(*) FILTER (WHERE t.checked_in_at IS NOT NULL AND r.status='confirmed') AS checked
               FROM reservations r LEFT JOIN tickets t ON t.reservation_id=r.id WHERE r.event_id=%s''',
            (event_id,), True,
        )
        return render_template('checkin.html', event=event, result=result, stats=stats)

    @app.get('/activities/<int:event_id>/affiche.png')
    def poster(event_id):
        event = query(event_select + ' WHERE e.id=%s', (event_id,), True)
        if not event or (event['status'] == 'draft' and (not g.user or (event['organizer_id'] != g.user['id'] and 'admin' not in g.roles))):
            abort(404)
        covers.decorate([event])
        cover_file = None
        if event.get('cover_static'):
            candidate = covers.ROOT / 'app' / 'static' / event['cover_static']
            if candidate.is_file():
                cover_file = candidate
        elif event.get('cover_image'):
            candidate = covers.upload_dir(app) / str(event['cover_image'])
            if candidate.is_file():
                cover_file = candidate
        return app.response_class(
            render_poster(event, public_base() + url_for('detail', event_id=event_id), cover_file),
            mimetype='image/png',
        )

    @app.get('/favicon.ico')
    def favicon():
        return send_from_directory(app.static_folder, 'favicon.svg', mimetype='image/svg+xml')

    @app.get('/media/<filename>')
    def media(filename):
        if not re.fullmatch(r'e[0-9]+-[a-f0-9]{16}\.webp', filename):
            abort(404)
        directory = covers.upload_dir(app)
        path = (directory / filename).resolve()
        if path.parent != directory or not path.is_file():
            abort(404)
        return send_from_directory(directory, filename, mimetype='image/webp', max_age=86400)

    @app.get('/media/avatars/<filename>')
    def media_avatar(filename):
        if not avatars.AVATAR_RE.fullmatch(filename):
            abort(404)
        directory = avatars.avatar_dir(app)
        path = (directory / filename).resolve()
        if path.parent != directory or not path.is_file():
            abort(404)
        return send_from_directory(directory, filename, mimetype='image/webp', max_age=86400)

    @app.get('/admin/couvertures')
    @require('admin')
    def admin_covers():
        return render_template('admin_covers.html', library=covers.library_tree())

    @app.post('/admin/events/<int:event_id>/cover')
    @require('admin')
    def admin_event_cover(event_id):
        event = query('SELECT id, cover_image FROM events WHERE id=%s', (event_id,), True)
        if not event:
            abort(404)
        store_cover(event_id, event['cover_image'])
        flash('Image de couverture mise à jour.', 'success')
        return redirect(url_for('detail', event_id=event_id))

    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        if request.method == 'POST':
            rate_limit('contact', 5)
            db().execute('INSERT INTO contact_requests(name,email,subject,message) VALUES (%s,%s,%s,%s)', (text('name', 100), email_value(), text('subject', 180), text('message', 5000)))
            flash('Votre demande a été enregistrée. L’équipe peut la consulter dans son espace de gestion.', 'success')
            return redirect(url_for('contact'))
        return render_template('contact.html')

    @app.get('/admin')
    @require('admin')
    def admin():
        days = dashboards.period_days(request.args)
        payload = dashboards.admin_payload(query, days)
        return render_template('admin.html', users=query('''SELECT u.id,u.email,u.display_name,u.status,u.avatar_path,
            ARRAY(SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=u.id) AS roles
            FROM users u ORDER BY u.id'''), faqs=query('SELECT * FROM faqs ORDER BY sort_order,id'),
            pages=query('SELECT * FROM legal_pages ORDER BY kind,version DESC'), messages=query('SELECT * FROM contact_requests ORDER BY created_at DESC'),
            priced_events=query('''SELECT e.id, e.title, e.price_cents, e.starts_at, u.display_name AS organizer
                FROM events e JOIN users u ON u.id=e.organizer_id
                WHERE e.status <> 'cancelled' ORDER BY e.starts_at DESC LIMIT 40'''),
            reviews=query('''SELECT rv.*, u.display_name, e.title FROM reviews rv
                JOIN users u ON u.id=rv.author_id JOIN events e ON e.id=rv.event_id
                ORDER BY rv.created_at DESC LIMIT 40'''),
            refundable=query('''SELECT r.id, u.display_name, e.title, e.price_cents, r.refund_cents, r.refund_status
                FROM reservations r JOIN users u ON u.id=r.member_id JOIN events e ON e.id=r.event_id
                WHERE e.price_cents > 0 ORDER BY r.reserved_at DESC LIMIT 20'''),
            **payload)

    @app.post('/admin/events/<int:event_id>/price')
    @require('admin')
    def admin_event_price(event_id):
        cents = money_cents()
        if not query('SELECT id FROM events WHERE id=%s', (event_id,), True):
            abort(404)
        db().execute('UPDATE events SET price_cents=%s WHERE id=%s', (cents, event_id))
        flash('Prix mis à jour.', 'success')
        return redirect(url_for('admin') + '#tarifs')

    @app.post('/admin/reservations/<int:booking_id>/remboursement')
    @require('admin')
    def admin_manual_refund(booking_id):
        if request.form.get('confirm') != '1':
            raise ValueError('Confirmez le remboursement simulé.')
        cents = money_cents('refund')
        booking = query(
            '''SELECT r.id, e.price_cents FROM reservations r JOIN events e ON e.id=r.event_id WHERE r.id=%s''',
            (booking_id,), True,
        )
        if not booking:
            abort(404)
        if cents > int(booking['price_cents'] or 0):
            raise ValueError('Le remboursement ne peut pas dépasser le prix.')
        if cents == 0:
            db().execute(
                "UPDATE reservations SET refund_cents=0, refund_status='none', refunded_at=NULL WHERE id=%s",
                (booking_id,),
            )
        else:
            db().execute(
                '''UPDATE reservations SET refund_cents=%s, refund_status='manual', refunded_at=clock_timestamp()
                   WHERE id=%s''',
                (cents, booking_id),
            )
        flash('Remboursement simulé enregistré.', 'success')
        return redirect(url_for('admin') + '#remboursements')

    @app.post('/admin/events/<int:event_id>/dates')
    @require('admin')
    def admin_event_dates(event_id):
        if not query('SELECT id FROM events WHERE id=%s', (event_id,), True):
            abort(404)
        try:
            starts = datetime.fromisoformat(text('starts_at')).replace(tzinfo=PARIS)
            ends = datetime.fromisoformat(text('ends_at')).replace(tzinfo=PARIS)
        except ValueError:
            raise ValueError('Vérifiez les dates.')
        for instant in (starts, ends):
            if instant.astimezone(timezone.utc).astimezone(PARIS).replace(tzinfo=None) != instant.replace(tzinfo=None):
                raise ValueError('Cette heure n’existe pas lors du changement d’heure.')
        if ends <= starts:
            raise ValueError('La fin doit être après le début.')
        db().execute('UPDATE events SET starts_at=%s, ends_at=%s WHERE id=%s', (starts, ends, event_id))
        flash('Dates corrigées.', 'success')
        return redirect(url_for('detail', event_id=event_id))

    @app.post('/admin/reviews/<int:review_id>')
    @require('admin')
    def admin_review(review_id):
        if not query('SELECT id FROM reviews WHERE id=%s', (review_id,), True):
            abort(404)
        db().execute('UPDATE reviews SET hidden=%s WHERE id=%s', ('hidden' in request.form, review_id))
        flash('Avis modéré.', 'success')
        return redirect(url_for('admin') + '#avis')

    @app.post('/admin/users/<int:user_id>')
    @require('admin')
    def admin_user(user_id):
        roles = set(request.form.getlist('roles'))
        status = text('status')
        if not roles <= {'member', 'organizer', 'admin'} or status not in ('active', 'suspended'):
            abort(400)
        if user_id == g.user['id']:
            raise ValueError('Vous ne pouvez pas modifier vos propres droits ou suspendre votre compte.')
        with db().transaction():
            db().execute('SELECT pg_advisory_xact_lock(2002)')
            if not query("SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=%s AND r.name='admin'", (g.user['id'],), True):
                abort(403)
            if not query('SELECT id FROM users WHERE id=%s FOR UPDATE', (user_id,), True):
                abort(404)
            db().execute('UPDATE users SET status=%s WHERE id=%s', (status, user_id))
            db().execute('DELETE FROM user_roles WHERE user_id=%s', (user_id,))
            db().execute('INSERT INTO user_roles(user_id,role_id) SELECT %s,id FROM roles WHERE name=ANY(%s)', (user_id, list(roles | {'member'})))
            db().execute('DELETE FROM web_sessions WHERE user_id=%s', (user_id,))
        flash('Compte mis à jour ; ses sessions ont été révoquées.', 'success')
        return redirect(url_for('admin'))

    @app.post('/admin/users/<int:user_id>/avatar')
    @require('admin')
    def admin_remove_avatar(user_id):
        person = query('SELECT id, avatar_path FROM users WHERE id=%s', (user_id,), True)
        if not person:
            abort(404)
        db().execute('UPDATE users SET avatar_path=NULL WHERE id=%s', (user_id,))
        avatars.delete_avatar(app, person['avatar_path'])
        flash('Photo de profil retirée.', 'success')
        return redirect(url_for('admin_user_detail', user_id=user_id))

    @app.post('/admin/faq')
    @require('admin')
    def admin_faq():
        order = int(text('sort_order'))
        if not -1000000 <= order <= 1000000:
            raise ValueError('Ordre de tri invalide.')
        values = (text('question', 500), text('answer', 10000), order, 'published' in request.form)
        faq_id = request.form.get('id')
        if faq_id:
            db().execute('UPDATE faqs SET question=%s,answer=%s,sort_order=%s,published=%s WHERE id=%s', (*values, int(faq_id)))
        else:
            db().execute('INSERT INTO faqs(question,answer,sort_order,published) VALUES (%s,%s,%s,%s)', values)
        flash('FAQ enregistrée.', 'success')
        return redirect(url_for('admin'))

    @app.post('/admin/legal')
    @require('admin')
    def admin_legal():
        kind = text('kind')
        if kind not in LEGAL_TITLES:
            abort(400)
        content = text('content', 30000)
        with db().transaction():
            db().execute('SELECT pg_advisory_xact_lock(2001)')
            version = query('SELECT coalesce(max(version),0)+1 AS n FROM legal_pages WHERE kind=%s', (kind,), True)['n']
            db().execute('INSERT INTO legal_pages(kind,version,content,published_at) VALUES (%s,%s,%s,now())', (kind, version, content))
        flash('Nouvelle version publiée.', 'success')
        return redirect(url_for('admin'))

    @app.post('/admin/contact/<int:message_id>')
    @require('admin')
    def resolve_contact(message_id):
        db().execute('UPDATE contact_requests SET resolved=%s WHERE id=%s', ('resolved' in request.form, message_id))
        return redirect(url_for('admin'))

    @app.route('/forgot-password', methods=['GET', 'POST'])
    def forgot_password():
        configured = bool(os.environ.get('SMTP_HOST') and os.environ.get('MAIL_FROM') and os.environ.get('PUBLIC_BASE_URL'))
        if request.method == 'POST':
            if not configured:
                raise ValueError('L’envoi d’e-mails n’est pas encore configuré. Contactez l’équipe.')
            rate_limit('reset', 5)
            user = query("SELECT id FROM users WHERE email=%s AND status='active'", (email_value(),), True)
            if user:
                token = secrets.token_urlsafe(32)
                with db().transaction():
                    db().execute('SELECT id FROM users WHERE id=%s FOR UPDATE', (user['id'],))
                    db().execute('DELETE FROM password_resets WHERE user_id=%s', (user['id'],))
                    db().execute("INSERT INTO password_resets VALUES (%s,%s,now()+interval '30 minutes')", (digest(token), user['id']))
                message = EmailMessage()
                message['Subject'] = 'Réinitialiser votre mot de passe Joinly'
                message['From'] = os.environ['MAIL_FROM']
                message['To'] = email_value()
                message.set_content('Votre lien valable 30 minutes : ' + os.environ['PUBLIC_BASE_URL'].rstrip('/') + url_for('reset_password', token=token))
                try:
                    with smtplib.SMTP(os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT', '587')), timeout=10) as smtp:
                        smtp.starttls(context=ssl.create_default_context())
                        if os.environ.get('SMTP_USER'):
                            smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                        smtp.send_message(message)
                except (OSError, smtplib.SMTPException):
                    app.logger.error('Password reset delivery failed')
            flash('Si ce compte est actif, un lien de réinitialisation sera envoyé.', 'success')
            return redirect(url_for('login'))
        return render_template('auth.html', mode='forgot', configured=configured)

    @app.route('/reset-password/<token>', methods=['GET', 'POST'])
    def reset_password(token):
        if not query('SELECT user_id FROM password_resets WHERE token_hash=%s AND expires_at>now()', (digest(token),), True):
            raise ValueError('Ce lien a expiré ou a déjà été utilisé.')
        if request.method == 'POST':
            hashed = generate_password_hash(password_value())
            with db().transaction():
                reset = query('DELETE FROM password_resets WHERE token_hash=%s AND expires_at>now() RETURNING user_id', (digest(token),), True)
                if not reset:
                    raise ValueError('Ce lien a expiré ou a déjà été utilisé.')
                db().execute('UPDATE users SET password_hash=%s WHERE id=%s', (hashed, reset['user_id']))
                db().execute('DELETE FROM web_sessions WHERE user_id=%s', (reset['user_id'],))
            session.clear()
            flash('Mot de passe changé. Connectez-vous à nouveau.', 'success')
            return redirect(url_for('login'))
        return render_template('auth.html', mode='reset')

    @app.get('/index.html')
    @app.get('/joinly_front/index.html')
    def legacy_home():
        return redirect(url_for('home'), code=301)

    @app.get('/joinly_front/activites.html')
    def legacy_activities():
        return redirect(url_for('activities'), code=301)

    @app.get('/health')
    def health():
        query('SELECT 1', one=True)
        return {'status': 'ok'}

    @app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.option('--name', prompt=True)
    @click.password_option(confirmation_prompt=True)
    def create_admin(email, name, password):
        email = email.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or not 12 <= len(password) <= 128:
            raise click.ClickException('Invalid email or password (12–128 characters).')
        with db().transaction():
            user = query('INSERT INTO users(email,display_name,password_hash,email_verified_at) VALUES (%s,%s,%s,now()) RETURNING id', (email, name, generate_password_hash(password)), True)
            db().execute('INSERT INTO user_roles(user_id,role_id) SELECT %s,id FROM roles', (user['id'],))
        click.echo('Administrator created.')

    @app.cli.command('cleanup')
    def cleanup():
        for table in ('web_sessions', 'password_resets', 'rate_limits'):
            db().execute(f'DELETE FROM {table} WHERE expires_at<now()')
        db().execute("DELETE FROM assistant_booking_requests WHERE expires_at<now()-interval '30 days'")
        db().execute("DELETE FROM mcp_tokens WHERE expires_at<now()-interval '30 days' OR revoked_at<now()-interval '30 days'")
        click.echo('Expired sessions, tokens, proposals and rate limits removed.')

    @app.cli.command('seed-demo')
    def seed_demo_command():
        """Insert idempotent demonstration accounts, activities and registrations."""
        from app.seed_demo import seed_demo
        try:
            stats = seed_demo(db())
        except RuntimeError as error:
            raise click.ClickException(str(error))
        click.echo(
            'Demonstration data ready: '
            f"{stats['users_created']} new accounts, "
            f"{stats['events_created']} new activities, "
            f"{stats['bookings_created']} new registrations "
            f"({stats['demo_users']} demo accounts, {stats['demo_events']} demo activities in total)."
        )
        click.echo('Credentials: docs/demo-accounts.md')

    @app.cli.command('send-reminders')
    def send_reminders():
        """Email and notify confirmed attendees whose activity starts within 24 hours."""
        count = notify.send_reminders(app, query, db)
        click.echo(f'Reminders sent: {count}')

    from app.admin_office import register_office
    register_office(app, query, db, text, email_value, money_cents)

    from app.chatbot import register as register_chatbot
    from app.assistant_tools import ToolService
    assistant_tools = ToolService(query, db, cutoff_minutes)
    from app.mcp_server import register as register_mcp
    register_mcp(app, query, db, assistant_tools, send_booking_notification)
    register_chatbot(app, query, db, cutoff_minutes, assistant_tools)

    return app
