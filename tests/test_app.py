import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash
from app import create_app

PASSWORD = 'A sufficiently long test password'

@pytest.fixture()
def app():
    application = create_app({'TESTING': True, 'DATABASE': 'joinly_test', 'SECRET_KEY': 'test-secret-not-for-deployment', 'WTF_CSRF_ENABLED': False})
    with psycopg.connect(dbname='joinly_test', autocommit=True) as db:
        db.execute('TRUNCATE users,events,categories,faqs,legal_pages,contact_requests,rate_limits,user_interests,dev_outbox CASCADE')
    return application

@pytest.fixture()
def db(app):
    with psycopg.connect(dbname='joinly_test', row_factory=dict_row, autocommit=True) as connection:
        yield connection


def ensure_categories(db):
    samples = (('Cuisine', '🍳'), ('Musique', '🎵'), ('Sport', '🏃'), ('Photo', '📸'))
    ids = []
    for name, icon in samples:
        ids.append(db.execute(
            '''INSERT INTO categories(name, icon) VALUES (%s, %s)
               ON CONFLICT (name) DO UPDATE SET icon=EXCLUDED.icon RETURNING id''',
            (name, icon),
        ).fetchone()['id'])
    return ids


def user(db, email='member@example.test', roles=('member',), interests=None):
    result = db.execute('INSERT INTO users(email,display_name,password_hash,email_verified_at) VALUES (%s,%s,%s,now()) RETURNING id', (email, email.split('@')[0], generate_password_hash(PASSWORD))).fetchone()['id']
    db.execute('INSERT INTO user_roles SELECT %s,id FROM roles WHERE name=ANY(%s)', (result,list(roles)))
    if interests is None:
        interests = 'admin' not in roles
    if interests:
        for category_id in ensure_categories(db)[:3]:
            db.execute('INSERT INTO user_interests(user_id, category_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (result, category_id))
    return result


def login(app, email='member@example.test'):
    client = app.test_client()
    assert client.post('/login', data={'email': email,'password': PASSWORD}).status_code == 302
    return client


def event(db, owner, capacity=1, status='published'):
    category = db.execute("INSERT INTO categories(name) VALUES ('Nature') ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING id").fetchone()['id']
    return db.execute("""INSERT INTO events(organizer_id,category_id,title,description,location,starts_at,ends_at,capacity,status)
        VALUES (%s,%s,'Balade','Au bord du fleuve','Paris',now()+interval '2 days',now()+interval '2 days 2 hours',%s,%s) RETURNING id""", (owner,category,capacity,status)).fetchone()['id']


def event_form(db, event_id, **changes):
    row = db.execute('SELECT * FROM events WHERE id=%s', (event_id,)).fetchone()
    form = {key: str(row[key]) for key in ('title','description','location','capacity','status','category_id')}
    for field in ('starts_at','ends_at'):
        form[field] = row[field].astimezone(ZoneInfo('Europe/Paris')).isoformat(timespec='microseconds').split('+')[0]
    cents = row['price_cents']
    form['price'] = f'{cents // 100},{cents % 100:02d}'
    form.update(changes)
    return form


def test_public_pages(app):
    client = app.test_client()
    for path in ['/', '/activities', '/classement', '/faq','/contact','/login','/signup','/legal/terms','/legal/legal_notice','/forgot-password','/health']:
        assert client.get(path).status_code == 200, path
    assert client.get('/missing').status_code == 404


def test_signup_roles_duplicates_and_password(app, db):
    client = app.test_client()
    form = {'email':'  NEW@Example.test ', 'display_name':'New', 'password':PASSWORD, 'role':'organizer'}
    assert client.post('/signup', data={**form, 'password':'short'}).status_code == 400
    assert client.post('/signup', data={**form, 'role':'admin'}).status_code == 400
    assert client.post('/signup', data=form).status_code == 302
    row = db.execute("SELECT * FROM users WHERE email='new@example.test'").fetchone()
    assert row['password_hash'] != PASSWORD and row['email_verified_at'] is None
    roles = db.execute('SELECT r.name FROM roles r JOIN user_roles ur ON r.id=ur.role_id WHERE user_id=%s',(row['id'],)).fetchall()
    assert {r['name'] for r in roles} == {'member','organizer'}
    assert db.execute('SELECT count(*) AS n FROM user_interests WHERE user_id=%s', (row['id'],)).fetchone()['n'] == 0
    assert client.post('/signup', data=form).status_code == 409
    mail = db.execute("SELECT body FROM dev_outbox WHERE recipient='new@example.test' ORDER BY id DESC LIMIT 1").fetchone()
    code = re.search(r'\b(\d{6})\b', mail['body']).group(1)
    assert client.post('/verifier-email', data={'email': 'new@example.test', 'code': '000000'}).status_code == 400
    assert client.post('/verifier-email', data={'email': 'new@example.test', 'code': code}).status_code == 302
    assert client.get('/interests').status_code == 200
    assert db.execute("SELECT email_verified_at FROM users WHERE email='new@example.test'").fetchone()['email_verified_at']


def test_verification_code_expires_attempts_and_blocks_login(app, db):
    client = app.test_client()
    form = {'email': 'wait@example.test', 'display_name': 'Wait', 'password': PASSWORD, 'role': 'member'}
    assert client.post('/signup', data=form).status_code == 302
    assert client.post('/login', data={'email': 'wait@example.test', 'password': PASSWORD}).status_code == 302
    assert client.get('/account').status_code == 302
    assert client.post('/verifier-email/renvoyer', data={'email': 'wait@example.test'}).status_code == 400
    db.execute("UPDATE email_verifications SET last_sent_at=now()-interval '2 minutes' WHERE user_id=(SELECT id FROM users WHERE email='wait@example.test')")
    assert client.post('/verifier-email/renvoyer', data={'email': 'wait@example.test'}).status_code == 302
    for _ in range(5):
        assert client.post('/verifier-email', data={'email': 'wait@example.test', 'code': '111111'}).status_code == 400
    body = db.execute("SELECT body FROM dev_outbox WHERE recipient='wait@example.test' ORDER BY id DESC LIMIT 1").fetchone()['body']
    code = re.search(r'\b(\d{6})\b', body).group(1)
    assert client.post('/verifier-email', data={'email': 'wait@example.test', 'code': code}).status_code == 400


def test_session_logout_and_suspend(app, db):
    member = user(db)
    client = login(app)
    assert client.get('/account').status_code == 200
    token = client.get_cookie('session').value
    client.post('/logout')
    client.set_cookie('session',token)
    assert client.get('/account').status_code == 302
    client = login(app)
    db.execute("UPDATE users SET status='suspended' WHERE id=%s",(member,))
    assert client.get('/account').status_code == 302
    assert client.post('/login',data={'email':'member@example.test','password':PASSWORD}).status_code == 401


def test_csrf_and_headers(app):
    app.config['WTF_CSRF_ENABLED'] = True
    client = app.test_client()
    assert client.post('/contact',data={}).status_code == 400
    response = client.get('/contact')
    token = re.search(r'name="csrf_token" value="([^"]+)"',response.text).group(1)
    assert client.post('/contact',data={'csrf_token':token,'name':'Test','email':'test@example.test','subject':'Question','message':'Hello'}).status_code == 302
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['Cache-Control'] == 'no-store'


def test_profile_saved_and_cannot_grant_admin(app, db):
    uid = user(db)
    client = login(app)
    ids = [str(row['id']) for row in db.execute('SELECT id FROM categories ORDER BY id').fetchall()]
    assert client.post('/account',data={'display_name':'<script>alert(1)</script>','interest_ids':ids[:1],'chosen_area':'Paris','roles':'admin'}).status_code == 400
    assert client.post('/account',data={'display_name':'<script>alert(1)</script>','interest_ids':ids[:3],'chosen_area':'Paris','roles':'admin'}).status_code == 302
    html = client.get('/account').text
    assert '&lt;script&gt;' in html and '<script>alert' not in html
    assert client.get('/admin').status_code == 403
    assert db.execute('SELECT assistant_consent FROM member_preferences WHERE user_id=%s',(uid,)).fetchone()['assistant_consent'] is False
    assert db.execute('SELECT count(*) AS n FROM user_interests WHERE user_id=%s', (uid,)).fetchone()['n'] == 3


def test_catalogue_filters_and_private_drafts(app, db):
    owner = user(db, roles=('member','organizer'))
    public = event(db,owner)
    draft = event(db,owner,status='draft')
    client = app.test_client()
    assert 'Balade' in client.get('/activities?q=FLEUVE&location=paris').text
    assert 'Balade' not in client.get('/activities?q=unknown').text
    assert client.get(f'/activities/{draft}').status_code == 404
    assert client.get(f'/activities/{public}').status_code == 200
    assert client.get('/activities?from=invalid').status_code == 400


def test_booking_cancel_rebook_and_ownership(app, db):
    uid = user(db)
    other = user(db,'other@example.test')
    eid = event(db,uid,2)
    client = login(app)
    assert client.post(f'/activities/{eid}/reserve').status_code == 302
    assert client.post(f'/activities/{eid}/reserve').status_code == 409
    bid = db.execute('SELECT id FROM reservations WHERE member_id=%s',(uid,)).fetchone()['id']
    assert login(app,'other@example.test').post(f'/reservations/{bid}/cancel').status_code == 404
    assert client.post(f'/reservations/{bid}/cancel').status_code == 302
    assert client.post(f'/reservations/{bid}/cancel').status_code == 302
    assert client.post(f'/activities/{eid}/reserve').status_code == 302
    assert db.execute("SELECT count(*) AS n FROM reservations WHERE status='confirmed'").fetchone()['n'] == 1


def test_last_place_concurrency(app, db):
    owner = user(db)
    user(db,'second@example.test')
    eid = event(db,owner,1)
    clients = [login(app), login(app,'second@example.test')]
    barrier = Barrier(2)
    def reserve(client):
        barrier.wait(timeout=5)
        return client.post(f'/activities/{eid}/reserve').status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, clients))
    assert sorted(results) == [302,400]
    assert db.execute("SELECT count(*) AS n FROM reservations WHERE event_id=%s AND status='confirmed'",(eid,)).fetchone()['n'] == 1


def test_organizer_permissions_and_lifecycle(app, db):
    owner = user(db,roles=('member','organizer'))
    user(db,'stranger@example.test',roles=('member','organizer'))
    eid = event(db,owner,2)
    client = login(app)
    stranger = login(app,'stranger@example.test')
    assert stranger.get(f'/organizer/{eid}/participants').status_code == 404
    assert stranger.post(f'/organizer/{eid}/cancel').status_code == 404
    assert stranger.post(f'/organizer/{eid}/edit',data=event_form(db,eid)).status_code == 404
    assert client.post(f'/activities/{eid}/reserve').status_code == 302
    assert client.post(f'/organizer/{eid}/edit',data=event_form(db,eid,location='Lyon')).status_code == 400
    assert client.post(f'/organizer/{eid}/edit',data=event_form(db,eid,capacity='0')).status_code == 400
    assert client.post(f'/organizer/{eid}/edit',data=event_form(db,eid,title='Updated')).status_code == 302
    html = client.get(f'/organizer/{eid}/participants').text
    assert 'member@example.test' not in html
    assert client.post(f'/organizer/{eid}/cancel').status_code == 302
    assert db.execute('SELECT status FROM reservations WHERE event_id=%s',(eid,)).fetchone()['status'] == 'cancelled'
    assert stranger.post(f'/activities/{eid}/reserve').status_code == 400


def test_event_creation_and_draft_publication(app, db):
    owner = user(db,roles=('member','organizer'))
    source = event(db,owner)
    client = login(app)
    form = event_form(db,source,title='New draft',status='draft')
    assert client.post('/organizer/new',data=form).status_code == 302
    row = db.execute("SELECT id FROM events WHERE title='New draft'").fetchone()
    assert row
    assert app.test_client().get(f'/activities/{row["id"]}').status_code == 404
    form['status'] = 'published'
    assert client.post(f'/organizer/{row["id"]}/edit',data=form).status_code == 302
    assert app.test_client().get(f'/activities/{row["id"]}').status_code == 200


def test_started_events_and_capacity_reduction(app, db):
    owner = user(db,roles=('member','organizer'))
    user(db,'second@example.test')
    eid = event(db,owner,2)
    client = login(app)
    client.post(f'/activities/{eid}/reserve')
    login(app,'second@example.test').post(f'/activities/{eid}/reserve')
    assert client.post(f'/organizer/{eid}/edit',data=event_form(db,eid,capacity='1')).status_code == 400
    db.execute("UPDATE events SET starts_at=now()-interval '1 hour' WHERE id=%s",(eid,))
    bid = db.execute('SELECT id FROM reservations WHERE member_id=%s',(owner,)).fetchone()['id']
    assert client.post(f'/reservations/{bid}/cancel').status_code == 400
    assert client.post(f'/organizer/{eid}/cancel').status_code == 400


def test_admin_content_contact_and_roles(app, db):
    admin_id = user(db,'admin@example.test',('member','admin'))
    member = user(db)
    admin = login(app,'admin@example.test')
    member_client = login(app)
    assert member_client.get('/admin').status_code == 403
    assert admin.get('/admin').status_code == 200
    assert admin.post('/admin/faq',data={'question':'Question','answer':'Answer','sort_order':'1','published':'on'}).status_code == 302
    assert 'Answer' in app.test_client().get('/faq').text
    faq_id = db.execute('SELECT id FROM faqs').fetchone()['id']
    admin.post('/admin/faq',data={'id':faq_id,'question':'Question','answer':'Answer','sort_order':'1'})
    assert 'Answer' not in app.test_client().get('/faq').text
    for content in ['First version','Second version']:
        assert admin.post('/admin/legal',data={'kind':'terms','content':content}).status_code == 302
    assert 'Second version' in app.test_client().get('/legal/terms').text
    assert db.execute('SELECT count(*) AS n FROM legal_pages').fetchone()['n'] == 2
    assert app.test_client().post('/contact',data={'name':'Someone','email':'visitor@example.test','subject':'Help','message':'Contact content'}).status_code == 302
    assert 'Contact content' in admin.get('/admin').text
    assert admin.post(f'/admin/users/{admin_id}',data={'status':'suspended'}).status_code == 400
    assert admin.post(f'/admin/users/{member}',data={'status':'suspended','roles':['organizer']}).status_code == 302
    assert member_client.get('/account').status_code == 302


def test_password_reset_single_use_and_revocation(app, db):
    uid = user(db)
    client = login(app)
    token = 'only-for-reset-test'
    db.execute("INSERT INTO password_resets VALUES (%s,%s,now()+interval '10 minutes')",(hashlib.sha256(token.encode()).hexdigest(),uid))
    other = app.test_client()
    assert other.post('/reset-password/'+token,data={'password':PASSWORD+'new'}).status_code == 302
    assert other.get('/reset-password/'+token).status_code == 400
    assert client.get('/account').status_code == 302
    assert other.post('/login',data={'email':'member@example.test','password':PASSWORD+'new'}).status_code == 302


def test_rate_limit(app):
    client = app.test_client()
    for _ in range(10):
        assert client.post('/login',data={'email':'unknown@example.test','password':PASSWORD}).status_code == 401
    assert client.post('/login',data={'email':'unknown@example.test','password':PASSWORD}).status_code == 429


def test_change_email_password_invalidates_all_sessions(app, db):
    user(db)
    first = login(app)
    second = login(app)
    assert first.post('/account/security',data={'current_password':'wrong','email':'changed@example.test','password':PASSWORD+'new'}).status_code == 400
    assert first.post('/account/security',data={'current_password':PASSWORD,'email':'changed@example.test','password':PASSWORD+'new'}).status_code == 302
    assert second.get('/account').status_code == 302
    assert app.test_client().post('/login',data={'email':'changed@example.test','password':PASSWORD+'new'}).status_code == 302


def test_concurrent_event_cancel_and_reserve(app, db):
    owner = user(db,roles=('member','organizer'))
    user(db,'second@example.test')
    eid = event(db,owner,2)
    organizer = login(app)
    member = login(app,'second@example.test')
    barrier = Barrier(2)
    def action(pair):
        client, path = pair
        barrier.wait(timeout=5)
        return client.post(path).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        result = list(executor.map(action, [(organizer,f'/organizer/{eid}/cancel'), (member,f'/activities/{eid}/reserve')]))
    assert result[0] == 302 and result[1] in (302,400)
    assert db.execute('SELECT status FROM events WHERE id=%s',(eid,)).fetchone()['status'] == 'cancelled'
    assert db.execute("SELECT count(*) AS n FROM reservations WHERE event_id=%s AND status='confirmed'",(eid,)).fetchone()['n'] == 0


def test_reset_mail_transport_and_expiry(app, db, monkeypatch):
    user(db)
    monkeypatch.setenv('SMTP_HOST','mail.example.test')
    monkeypatch.setenv('MAIL_FROM','joinly@example.test')
    monkeypatch.setenv('PUBLIC_BASE_URL','https://joinly.example.test')
    sent = []
    class Mail:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def starttls(self, **kwargs):
            assert kwargs["context"].check_hostname
        def send_message(self,message): sent.append(message)
    monkeypatch.setattr('app.smtplib.SMTP', Mail)
    client = app.test_client()
    real = client.post('/forgot-password',data={'email':'member@example.test'},follow_redirects=True)
    unknown = app.test_client().post('/forgot-password',data={'email':'unknown@example.test'},follow_redirects=True)
    assert 'Si ce compte est actif' in real.text and 'Si ce compte est actif' in unknown.text
    assert len(sent) == 1
    assert 'https://joinly.example.test/reset-password/' in sent[0].get_content()
    db.execute("UPDATE password_resets SET expires_at=now()-interval '1 second'")
    token = sent[0].get_content().strip().rsplit('/',1)[-1]
    assert client.get('/reset-password/'+token).status_code == 400


def test_privacy_robots_sitemap_and_meta(app, db):
    app.config['PUBLIC_BASE_URL'] = 'https://isep.wangjiahan.com'
    client = app.test_client()
    privacy = client.get('/legal/privacy')
    assert privacy.status_code == 200
    assert 'Politique de confidentialité' in privacy.text
    assert 'Brevo' in privacy.text and 'CNIL' in privacy.text
    assert 'cookie' in privacy.text.lower()
    assert 'id="cookies"' in privacy.text
    assert 'Document de démonstration' not in privacy.text
    assert 'à renseigner' not in privacy.text
    notice = client.get('/legal/legal_notice')
    assert 'Welfenstraße 22' in notice.text
    assert 'Jiahan Wang' in notice.text
    assert 'contact@wangjiahan.com' in notice.text
    assert 'à renseigner' not in notice.text
    redirect = client.get('/privacy')
    assert redirect.status_code == 301
    assert redirect.headers['Location'].endswith('/legal/privacy')
    robots = client.get('/robots.txt')
    assert robots.status_code == 200
    assert robots.mimetype.startswith('text/plain')
    assert 'Sitemap: https://isep.wangjiahan.com/sitemap.xml' in robots.text
    assert 'Disallow: /admin' in robots.text
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    public = event(db, owner)
    draft = event(db, owner, status='draft')
    sitemap = client.get('/sitemap.xml')
    assert sitemap.status_code == 200
    assert sitemap.mimetype.startswith('application/xml')
    assert f'https://isep.wangjiahan.com/activities/{public}' in sitemap.text
    assert f'/activities/{draft}' not in sitemap.text
    assert 'https://isep.wangjiahan.com/legal/privacy' in sitemap.text
    home = client.get('/')
    assert 'property="og:title"' in home.text
    assert 'rel="canonical"' in home.text
    assert 'favicon.svg' in home.text
    assert client.get('/favicon.ico').status_code == 200
    missing = client.get('/missing')
    assert missing.status_code == 404
    assert 'Page introuvable' in missing.text


def test_seed_demo_is_idempotent_and_keeps_existing_accounts(app, db):
    from app.seed_demo import DEMO_PASSWORDS, seed_demo
    kept = user(db, 'kept@example.test')
    kept_hash = db.execute('SELECT password_hash FROM users WHERE id=%s', (kept,)).fetchone()['password_hash']
    custom = generate_password_hash('Already chosen password 123')
    db.execute(
        "INSERT INTO users(email, display_name, password_hash) VALUES ('lea.moreau@demo.joinly.fr', 'Déjà présente', %s)",
        (custom,),
    )
    db.execute(
        "INSERT INTO legal_pages(kind, version, content, published_at) VALUES ('terms', 1, 'Version conservée du projet', now())"
    )
    first = seed_demo(db)
    second = seed_demo(db)
    assert first['users_created'] >= 39
    assert second['users_created'] == 0
    assert second['events_created'] == 0
    assert second['bookings_created'] == 0
    assert first['events_created'] == 50
    assert 40 <= first['demo_users'] <= 46
    assert first['demo_users'] == second['demo_users']
    assert first['demo_events'] == second['demo_events'] == 50
    assert db.execute("SELECT password_hash FROM users WHERE id=%s", (kept,)).fetchone()['password_hash'] == kept_hash
    stored = db.execute("SELECT password_hash, display_name FROM users WHERE email='lea.moreau@demo.joinly.fr'").fetchone()
    assert stored['password_hash'] == custom
    assert stored['display_name'] == 'Déjà présente'
    admin = db.execute("SELECT password_hash FROM users WHERE email='admin.demo@demo.joinly.fr'").fetchone()
    assert admin['password_hash'] != DEMO_PASSWORDS['admin']
    assert check_password_hash(admin['password_hash'], DEMO_PASSWORDS['admin'])
    overflow = db.execute(
        """SELECT e.id FROM events e
           WHERE (SELECT count(*) FROM reservations r WHERE r.event_id=e.id AND r.status='confirmed') > e.capacity"""
    ).fetchone()
    assert overflow is None
    assert db.execute("SELECT count(*) AS n FROM reservations").fetchone()['n'] > 30
    client = app.test_client()
    assert 'Version conservée du projet' in client.get('/legal/terms').text
    assert 'Brevo' in client.get('/legal/privacy').text
    assert client.post('/login', data={'email': 'admin.demo@demo.joinly.fr', 'password': DEMO_PASSWORDS['admin']}).status_code == 302
    assert client.get('/admin').status_code == 200
    member = app.test_client()
    assert member.post('/login', data={'email': 'marie.dupont@demo.joinly.fr', 'password': DEMO_PASSWORDS['member']}).status_code == 302
    assert 'Balade commentée au Luxembourg' in app.test_client().get('/activities').text
    draft = db.execute("SELECT id FROM events WHERE title='Atelier calligraphie latine'").fetchone()['id']
    assert app.test_client().get(f'/activities/{draft}').status_code == 404
    assert db.execute("SELECT count(*) AS n FROM events WHERE price_cents > 0").fetchone()['n'] == 10
    assert db.execute("SELECT icon FROM categories WHERE name='Musique'").fetchone()['icon'] == '🎵'
    assert db.execute("SELECT icon FROM categories WHERE name='Pique-nique'").fetchone()['icon'] == '🧺'
    assert db.execute(
        """SELECT count(*) AS n FROM user_interests ui JOIN users u ON u.id=ui.user_id
           WHERE u.email='lea.moreau@demo.joinly.fr'"""
    ).fetchone()['n'] >= 3
    assert db.execute(
        """SELECT count(*) AS n FROM user_interests ui JOIN users u ON u.id=ui.user_id
           WHERE u.email='kept@example.test'"""
    ).fetchone()['n'] == 3
    db.execute("UPDATE events SET price_cents=1 WHERE title='Yoga au parc'")
    third = seed_demo(db)
    assert third['events_created'] == 0
    assert third['users_created'] == 0
    assert db.execute("SELECT price_cents FROM events WHERE title='Yoga au parc'").fetchone()['price_cents'] == 800
    assert db.execute("SELECT city FROM events WHERE title='Balade commentée au Luxembourg'").fetchone()['city'] == 'Paris'
    luxembourg = db.execute("SELECT latitude, longitude FROM events WHERE title='Balade commentée au Luxembourg'").fetchone()
    assert luxembourg['latitude'] is not None and abs(float(luxembourg['latitude']) - 48.84622) < 0.01
    assert db.execute("SELECT city FROM events WHERE title='Tartes de saison'").fetchone()['city'] == 'Montreuil'
    assert db.execute(
        "SELECT count(*) AS n FROM reviews rv JOIN users u ON u.id=rv.author_id WHERE u.email='kept@example.test'"
    ).fetchone()['n'] == 0
    review_count = db.execute('SELECT count(*) AS n FROM reviews').fetchone()['n']
    assert review_count > 0
    assert db.execute(
        'SELECT count(*) AS n FROM reviews rv JOIN events e ON e.id=rv.event_id WHERE e.ends_at > now()'
    ).fetchone()['n'] == 0
    seed_demo(db)
    assert db.execute('SELECT count(*) AS n FROM reviews').fetchone()['n'] == review_count
    assert db.execute(
        "SELECT count(*) AS n FROM favorites f JOIN users u ON u.id=f.user_id WHERE u.email='kept@example.test'"
    ).fetchone()['n'] == 0
    follows = db.execute('SELECT count(*) AS n FROM organizer_follows').fetchone()['n']
    favorites = db.execute('SELECT count(*) AS n FROM favorites').fetchone()['n']
    assert follows > 0 and favorites > 0
    seed_demo(db)
    assert db.execute('SELECT count(*) AS n FROM organizer_follows').fetchone()['n'] == follows
    assert db.execute('SELECT count(*) AS n FROM favorites').fetchone()['n'] == favorites
    assert member.get('/').status_code == 200
    assert 'Recommandé pour vous' in member.get('/').text


def test_interest_gate_blocks_members_and_lets_admins_skip(app, db):
    user(db, interests=False)
    ids = [str(category_id) for category_id in ensure_categories(db)]
    client = login(app)
    account = client.get('/account')
    assert account.status_code == 302 and account.headers['Location'].endswith('/interests')
    assert client.get('/activities').status_code == 302
    picker = client.get('/interests')
    assert picker.status_code == 200
    assert '🍳' in picker.text and 'Cuisine' in picker.text
    assert 'Passer cette étape' not in picker.text
    assert client.post('/interests', data={'interest_ids': ids[:2]}).status_code == 400
    assert db.execute("SELECT count(*) AS n FROM user_interests").fetchone()['n'] == 0
    assert client.post('/interests', data={'interest_ids': ids[:3]}).status_code == 302
    assert client.get('/account').status_code == 200
    assert client.post('/account', data={'display_name': 'member', 'interest_ids': ids[:2], 'chosen_area': ''}).status_code == 400
    user(db, 'admin@example.test', ('member', 'admin'), interests=False)
    admin = login(app, 'admin@example.test')
    assert admin.get('/account').status_code == 200
    assert admin.get('/admin').status_code == 200
    assert 'Passer cette étape' in admin.get('/interests').text


def test_recommendations_match_interests(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    member_id = user(db, 'fan@example.test')
    cuisine = db.execute("SELECT id FROM categories WHERE name='Cuisine'").fetchone()['id']
    music = db.execute("SELECT id FROM categories WHERE name='Musique'").fetchone()['id']
    photo = db.execute("SELECT id FROM categories WHERE name='Photo'").fetchone()['id']
    sport = db.execute("SELECT id FROM categories WHERE name='Sport'").fetchone()['id']
    db.execute('DELETE FROM user_interests WHERE user_id=%s', (member_id,))
    for category_id in (cuisine, music, photo):
        db.execute('INSERT INTO user_interests(user_id, category_id) VALUES (%s, %s)', (member_id, category_id))
    soup = event(db, owner)
    run = event(db, owner)
    db.execute("UPDATE events SET title='Atelier soupe', category_id=%s WHERE id=%s", (cuisine, soup))
    db.execute("UPDATE events SET title='Footing dimanche', category_id=%s WHERE id=%s", (sport, run))
    html = login(app, 'fan@example.test').get('/').text
    block = html.split('id="recommandations"', 1)[1].split('id="classement"', 1)[0]
    assert 'Atelier soupe' in block
    assert 'Footing dimanche' not in block
    assert 'vos centres d’intérêt' in block
    anon = app.test_client().get('/').text
    fallback = anon.split('id="recommandations"', 1)[1].split('id="classement"', 1)[0]
    assert 'Atelier soupe' in fallback and 'Footing dimanche' in fallback
    assert 'Connectez-vous' in fallback


def test_ranking_uses_heat_and_shows_badges(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    members = [user(db, f'fan{i}@example.test') for i in range(8)]
    calm = event(db, owner, 10)
    viewed = event(db, owner, 10)
    popular = event(db, owner, 10)
    db.execute("UPDATE events SET title='Calme' WHERE id=%s", (calm,))
    db.execute("UPDATE events SET title='Consultée', view_count=40 WHERE id=%s", (viewed,))
    db.execute("UPDATE events SET title='Populaire' WHERE id=%s", (popular,))
    for member in members:
        db.execute('INSERT INTO reservations(member_id, event_id) VALUES (%s, %s)', (member, popular))
    page = app.test_client().get('/classement').text
    assert page.index('Populaire') < page.index('Consultée') < page.index('Calme')
    assert 'rank-badge rank-1' in page and 'rank-badge rank-2' in page and 'rank-badge rank-3' in page
    home = app.test_client().get('/').text
    section = home.split('id="classement"', 1)[1]
    assert 'Populaire' in section and 'rank-badge rank-1' in section


def test_view_counter_on_published_detail(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    public = event(db, owner)
    draft = event(db, owner, status='draft')
    client = app.test_client()
    assert client.get(f'/activities/{public}').status_code == 200
    assert client.get(f'/activities/{public}').status_code == 200
    assert db.execute('SELECT view_count FROM events WHERE id=%s', (public,)).fetchone()['view_count'] == 2
    assert login(app, 'owner@example.test').get(f'/activities/{draft}').status_code == 200
    assert db.execute('SELECT view_count FROM events WHERE id=%s', (draft,)).fetchone()['view_count'] == 0


def test_paid_activity_simulated_payment_and_admin_price(app, db):
    owner = user(db, roles=('member', 'organizer'))
    user(db, 'payer@example.test')
    user(db, 'admin@example.test', ('member', 'admin'), interests=False)
    eid = event(db, owner, 5)
    organizer = login(app)
    assert organizer.post(f'/organizer/{eid}/edit', data=event_form(db, eid, price='12,50')).status_code == 302
    assert db.execute('SELECT price_cents FROM events WHERE id=%s', (eid,)).fetchone()['price_cents'] == 1250
    assert organizer.post(f'/organizer/{eid}/edit', data=event_form(db, eid, price='-1')).status_code == 400
    assert organizer.post(f'/organizer/{eid}/edit', data=event_form(db, eid, price='12.555')).status_code == 400
    public = app.test_client().get(f'/activities/{eid}')
    assert '12,50 €' in public.text
    assert '12,50 €' in app.test_client().get('/activities').text
    payer = login(app, 'payer@example.test')
    assert payer.post(f'/activities/{eid}/reserve').status_code == 400
    payment = payer.get(f'/activities/{eid}/paiement')
    assert payment.status_code == 200
    assert 'Paiement simulé — projet étudiant' in payment.text
    assert 'name="card"' not in payment.text and 'name="cvv"' not in payment.text and 'name="pan"' not in payment.text
    assert payer.post(f'/activities/{eid}/reserve', data={'payment_simulated': '1'}).status_code == 302
    assert db.execute("SELECT count(*) AS n FROM reservations WHERE event_id=%s AND status='confirmed'", (eid,)).fetchone()['n'] == 1
    free = event(db, owner, 5)
    assert payer.post(f'/activities/{free}/reserve').status_code == 302
    assert payer.get(f'/activities/{free}/paiement').status_code == 302
    admin = login(app, 'admin@example.test')
    assert admin.post(f'/admin/events/{free}/price', data={'price': '9'}).status_code == 302
    assert db.execute('SELECT price_cents FROM events WHERE id=%s', (free,)).fetchone()['price_cents'] == 900
    assert '9 €' in app.test_client().get(f'/activities/{free}').text
    assert payer.get(f'/activities/{free}/paiement').status_code == 200


def test_trusted_proxy_https_forms_and_hosts(app):
    proxied = create_app({'TESTING':True,'DATABASE':'joinly_test','SECRET_KEY':'proxy-test-secret','TRUST_PROXY':True,'TRUSTED_HOSTS':['isep.wangjiahan.com'],'SESSION_COOKIE_SECURE':True})
    client = proxied.test_client()
    headers = {'Host':'isep.wangjiahan.com','X-Forwarded-Proto':'https','X-Forwarded-For':'192.0.2.1'}
    response = client.get('/contact',headers=headers)
    assert response.status_code == 200
    assert 'Secure;' in response.headers['Set-Cookie']
    token = re.search(r'name="csrf_token" value="([^"]+)"',response.text).group(1)
    headers['Referer'] = 'https://isep.wangjiahan.com/contact'
    response = client.post('/contact',headers=headers,data={'csrf_token':token,'name':'Proxy test','email':'proxy@example.test','subject':'HTTPS','message':'Test'})
    assert response.status_code == 302
    assert client.get('/',headers={'Host':'untrusted.example'}).status_code == 400


def test_finished_activities_stay_visible_but_leave_the_lists(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    user(db, 'admin@example.test', ('member', 'admin'), interests=False)
    user(db, 'guest@example.test')
    eid = event(db, owner, 4)
    db.execute(
        """UPDATE events SET title='Sortie finie', city='Paris', price_cents=1000,
           starts_at=now()-interval '3 hours', ends_at=now()-interval '1 hour' WHERE id=%s""",
        (eid,),
    )
    db.execute('INSERT INTO reservations(member_id, event_id) VALUES (%s, %s)', (
        db.execute("SELECT id FROM users WHERE email='guest@example.test'").fetchone()['id'], eid,
    ))
    public = app.test_client()
    assert 'Sortie finie' not in public.get('/activities').text
    assert 'Sortie finie' not in public.get('/').text
    assert 'Sortie finie' not in public.get('/classement').text
    archive = public.get('/activities?when=past')
    assert archive.status_code == 200
    assert 'Sortie finie' in archive.text and 'Activité terminée' in archive.text
    detail = public.get(f'/activities/{eid}')
    assert detail.status_code == 200 and 'Activité terminée' in detail.text and 'Annulée' not in detail.text
    guest = login(app, 'guest@example.test')
    assert guest.post(f'/activities/{eid}/reserve').status_code == 400
    account = guest.get('/account').text
    assert 'Historique' in account and 'Sortie finie' in account
    organizer = login(app, 'owner@example.test')
    form = event_form(db, eid)
    upcoming = datetime.now(ZoneInfo('Europe/Paris')) + timedelta(days=4)
    form['starts_at'] = upcoming.strftime('%Y-%m-%dT10:00')
    form['ends_at'] = upcoming.strftime('%Y-%m-%dT12:00')
    denied = organizer.post(f'/organizer/{eid}/edit', data=form)
    assert denied.status_code == 400 and 'administrateur' in denied.text
    assert guest.post(f'/admin/events/{eid}/dates', data={'starts_at': form['starts_at'], 'ends_at': form['ends_at']}).status_code == 403
    admin = login(app, 'admin@example.test')
    assert admin.post(f'/admin/events/{eid}/dates', data={'starts_at': form['starts_at'], 'ends_at': form['ends_at']}).status_code == 302
    stored = db.execute('SELECT starts_at FROM events WHERE id=%s', (eid,)).fetchone()['starts_at']
    assert stored > datetime.now(ZoneInfo('Europe/Paris'))
    cancelled = event(db, owner, 4)
    db.execute("UPDATE events SET title='Sortie annulée', status='cancelled' WHERE id=%s", (cancelled,))
    cancelled_page = public.get(f'/activities/{cancelled}').text
    assert 'Annulée' in cancelled_page and 'Activité terminée' not in cancelled_page
    assert 'Sortie annulée' not in public.get('/activities?when=past').text


def test_booking_cutoff_closes_before_the_start(app, db):
    owner = user(db, roles=('member', 'organizer'))
    user(db, 'guest@example.test')
    eid = event(db, owner, 4)
    db.execute(
        "UPDATE events SET starts_at=now()+interval '30 minutes', ends_at=now()+interval '2 hours' WHERE id=%s",
        (eid,),
    )
    app.config['BOOKING_CUTOFF_MINUTES'] = 180
    db.execute('UPDATE site_settings SET booking_cutoff_minutes=180')
    guest = login(app, 'guest@example.test')
    assert guest.post(f'/activities/{eid}/reserve').status_code == 400
    assert 'Inscriptions closes' in guest.get(f'/activities/{eid}').text
    app.config['BOOKING_CUTOFF_MINUTES'] = 0
    db.execute('UPDATE site_settings SET booking_cutoff_minutes=0')
    assert guest.post(f'/activities/{eid}/reserve').status_code == 302


def test_activity_search_filters_sort_and_pagination(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    fans = [user(db, f'fan{i}@example.test') for i in range(3)]
    cheap = event(db, owner, 5)
    costly = event(db, owner, 5)
    popular = event(db, owner, 5)
    db.execute("UPDATE events SET title='Atelier gratuit', city='Paris', price_cents=0, description='Soupe de saison' WHERE id=%s", (cheap,))
    db.execute(
        """UPDATE events SET title='Atelier payant', city='Lyon', price_cents=2000,
           starts_at=now()+interval '4 days', ends_at=now()+interval '4 days 2 hours' WHERE id=%s""",
        (costly,),
    )
    db.execute(
        """UPDATE events SET title='Atelier suivi', city='Paris', price_cents=500,
           starts_at=now()+interval '5 days', ends_at=now()+interval '5 days 2 hours' WHERE id=%s""",
        (popular,),
    )
    for fan in fans:
        db.execute('INSERT INTO reservations(member_id, event_id) VALUES (%s, %s)', (fan, popular))
    client = app.test_client()
    assert 'Atelier gratuit' in client.get('/activities?q=soupe').text
    paris = client.get('/activities?city=Paris').text
    assert 'Atelier gratuit' in paris and 'Atelier payant' not in paris
    paid = client.get('/activities?price=paid').text
    assert 'Atelier payant' in paid and 'Atelier gratuit' not in paid
    assert 'Atelier payant' not in client.get('/activities?max=10').text
    assert 'Atelier payant' in client.get('/activities?max=20').text
    by_price = client.get('/activities?sort=price').text
    assert by_price.index('Atelier gratuit') < by_price.index('Atelier payant')
    by_popularity = client.get('/activities?sort=popularity').text
    assert by_popularity.index('Atelier suivi') < by_popularity.index('Atelier gratuit')
    assert client.get('/activities?when=later').status_code == 400
    assert client.get('/activities?sort=nope').status_code == 400
    assert client.get('/activities?max=abc').status_code == 400
    for index in range(13):
        created = event(db, owner, 3)
        db.execute(
            """UPDATE events SET title=%s, starts_at=now()+interval '10 days', ends_at=now()+interval '10 days 1 hour'
               WHERE id=%s""",
            (f'Pageitem {index:02d}', created),
        )
    first = client.get('/activities?q=Pageitem').text
    second = client.get('/activities?q=Pageitem&page=2').text
    assert 'Pageitem 00' in first and 'Pageitem 12' not in first
    assert 'Pageitem 12' in second and 'Suivant' not in second
    assert 'Précédent' in second


def test_reviews_are_unique_editable_and_moderated(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    guest_id = user(db, 'guest@example.test')
    stranger = user(db, 'stranger@example.test')
    user(db, 'admin@example.test', ('member', 'admin'), interests=False)
    eid = event(db, owner, 4)
    other = event(db, owner, 4)
    db.execute("UPDATE events SET title='Notée haut' WHERE id=%s", (eid,))
    db.execute("UPDATE events SET title='Notée bas' WHERE id=%s", (other,))
    guest = login(app, 'guest@example.test')
    assert guest.post(f'/activities/{eid}/reserve').status_code == 302
    assert guest.post(f'/activities/{eid}/avis', data={'rating': '5', 'comment': 'Trop tôt'}).status_code == 400
    db.execute("UPDATE events SET starts_at=now()-interval '3 hours', ends_at=now()-interval '1 hour' WHERE id=%s", (eid,))
    db.execute("UPDATE events SET starts_at=now()-interval '5 hours', ends_at=now()-interval '4 hours' WHERE id=%s", (other,))
    db.execute('INSERT INTO reservations(member_id, event_id) VALUES (%s, %s)', (stranger, other))
    assert guest.post(f'/activities/{eid}/avis', data={'rating': '4', 'comment': 'Très belle ambiance.'}).status_code == 302
    assert guest.post(f'/activities/{eid}/avis', data={'rating': '5', 'comment': 'Encore mieux après coup.'}).status_code == 302
    assert db.execute('SELECT count(*) AS n FROM reviews').fetchone()['n'] == 1
    assert login(app, 'stranger@example.test').post(
        f'/activities/{eid}/avis', data={'rating': '1', 'comment': 'Je n’y étais pas.'}
    ).status_code == 400
    page = app.test_client().get(f'/activities/{eid}').text
    assert 'Encore mieux après coup.' in page and '★' in page
    past = app.test_client().get('/activities?when=past&sort=rating').text
    assert past.index('Notée haut') < past.index('Notée bas') or 'Notée bas' not in past
    login(app, 'stranger@example.test').post(f'/activities/{other}/avis', data={'rating': '2', 'comment': 'Correct sans plus.'})
    ordered = app.test_client().get('/activities?when=past&sort=rating').text
    assert ordered.index('Notée haut') < ordered.index('Notée bas')
    admin = login(app, 'admin@example.test')
    review_id = db.execute('SELECT id FROM reviews WHERE author_id=%s', (guest_id,)).fetchone()['id']
    assert admin.post(f'/admin/reviews/{review_id}', data={'hidden': 'on'}).status_code == 302
    hidden = app.test_client().get(f'/activities/{eid}').text
    assert 'Encore mieux après coup.' not in hidden
    assert 'Masqué' in guest.get(f'/activities/{eid}').text
    assert db.execute(
        'SELECT rating_count FROM (SELECT (SELECT count(*) FROM reviews rv WHERE rv.event_id=e.id AND NOT rv.hidden) AS rating_count FROM events e WHERE e.id=%s) s',
        (eid,),
    ).fetchone()['rating_count'] == 0


def test_favorites_follows_and_public_organizer_profile(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    guest = user(db, 'guest@example.test')
    plain = user(db, 'plain@example.test')
    eid = event(db, owner, 4)
    db.execute("UPDATE events SET title='Balade favorite' WHERE id=%s", (eid,))
    client = login(app, 'guest@example.test')
    assert client.post(f'/activities/{eid}/favori').status_code == 302
    assert 'Balade favorite' in client.get('/account').text
    assert 'Retirer des favoris' in client.get(f'/activities/{eid}').text
    assert client.post(f'/activities/{eid}/favori').status_code == 302
    assert 'Balade favorite' not in client.get('/account').text.split('Mes favoris', 1)[1].split('Organisateurs suivis', 1)[0]
    assert client.post(f'/organisateurs/{plain}/suivre').status_code == 404
    assert client.post(f'/organisateurs/{guest}/suivre').status_code == 400
    assert client.post(f'/organisateurs/{owner}/suivre').status_code == 302
    profile = app.test_client().get(f'/organisateurs/{owner}')
    assert profile.status_code == 200
    assert 'Balade favorite' in profile.text and '1 abonné' in profile.text
    assert 'owner' in client.get('/account').text
    assert client.post(f'/organisateurs/{owner}/suivre').status_code == 302
    assert '1 abonné' not in app.test_client().get(f'/organisateurs/{owner}').text


def test_cover_library_is_stable_and_uploads_are_private(app, db, tmp_path):
    import base64
    import io
    from pathlib import Path
    from app.covers import SLUGS, auto_cover_index, library_files, pick_auto, pick_list
    app.config['UPLOAD_DIR'] = str(tmp_path)
    for name in SLUGS:
        files = library_files(name)
        assert 12 <= len(files) <= 15
        for filename in files:
            path = Path('app/static/covers') / SLUGS[name] / filename
            assert path.stat().st_size < 150_000
    sample = library_files('Cuisine')
    assert pick_auto(4, sample) == pick_auto(4, sample)
    shared = auto_cover_index(1, len(sample))
    twin = next(index for index in range(2, 8000) if auto_cover_index(index, len(sample)) == shared)
    assert pick_list([(1, sample, None), (twin, sample, None)])[0] != pick_list([(1, sample, None), (twin, sample, None)])[1]
    assert pick_list([(1, sample, 'custom.webp')]) == ['custom.webp']
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    user(db, 'admin@example.test', ('member', 'admin'), interests=False)
    cuisine = db.execute("SELECT id FROM categories WHERE name='Cuisine'").fetchone()['id']
    sport = db.execute("SELECT id FROM categories WHERE name='Sport'").fetchone()['id']
    eid = event(db, owner)
    db.execute("UPDATE events SET category_id=%s, title='Atelier couvert' WHERE id=%s", (cuisine, eid))
    assert 'covers/cuisine/' in app.test_client().get(f'/activities/{eid}').text
    organizer = login(app, 'owner@example.test')
    form = event_form(db, eid, category_id=str(sport))
    assert organizer.post(f'/organizer/{eid}/edit', data=form).status_code == 302
    assert 'covers/sport/' in app.test_client().get(f'/activities/{eid}').text
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
    uploaded = event_form(db, eid)
    uploaded['cover'] = (io.BytesIO(png), 'point.png')
    assert organizer.post(f'/organizer/{eid}/edit', data=uploaded, content_type='multipart/form-data').status_code == 302
    with_file = app.test_client().get(f'/activities/{eid}').text
    assert '/media/e' in with_file
    moved = event_form(db, eid, category_id=str(cuisine))
    assert organizer.post(f'/organizer/{eid}/edit', data=moved).status_code == 302
    assert '/media/e' in app.test_client().get(f'/activities/{eid}').text
    rejected = event_form(db, eid)
    rejected['cover'] = (io.BytesIO(b'this is not an image file'), 'note.png')
    assert organizer.post(f'/organizer/{eid}/edit', data=rejected, content_type='multipart/form-data').status_code == 400
    assert app.test_client().get('/media/e1-0123456789abcdef.webp').status_code == 404
    admin = login(app, 'admin@example.test')
    assert admin.get('/admin/couvertures').status_code == 200
    assert 'covers/cuisine/01.webp' in admin.get('/admin/couvertures').text
    assert organizer.get('/admin/couvertures').status_code == 403
    chosen = 'covers/cuisine/03.webp'
    assert admin.post(f'/admin/events/{eid}/cover', data={'cover_choice': chosen}).status_code == 302
    assert chosen in app.test_client().get(f'/activities/{eid}').text
    assert admin.post(f'/admin/events/{eid}/cover', data={'cover_choice': 'auto'}).status_code == 302
    assert 'covers/cuisine/' in app.test_client().get(f'/activities/{eid}').text


def test_map_uses_coordinates_and_allows_openstreetmap(app, db):
    owner = user(db, roles=('member', 'organizer'))
    eid = event(db, owner)
    plain = app.test_client().get(f'/activities/{eid}')
    assert 'activity-map' not in plain.text
    policy = plain.headers['Content-Security-Policy']
    assert 'unpkg.com' in policy and 'tile.openstreetmap.org' in policy
    organizer = login(app)
    assert organizer.post(f'/organizer/{eid}/edit', data=event_form(db, eid, latitude='48.8566', longitude='2.3522')).status_code == 302
    mapped = app.test_client().get(f'/activities/{eid}').text
    assert 'id="activity-map"' in mapped and 'data-lat="48.8566' in mapped and 'leaflet.js' in mapped
    assert organizer.post(f'/organizer/{eid}/edit', data=event_form(db, eid, latitude='95', longitude='2')).status_code == 400


def test_notifications_mail_and_reminders(app, db, monkeypatch):
    import smtplib
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    guest = user(db, 'guest@example.test')
    fan = user(db, 'fan@example.test')
    eid = event(db, owner, 4)
    db.execute('INSERT INTO organizer_follows(follower_id, organizer_id) VALUES (%s, %s)', (fan, owner))
    client = login(app, 'guest@example.test')
    assert client.post(f'/activities/{eid}/reserve').status_code == 302
    note = db.execute(
        "SELECT kind FROM notifications WHERE user_id=%s AND kind='booking_confirmed'", (guest,),
    ).fetchone()
    assert note
    mail = db.execute("SELECT subject, body FROM dev_outbox WHERE recipient='guest@example.test'").fetchone()
    assert mail and 'Place confirmée' in mail['subject']
    assert 'bell-count' in client.get('/').text
    page = client.get('/notifications')
    assert page.status_code == 200 and 'Place confirmée' in page.text
    assert client.post('/notifications/lu').status_code == 302
    assert db.execute(
        'SELECT count(*) AS n FROM notifications WHERE user_id=%s AND read_at IS NULL', (guest,),
    ).fetchone()['n'] == 0
    organizer = login(app, 'owner@example.test')
    assert organizer.post(f'/organizer/{eid}/edit', data=event_form(db, eid, title='Balade modifiée')).status_code == 302
    assert db.execute(
        "SELECT count(*) AS n FROM notifications WHERE user_id=%s AND kind='event_changed'", (guest,),
    ).fetchone()['n'] == 1
    assert organizer.post(f'/organizer/{eid}/cancel').status_code == 302
    assert db.execute(
        "SELECT count(*) AS n FROM notifications WHERE user_id=%s AND kind='event_cancelled'", (guest,),
    ).fetchone()['n'] == 1
    published = event(db, owner, 4)
    db.execute("UPDATE events SET title='Nouvelle sortie' WHERE id=%s", (published,))
    assert organizer.post(f'/organizer/{published}/edit', data=event_form(db, published, title='Nouvelle sortie')).status_code == 302
    assert db.execute(
        "SELECT count(*) AS n FROM notifications WHERE user_id=%s AND kind='new_activity'", (fan,),
    ).fetchone()['n'] == 0
    fresh = event(db, owner, status='draft')
    assert organizer.post(f'/organizer/{fresh}/edit', data=event_form(db, fresh, status='published', title='Sortie suivie')).status_code == 302
    assert db.execute(
        "SELECT count(*) AS n FROM notifications WHERE user_id=%s AND kind='new_activity'", (fan,),
    ).fetchone()['n'] == 1
    past = event(db, owner, 4)
    db.execute("UPDATE events SET starts_at=now()-interval '3 hours', ends_at=now()-interval '1 hour' WHERE id=%s", (past,))
    db.execute('INSERT INTO reservations(member_id, event_id) VALUES (%s, %s)', (guest, past))
    assert client.post(f'/activities/{past}/avis', data={'rating': '5', 'comment': 'Très belle sortie.'}).status_code == 302
    assert db.execute(
        "SELECT count(*) AS n FROM notifications WHERE user_id=%s AND kind='new_review'", (owner,),
    ).fetchone()['n'] == 1
    soon = event(db, owner, 4)
    db.execute(
        "UPDATE events SET starts_at=now()+interval '3 hours', ends_at=now()+interval '5 hours' WHERE id=%s",
        (soon,),
    )
    db.execute('INSERT INTO reservations(member_id, event_id) VALUES (%s, %s)', (guest, soon))
    runner = app.test_cli_runner()
    assert runner.invoke(args=['send-reminders']).exit_code == 0
    assert runner.invoke(args=['send-reminders']).exit_code == 0
    assert db.execute(
        "SELECT count(*) AS n FROM notifications WHERE user_id=%s AND kind='reminder'", (guest,),
    ).fetchone()['n'] == 1
    assert db.execute('SELECT reminder_sent_at FROM reservations WHERE event_id=%s', (soon,)).fetchone()['reminder_sent_at']

    class Boom:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def starttls(self, **kwargs):
            raise smtplib.SMTPException('down')
        def send_message(self, message):
            raise smtplib.SMTPException('down')

    monkeypatch.setenv('SMTP_HOST', 'mail.example.test')
    monkeypatch.setenv('MAIL_FROM', 'noreply@wangjiahan.com')
    monkeypatch.setattr('app.notify.smtplib.SMTP', Boom)
    other = event(db, owner, 4)
    assert client.post(f'/activities/{other}/reserve').status_code == 302


def test_tickets_check_in_once_and_reject_the_wrong_organizer(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    other = user(db, 'other-org@example.test', roles=('member', 'organizer'))
    guest = user(db, 'guest@example.test')
    eid = event(db, owner, 4)
    client = login(app, 'guest@example.test')
    assert client.post(f'/activities/{eid}/reserve').status_code == 302
    ticket = db.execute(
        '''SELECT t.id, t.code, t.token FROM tickets t JOIN reservations r ON r.id=t.reservation_id
           WHERE r.member_id=%s AND r.event_id=%s''',
        (guest, eid),
    ).fetchone()
    assert ticket['code'].startswith('JOIN-')
    assert client.get('/account/billets').status_code == 200
    assert ticket['code'] in client.get('/account/billets').text
    qr = client.get(f'/billets/{ticket["id"]}/qr.png')
    assert qr.status_code == 200 and qr.data.startswith(b'\x89PNG')
    assert login(app, 'other-org@example.test').get(f'/organizer/{eid}/controle').status_code == 403
    door = login(app, 'owner@example.test')
    ok = door.post(f'/organizer/{eid}/controle', data={'code': ticket['code']})
    assert ok.status_code == 200 and 'Entrée enregistrée' in ok.text
    again = door.post(f'/organizer/{eid}/controle', data={'code': ticket['token']})
    assert 'Déjà contrôlé' in again.text
    assert door.post(f'/organizer/{eid}/controle', data={'undo': '1', 'ticket_id': str(ticket['id'])}).status_code == 302
    assert 'Contrôlé' in door.get(f'/organizer/{eid}/participants').text or 'contrôlée' in door.get(f'/organizer/{eid}/participants').text.lower()
    client.post(f'/reservations/{db.execute("SELECT id FROM reservations WHERE member_id=%s AND event_id=%s", (guest, eid)).fetchone()["id"]}/cancel')
    cancelled = door.post(f'/organizer/{eid}/controle', data={'code': ticket['code']})
    assert 'Billet annulé' in cancelled.text
    assert 'Billet inconnu' in door.post(f'/organizer/{eid}/controle', data={'code': 'JOIN-XXXX-YY'}).text


def test_simulated_refunds_follow_the_cancellation_policy(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    guest = user(db, 'guest@example.test')
    user(db, 'admin@example.test', ('member', 'admin'), interests=False)

    def priced(title, policy, hours, cents=2000):
        eid = event(db, owner, 4)
        db.execute(
            """UPDATE events SET title=%s, price_cents=%s, cancellation_policy=%s,
               starts_at=now()+make_interval(hours => %s), ends_at=now()+make_interval(hours => %s)+interval '2 hours'
               WHERE id=%s""",
            (title, cents, policy, hours, hours, eid),
        )
        return eid

    flexible = priced('Flexible loin', 'flexible', 48)
    guest_client = login(app, 'guest@example.test')
    assert guest_client.post(f'/activities/{flexible}/reserve', data={'payment_simulated': '1'}).status_code == 302
    page = guest_client.get('/account').text
    assert 'Remboursement simulé' in page and '20 €' in page
    booking = db.execute('SELECT id FROM reservations WHERE event_id=%s', (flexible,)).fetchone()['id']
    assert guest_client.post(f'/reservations/{booking}/cancel').status_code == 302
    stored = db.execute('SELECT refund_cents, refund_status, status FROM reservations WHERE id=%s', (booking,)).fetchone()
    assert stored['status'] == 'cancelled' and stored['refund_cents'] == 2000 and stored['refund_status'] == 'simulated'
    assert 'Remboursement simulé' in db.execute(
        "SELECT body FROM dev_outbox WHERE recipient='guest@example.test' ORDER BY id DESC LIMIT 1"
    ).fetchone()['body']

    late = priced('Flexible tard', 'flexible', 2)
    assert guest_client.post(f'/activities/{late}/reserve', data={'payment_simulated': '1'}).status_code == 302
    late_id = db.execute('SELECT id FROM reservations WHERE event_id=%s', (late,)).fetchone()['id']
    assert guest_client.post(f'/reservations/{late_id}/cancel').status_code == 302
    assert db.execute('SELECT refund_cents FROM reservations WHERE id=%s', (late_id,)).fetchone()['refund_cents'] == 0

    half = priced('Modérée', 'moderate', 48)
    assert guest_client.post(f'/activities/{half}/reserve', data={'payment_simulated': '1'}).status_code == 302
    half_id = db.execute('SELECT id FROM reservations WHERE event_id=%s', (half,)).fetchone()['id']
    assert guest_client.post(f'/reservations/{half_id}/cancel').status_code == 302
    assert db.execute('SELECT refund_cents FROM reservations WHERE id=%s', (half_id,)).fetchone()['refund_cents'] == 1000

    strict = priced('Stricte', 'strict', 96)
    organizer = login(app, 'owner@example.test')
    assert guest_client.post(f'/activities/{strict}/reserve', data={'payment_simulated': '1'}).status_code == 302
    assert organizer.post(f'/organizer/{strict}/cancel').status_code == 302
    assert db.execute(
        "SELECT refund_cents FROM reservations WHERE event_id=%s", (strict,)
    ).fetchone()['refund_cents'] == 2000
    manual = priced('Manuelle', 'strict', 96, cents=1500)
    assert guest_client.post(f'/activities/{manual}/reserve', data={'payment_simulated': '1'}).status_code == 302
    manual_id = db.execute('SELECT id FROM reservations WHERE event_id=%s', (manual,)).fetchone()['id']
    admin = login(app, 'admin@example.test')
    assert admin.post(f'/admin/reservations/{manual_id}/remboursement', data={'refund': '4'}).status_code == 400
    assert admin.post(f'/admin/reservations/{manual_id}/remboursement', data={'refund': '4', 'confirm': '1'}).status_code == 302
    assert db.execute('SELECT refund_status, refund_cents FROM reservations WHERE id=%s', (manual_id,)).fetchone()['refund_status'] == 'manual'


def test_google_sign_in_is_hidden_until_configured_and_links_accounts(app, db):
    from urllib.parse import parse_qs, urlparse
    assert 'Continuer avec Google' not in app.test_client().get('/login').text
    assert app.test_client().get('/auth/google').status_code == 404
    app.config['GOOGLE_CLIENT_ID'] = 'test-client'
    app.config['GOOGLE_CLIENT_SECRET'] = 'test-secret'
    app.config['PUBLIC_BASE_URL'] = 'https://isep.wangjiahan.com'
    client = app.test_client()
    assert 'Continuer avec Google' in client.get('/login').text
    assert 'Continuer avec Google' in client.get('/signup').text
    start = client.get('/auth/google')
    assert start.status_code == 302 and 'accounts.google.com' in start.location
    query = parse_qs(urlparse(start.location).query)
    assert query['redirect_uri'] == ['https://isep.wangjiahan.com/auth/google/callback']
    assert query['client_id'] == ['test-client']
    assert client.get('/auth/google/callback?state=wrong').status_code == 400
    with client.session_transaction() as sess:
        nonce = sess['google_nonce']
        state = sess['google_state']
    app.google_userinfo = lambda: {
        'sub': 'google-sub-1', 'email': 'ada@example.test', 'email_verified': True,
        'name': 'Ada Google', 'nonce': nonce,
    }
    landing = client.get(f'/auth/google/callback?state={state}')
    assert urlparse(landing.headers['Location']).path == '/interests'
    stored = db.execute("SELECT email_verified_at, google_sub FROM users WHERE email='ada@example.test'").fetchone()
    assert stored['google_sub'] == 'google-sub-1' and stored['email_verified_at']
    user(db, 'known@example.test')
    again = app.test_client()
    again.get('/auth/google')
    with again.session_transaction() as sess:
        nonce = sess['google_nonce']
        state = sess['google_state']
    app.google_userinfo = lambda: {
        'sub': 'google-sub-2', 'email': 'known@example.test', 'email_verified': True,
        'name': 'Known', 'nonce': nonce,
    }
    landing = again.get(f'/auth/google/callback?state={state}')
    assert urlparse(landing.headers['Location']).path == '/'
    assert db.execute("SELECT google_sub FROM users WHERE email='known@example.test'").fetchone()['google_sub'] == 'google-sub-2'


def test_share_poster_and_open_graph_use_the_cover(app, db):
    owner = user(db, roles=('member', 'organizer'))
    eid = event(db, owner)
    db.execute("UPDATE events SET title='Sortie à partager', category_id=(SELECT id FROM categories WHERE name='Cuisine') WHERE id=%s", (eid,))
    app.config['PUBLIC_BASE_URL'] = 'https://isep.wangjiahan.com'
    page = app.test_client().get(f'/activities/{eid}')
    assert 'Copier le lien' in page.text and 'WhatsApp' in page.text and 'Télécharger l’affiche' in page.text
    assert 'property="og:image"' in page.text
    assert 'https://isep.wangjiahan.com/static/covers/cuisine/' in page.text
    assert 'twitter:image' in page.text
    poster = app.test_client().get(f'/activities/{eid}/affiche.png')
    assert poster.status_code == 200 and poster.mimetype == 'image/png' and poster.data.startswith(b'\x89PNG')
    assert len(poster.data) > 1000


def test_organizer_dashboard_sums_views_fill_and_revenue(app, db):
    owner = user(db, 'owner@example.test', roles=('member', 'organizer'))
    eid = event(db, owner, 10)
    db.execute("UPDATE events SET title='Atelier suivi', price_cents=1000, view_count=12 WHERE id=%s", (eid,))
    for index in range(4):
        member = user(db, f'dash{index}@example.test')
        db.execute('INSERT INTO reservations(member_id, event_id) VALUES (%s, %s)', (member, eid))
    db.execute(
        "INSERT INTO reviews(event_id, author_id, rating, comment) VALUES (%s, %s, 4, 'Très bonne organisation.')",
        (eid, owner),
    )
    page = login(app, 'owner@example.test').get('/organizer/tableau')
    assert page.status_code == 200
    assert '12' in page.text and '40 %' in page.text and '40 €' in page.text and '<svg' in page.text
    assert 'Atelier suivi' in page.text
    assert login(app, 'dash0@example.test').get('/organizer/tableau').status_code == 403


def test_admin_office_exports_edits_and_impersonates(app, db):
    admin_id = user(db, 'boss@example.test', ('member', 'admin'), interests=False)
    member = user(db, 'cible@example.test')
    owner = user(db, 'orga@example.test', roles=('member', 'organizer'))
    eid = event(db, owner, 4)
    db.execute("UPDATE events SET title='Sortie admin' WHERE id=%s", (eid,))
    db.execute(
        "INSERT INTO reviews(event_id, author_id, rating, comment) VALUES (%s, %s, 5, 'Commentaire initial.')",
        (eid, member),
    )
    member_client = login(app, 'cible@example.test')
    assert member_client.get('/admin/utilisateurs').status_code == 403
    office = login(app, 'boss@example.test')
    assert 'cible@example.test' in office.get('/admin/utilisateurs.csv').data.decode()
    assert office.post('/admin/utilisateurs/bulk', data={'ids': [member], 'action': 'ban', 'confirm': '1'}).status_code == 302
    assert db.execute('SELECT status FROM users WHERE id=%s', (member,)).fetchone()['status'] == 'banned'
    db.execute("UPDATE users SET status='active' WHERE id=%s", (member,))
    review_id = db.execute('SELECT id FROM reviews WHERE author_id=%s', (member,)).fetchone()['id']
    assert office.post(f'/admin/avis/{review_id}/texte', data={'rating': '2', 'comment': 'Texte corrigé par l’admin.'}).status_code == 302
    assert db.execute('SELECT rating, comment FROM reviews WHERE id=%s', (review_id,)).fetchone()['comment'] == 'Texte corrigé par l’admin.'
    assert office.post('/admin/reglages', data={
        'site_name': 'Joinly', 'banner': 'Annonce de test', 'booking_cutoff_minutes': '0',
        'default_cancellation_policy': 'flexible', 'heat_recent_weight': '10', 'heat_fill_weight': '1', 'heat_view_cap': '400',
        'listed_ids': [eid], 'pinned_ids': [eid],
    }).status_code == 302
    assert 'Annonce de test' in office.get('/').text
    assert 'Sortie admin' in office.get('/').text
    assert office.post(f'/admin/utilisateurs/{member}/consulter').status_code == 302
    assert 'Consultation en tant que' in office.get('/account').text
    assert office.post('/impersonation/stop').status_code == 302
    assert db.execute("SELECT count(*) AS n FROM audit_log WHERE action='impersonate.start'").fetchone()['n'] == 1
    assert 'impersonate.start' in office.get('/admin/journal').text
