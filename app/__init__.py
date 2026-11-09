import hashlib
import os
import re
import secrets
import smtplib
import ssl
import unicodedata
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
from zoneinfo import ZoneInfo

import click
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from flask import Flask, abort, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from flask_wtf.csrf import CSRFProtect, CSRFError
from markupsafe import Markup, escape as html_escape
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from app.legal_content import LEGAL_TEXTS

PARIS = ZoneInfo('Europe/Paris')
ROOT = Path(__file__).resolve().parents[1]
DUMMY_HASH = generate_password_hash('not-a-user-password')
MONTHS_FR = ('janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.')
LEGAL_TITLES = {
    'terms': 'Conditions d’utilisation',
    'legal_notice': 'Mentions légales',
    'privacy': 'Politique de confidentialité',
}
PUBLIC_PATHS = ('/', '/activities', '/faq', '/contact', '/legal/terms', '/legal/legal_notice', '/legal/privacy')


def create_app(config=None):
    load_dotenv(ROOT / '.env')
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        DATABASE=os.environ.get('PGDATABASE', 'joinly'),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE', '0') == '1',
        MAX_CONTENT_LENGTH=64 * 1024,
        TRUST_PROXY=os.environ.get('TRUST_PROXY', '0') == '1',
        TRUSTED_HOSTS=[host.strip() for host in os.environ.get('TRUSTED_HOSTS', '').split(',') if host.strip()] or None,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        WTF_CSRF_TIME_LIMIT=43200,
        PUBLIC_BASE_URL=os.environ.get('PUBLIC_BASE_URL', '').strip().rstrip('/'),
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
        token = session.get('auth_token')
        if token:
            g.user = query('''SELECT u.id, u.email, u.display_name, u.status FROM users u
                JOIN web_sessions s ON s.user_id=u.id
                WHERE s.token_hash=%s AND s.expires_at>now() AND u.status='active' ''', (digest(token),), True)
            if g.user:
                g.roles = {r['name'] for r in query('SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=%s', (g.user['id'],))}
            else:
                session.clear()

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
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

    @app.context_processor
    def context():
        base = public_base()
        return {
            'now': datetime.now(timezone.utc),
            'public_base_url': base,
            'canonical_url': base + request.path,
            'og_image': base + url_for('static', filename='logo.png'),
            'legal_titles': LEGAL_TITLES,
        }

    event_select = '''SELECT e.*, u.display_name AS organizer, c.name AS category,
        e.capacity-(SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') AS available
        FROM events e JOIN users u ON u.id=e.organizer_id LEFT JOIN categories c ON c.id=e.category_id'''

    def catalogue(limit=60):
        filters = ["e.status='published'", 'e.starts_at>now()']
        args = []
        for field, clause in [('q', '(e.title ILIKE %s OR e.description ILIKE %s)'), ('location', 'e.location ILIKE %s')]:
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
        page = request.args.get('page', '1')
        if not page.isdigit() or not 1 <= int(page) <= 10000:
            raise ValueError('Page invalide.')
        return query(event_select + ' WHERE ' + ' AND '.join(filters) + ' ORDER BY e.starts_at,e.id LIMIT %s OFFSET %s', (*args, limit, (int(page)-1)*limit))

    @app.get('/')
    def home():
        return render_template('home.html', events=catalogue(6))

    @app.get('/activities')
    def activities():
        return render_template('activities.html', events=catalogue(), categories=query('SELECT * FROM categories ORDER BY name'))

    @app.get('/activities/<int:event_id>')
    def detail(event_id):
        event = query(event_select + ' WHERE e.id=%s', (event_id,), True)
        if not event or (event['status'] == 'draft' and (not g.user or event['organizer_id'] != g.user['id'])):
            abort(404)
        booking = query("SELECT * FROM reservations WHERE event_id=%s AND member_id=%s AND status='confirmed'", (event_id, g.user['id']), True) if g.user else None
        return render_template('detail.html', event=event, booking=booking)

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
                db().execute('INSERT INTO member_preferences(user_id) VALUES (%s)', (user['id'],))
            flash('Compte créé. Vous pouvez vous connecter.', 'success')
            return redirect(url_for('login'))
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
            token = secrets.token_urlsafe(32)
            session.clear()
            session.permanent = True
            session['auth_token'] = token
            db().execute('INSERT INTO web_sessions(token_hash,user_id,expires_at) VALUES (%s,%s,now()+interval \'12 hours\')', (digest(token), user['id']))
            return redirect(url_for('account'))
        return render_template('auth.html', mode='login')

    @app.post('/logout')
    def logout():
        if session.get('auth_token'):
            db().execute('DELETE FROM web_sessions WHERE token_hash=%s', (digest(session['auth_token']),))
        session.clear()
        return redirect(url_for('home'))

    @app.route('/account', methods=['GET', 'POST'])
    @require()
    def account():
        if request.method == 'POST':
            name = text('display_name', 100)
            interests = [s.strip() for s in text('interests', 500, False).split(',') if s.strip()]
            with db().transaction():
                db().execute('UPDATE users SET display_name=%s WHERE id=%s', (name, g.user['id']))
                db().execute('''INSERT INTO member_preferences(user_id,interests,chosen_area,assistant_consent) VALUES (%s,%s,%s,%s)
                    ON CONFLICT(user_id) DO UPDATE SET interests=EXCLUDED.interests, chosen_area=EXCLUDED.chosen_area, assistant_consent=EXCLUDED.assistant_consent''',
                    (g.user['id'], interests, text('chosen_area', 150, False), 'assistant_consent' in request.form))
            flash('Profil enregistré.', 'success')
            return redirect(url_for('account'))
        prefs = query('SELECT * FROM member_preferences WHERE user_id=%s', (g.user['id'],), True)
        bookings = query('''SELECT r.*, e.title,e.starts_at,e.location FROM reservations r JOIN events e ON e.id=r.event_id
            WHERE r.member_id=%s ORDER BY e.starts_at DESC''', (g.user['id'],))
        return render_template('account.html', preferences=prefs, bookings=bookings)

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

    @app.post('/activities/<int:event_id>/reserve')
    @require()
    def reserve(event_id):
        with db().transaction():
            event = query('SELECT * FROM events WHERE id=%s FOR UPDATE', (event_id,), True)
            if not event:
                abort(404)
            count = query("SELECT count(*) AS n FROM reservations WHERE event_id=%s AND status='confirmed'", (event_id,), True)['n']
            if event['status'] != 'published' or event['starts_at'] <= datetime.now(timezone.utc) or count >= event['capacity']:
                raise ValueError('Cette activité n’a plus de place disponible ou les inscriptions sont fermées.')
            db().execute('INSERT INTO reservations(member_id,event_id) VALUES (%s,%s)', (g.user['id'], event_id))
        flash('Votre place est réservée ! Retrouvez-la dans votre espace.', 'success')
        return redirect(url_for('account'))

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
            db().execute("UPDATE reservations SET status='cancelled',cancelled_at=clock_timestamp() WHERE id=%s AND status='confirmed'", (booking_id,))
        flash('Réservation annulée.', 'success')
        return redirect(url_for('account'))

    @app.get('/organizer')
    @require('organizer')
    def organizer():
        return render_template('organizer.html', events=query(event_select + ' WHERE e.organizer_id=%s ORDER BY e.starts_at DESC', (g.user['id'],)))

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
        return dict(title=text('title', 180), description=text('description', 10000), location=text('location', 200), starts_at=starts, ends_at=ends, capacity=capacity, category_id=category_id, status=status)

    @app.route('/organizer/new', methods=['GET', 'POST'])
    @app.route('/organizer/<int:event_id>/edit', methods=['GET', 'POST'])
    @require('organizer')
    def edit_event(event_id=None):
        event = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s', (event_id, g.user['id']), True) if event_id else None
        if event_id and not event:
            abort(404)
        if request.method == 'POST':
            data = event_data()
            with db().transaction():
                if event_id:
                    event = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s FOR UPDATE', (event_id, g.user['id']), True)
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
                    db().execute(f'INSERT INTO events(organizer_id,{columns}) VALUES (%s,{placeholders})', (g.user['id'], *data.values()))
            flash('Activité enregistrée.', 'success')
            return redirect(url_for('organizer'))
        return render_template('event_form.html', event=event, categories=query('SELECT * FROM categories ORDER BY name'))

    @app.post('/organizer/<int:event_id>/cancel')
    @require('organizer')
    def cancel_event(event_id):
        with db().transaction():
            event = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s FOR UPDATE', (event_id, g.user['id']), True)
            if not event:
                abort(404)
            if event['starts_at'] <= datetime.now(timezone.utc):
                raise ValueError('Cette activité a déjà commencé.')
            db().execute("UPDATE events SET status='cancelled' WHERE id=%s", (event_id,))
            db().execute("UPDATE reservations SET status='cancelled',cancelled_at=clock_timestamp() WHERE event_id=%s AND status='confirmed'", (event_id,))
        flash('Activité et inscriptions annulées.', 'success')
        return redirect(url_for('organizer'))

    @app.get('/organizer/<int:event_id>/participants')
    @require('organizer')
    def participants(event_id):
        event = query('SELECT * FROM events WHERE id=%s AND organizer_id=%s', (event_id, g.user['id']), True)
        if not event:
            abort(404)
        people = query("SELECT u.display_name,r.reserved_at FROM reservations r JOIN users u ON u.id=r.member_id WHERE r.event_id=%s AND r.status='confirmed' ORDER BY r.reserved_at", (event_id,))
        return render_template('participants.html', event=event, people=people)

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
            'Disallow: /organizer\n'
            'Disallow: /reset-password/\n'
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
        body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for loc in urls:
            body.append(f'  <url><loc>{xml_escape(loc)}</loc></url>')
        body.append('</urlset>')
        return app.response_class('\n'.join(body) + '\n', mimetype='application/xml; charset=utf-8')

    @app.get('/favicon.ico')
    def favicon():
        return send_from_directory(app.static_folder, 'favicon.svg', mimetype='image/svg+xml')

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
        return render_template('admin.html', users=query('''SELECT u.id,u.email,u.display_name,u.status,
            ARRAY(SELECT r.name FROM roles r JOIN user_roles ur ON ur.role_id=r.id WHERE ur.user_id=u.id) AS roles
            FROM users u ORDER BY u.id'''), faqs=query('SELECT * FROM faqs ORDER BY sort_order,id'),
            pages=query('SELECT * FROM legal_pages ORDER BY kind,version DESC'), messages=query('SELECT * FROM contact_requests ORDER BY created_at DESC'))

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
            user = query('INSERT INTO users(email,display_name,password_hash) VALUES (%s,%s,%s) RETURNING id', (email, name, generate_password_hash(password)), True)
            db().execute('INSERT INTO user_roles(user_id,role_id) SELECT %s,id FROM roles', (user['id'],))
        click.echo('Administrator created.')

    @app.cli.command('cleanup')
    def cleanup():
        for table in ('web_sessions', 'password_resets', 'rate_limits'):
            db().execute(f'DELETE FROM {table} WHERE expires_at<now()')
        click.echo('Expired sessions, tokens and rate limits removed.')

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

    return app
