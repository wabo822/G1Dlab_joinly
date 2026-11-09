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
        db.execute('TRUNCATE users,events,categories,faqs,legal_pages,contact_requests,rate_limits,user_interests CASCADE')
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
    result = db.execute('INSERT INTO users(email,display_name,password_hash) VALUES (%s,%s,%s) RETURNING id', (email, email.split('@')[0], generate_password_hash(PASSWORD))).fetchone()['id']
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
    ids = [str(category_id) for category_id in ensure_categories(db)]
    form = {'email':'  NEW@Example.test ', 'display_name':'New', 'password':PASSWORD, 'role':'organizer', 'interest_ids': ids[:3]}
    assert client.post('/signup', data={**form, 'interest_ids': ids[:2]}).status_code == 400
    assert db.execute("SELECT id FROM users WHERE email='new@example.test'").fetchone() is None
    assert client.post('/signup', data={**form, 'interest_ids': ids[:2] + ['999999']}).status_code == 400
    assert client.post('/signup', data=form).status_code == 302
    row = db.execute("SELECT * FROM users WHERE email='new@example.test'").fetchone()
    assert row['password_hash'] != PASSWORD
    roles = db.execute('SELECT r.name FROM roles r JOIN user_roles ur ON r.id=ur.role_id WHERE user_id=%s',(row['id'],)).fetchall()
    assert {r['name'] for r in roles} == {'member','organizer'}
    assert db.execute('SELECT count(*) AS n FROM user_interests WHERE user_id=%s', (row['id'],)).fetchone()['n'] == 3
    assert client.post('/signup', data=form).status_code == 409
    assert client.post('/signup', data={**form,'email':'admin@example.test','role':'admin'}).status_code == 400
    assert client.post('/signup', data={**form,'password':'short'}).status_code == 400


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
