"""Run after pytest, with a server using joinly_test at 127.0.0.1:8001."""
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from playwright.sync_api import sync_playwright, expect
from werkzeug.security import generate_password_hash

root = Path(__file__).resolve().parents[1]
load_dotenv(root / '.env')
password = 'Browser test password only 123!'
with psycopg.connect(dbname='joinly_test', autocommit=True) as db:
    db.execute('TRUNCATE users,events,categories,faqs,legal_pages,contact_requests,rate_limits CASCADE')
    db.execute("INSERT INTO categories(name) VALUES ('Nature')")
    uid = db.execute('INSERT INTO users(email,display_name,password_hash) VALUES (%s,%s,%s) RETURNING id', ('ui-admin@example.test','Admin UI',generate_password_hash(password))).fetchone()[0]
    db.execute("INSERT INTO user_roles SELECT %s,id FROM roles WHERE name IN ('member','admin')",(uid,))

base = 'http://127.0.0.1:8001'
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def signup(email,name,role):
        page.goto(base+'/signup')
        page.get_by_label('Votre nom affiché').fill(name)
        page.get_by_label('Adresse e-mail').fill(email)
        page.get_by_label('Mot de passe',exact=True).fill(password)
        page.get_by_label('Je souhaite').select_option(role)
        page.get_by_role('button',name='Créer mon compte').click()
        expect(page).to_have_url(base+'/login')
        signin(email)

    def signin(email):
        page.goto(base+'/login')
        page.get_by_label('Adresse e-mail').fill(email)
        page.get_by_label('Mot de passe',exact=True).fill(password)
        page.get_by_role('button',name='Se connecter',exact=True).click()
        expect(page).to_have_url(base+'/account')

    signup('ui-organizer@example.test','Organisateur UI','organizer')
    page.goto(base+'/organizer/new')
    page.get_by_label('Titre',exact=True).fill('Balade test navigateur')
    page.get_by_label('Description',exact=True).fill('Une activité pour vérifier tout le parcours.')
    page.get_by_label('Lieu de rendez-vous').fill('Paris')
    day=(datetime.now()+timedelta(days=5)).strftime('%Y-%m-%d')
    page.get_by_label('Début (heure de Paris)').fill(day+'T14:00')
    page.get_by_label('Fin (heure de Paris)').fill(day+'T16:00')
    page.get_by_label('Nombre de places').fill('2')
    page.get_by_label('Publication').select_option('published')
    page.get_by_role('button',name='Enregistrer l’activité').click()
    expect(page).to_have_url(base+'/organizer')
    activity_path=page.get_by_role('link',name='Balade test navigateur',exact=True).get_attribute('href')
    page.get_by_role('button',name='Déconnexion').click()

    signup('ui-member@example.test','Membre UI','member')
    page.goto(base+activity_path)
    page.get_by_role('button',name='Réserver ma place').click()
    expect(page.get_by_text('Votre place est réservée !',exact=False)).to_be_visible()
    page.get_by_role('button',name='Déconnexion').click()
    signin('ui-organizer@example.test')
    page.goto(base+'/organizer')
    page.get_by_role('link',name='Voir les participants').click()
    expect(page.get_by_text('Membre UI',exact=True)).to_be_visible()
    assert 'ui-member@example.test' not in page.content()
    page.get_by_role('button',name='Déconnexion').click()
    signin('ui-member@example.test')
    page.get_by_role('button',name='Annuler ma réservation').click()
    expect(page.get_by_text('Réservation annulée.',exact=True)).to_be_visible()

    page.goto(base+'/contact')
    page.get_by_label('Nom',exact=True).fill('Membre UI')
    page.get_by_label('E-mail de réponse').fill('ui-member@example.test')
    page.get_by_label('Objet').fill('Question navigateur')
    page.get_by_label('Message',exact=True).fill('Un message de test enregistré.')
    page.get_by_role('button',name='Envoyer ma demande').click()
    expect(page.get_by_text('Votre demande a été enregistrée.',exact=False)).to_be_visible()
    page.get_by_role('button',name='Déconnexion').click()
    signin('ui-admin@example.test')
    page.goto(base+'/admin')
    expect(page.get_by_text('Question navigateur',exact=True)).to_be_visible()

    for width in (375,768,1440):
        page.set_viewport_size({'width':width,'height':1000})
        for path in ['/', '/activities', activity_path, '/account', '/admin', '/contact', '/faq']:
            response=page.goto(base+path)
            assert response.status == 200, (path,response.status)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), (width,path)
    assert not errors, errors
    # Capture the demo instance, which is separate from the test database.
    page.get_by_role('button',name='Déconnexion').click()
    output=root/'.local'
    output.mkdir(exist_ok=True)
    for width,label in [(1440,'desktop'),(375,'mobile')]:
        page.set_viewport_size({'width':width,'height':1000})
        page.goto('http://127.0.0.1:8000/')
        page.screenshot(path=str(output/f'joinly-{label}.png'),full_page=True)
    browser.close()
print('Browser journey passed; no horizontal overflow at 375, 768, 1440px; no JavaScript errors.')
