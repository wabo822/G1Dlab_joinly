"""Seed initial content, optionally with clearly identified demo events; never overwrite content."""
import argparse
import os
from pathlib import Path
import secrets
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash

parser = argparse.ArgumentParser()
parser.add_argument('--demo', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
load_dotenv(root / '.env')
with psycopg.connect(row_factory=dict_row) as db:
    for category in ['Nature & plein air', 'Sport', 'Arts & culture', 'Jeux & rencontres', 'Cuisine']:
        db.execute('INSERT INTO categories(name) VALUES (%s) ON CONFLICT DO NOTHING', (category,))
    if not db.execute('SELECT 1 FROM faqs LIMIT 1').fetchone():
        for i, (q, a) in enumerate([
            ('Comment réserver une activité ?', 'Créez un compte, ouvrez la fiche d’une activité et cliquez sur « Réserver ma place ». Votre inscription apparaît dans « Mon espace ».'),
            ('Puis-je annuler mon inscription ?', 'Oui, depuis votre espace, avant le début de l’activité. Votre place redevient disponible.'),
            ('Les activités sont-elles payantes ?', 'Cette première version propose uniquement des activités gratuites.'),
            ('Comment organiser une activité ?', 'Choisissez le profil organisateur lors de votre inscription. Vous pourrez enregistrer un brouillon, puis le publier depuis votre espace organisateur.'),
            ('Quelles informations voit l’organisateur ?', 'L’organisateur voit les noms affichés des participants confirmés, sans leurs adresses e-mail.'),
        ]):
            db.execute('INSERT INTO faqs(question,answer,sort_order,published) VALUES (%s,%s,%s,true)', (q,a,i))
    for kind, content in [
        ('terms', 'Prototype pédagogique Joinly — G1D Lab\n\nCette version permet de découvrir des activités gratuites, de créer un compte et de gérer ses inscriptions. Les activités portant la mention [Démo] sont fictives : ne vous déplacez pas pour ces exemples.\n\nUne inscription correspond à une place. Elle peut être annulée avant le début de l’activité. L’organisateur peut annuler une activité, ce qui annule les inscriptions associées.\n\nUtilisez un nom affiché respectueux. Ne publiez pas de contenu illicite ni les coordonnées privées d’autrui. Pour une difficulté ou une demande concernant vos données, utilisez le formulaire de contact.\n\nDocument de démonstration à faire valider et compléter par le responsable du projet avant une ouverture au public.'),
        ('legal_notice', 'Joinly — projet pédagogique de G1D Lab\n\nContact : formulaire accessible depuis le pied de page.\n\nCette instance est un prototype de développement. L’identité juridique de l’éditeur, le responsable de publication, les coordonnées et l’identité de l’hébergeur restent à renseigner par le responsable du projet avant ouverture au public.\n\nLes comptes, inscriptions, préférences et demandes de contact sont enregistrés dans la base du projet. Les cookies servent à la connexion et à la protection des formulaires. Aucun outil publicitaire n’est intégré à cette version. La durée de conservation et les modalités d’exercice des droits restent à valider.\n\nLes exemples marqués [Démo] sont fictifs.')]:
        if not db.execute('SELECT 1 FROM legal_pages WHERE kind=%s', (kind,)).fetchone():
            db.execute('INSERT INTO legal_pages(kind,version,content,published_at) VALUES (%s,1,%s,now())', (kind, content))
    admin = db.execute("SELECT u.id FROM users u JOIN user_roles ur ON ur.user_id=u.id JOIN roles r ON r.id=ur.role_id WHERE r.name='admin' LIMIT 1").fetchone()
    if not admin:
        password = secrets.token_urlsafe(24)
        local = root / '.local'
        local.mkdir(exist_ok=True, mode=0o700)
        fd = os.open(local / 'initial-admin.txt', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write('Email: admin@joinly.test\nPassword: '+password+'\nLocal bootstrap administrator; replace before production.\n')
        admin = db.execute('INSERT INTO users(email,display_name,password_hash) VALUES (%s,%s,%s) RETURNING id', ('admin@joinly.test', 'Équipe Joinly', generate_password_hash(password))).fetchone()
        db.execute('INSERT INTO user_roles(user_id,role_id) SELECT %s,id FROM roles', (admin['id'],))
        print('Initial administrator credentials saved to .local/initial-admin.txt (mode 600).')
    if args.demo and not db.execute("SELECT 1 FROM events WHERE title LIKE '[Démo]%%' LIMIT 1").fetchone():
        for day, title, category, location, capacity in [
            (3, 'Balade au bord de la Seine', 'Nature & plein air', 'Paris · Quai de la Tournelle', 12),
            (5, 'À vos jeux, prêts, partez !', 'Jeux & rencontres', 'Paris · Maison de quartier', 8),
            (7, 'Dessiner la ville ensemble', 'Arts & culture', 'Paris · Jardin du Luxembourg', 10),
            (9, 'Un footing à votre rythme', 'Sport', 'Paris · Parc de Bercy', 15),
            (11, 'Un café, des idées, des rencontres', 'Jeux & rencontres', 'Paris · Café de démonstration', 6),
            (14, 'Les saveurs du dimanche', 'Cuisine', 'Paris · Atelier de démonstration', 8),
        ]:
            db.execute('''INSERT INTO events(organizer_id,category_id,title,description,location,starts_at,ends_at,capacity,status)
                VALUES (%s,(SELECT id FROM categories WHERE name=%s),%s,%s,%s,
                date_trunc('day',now())+%s::interval+interval '14 hours',date_trunc('day',now())+%s::interval+interval '16 hours',%s,'published')''',
                (admin['id'],category,'[Démo] '+title,'Activité fictive pour découvrir Joinly. Aucun événement réel n’est organisé à cette adresse.\n\nCe parcours permet de tester la réservation, la liste des participants et l’annulation.',location,f'{day} days',f'{day} days',capacity))
print('Initial content ready. Demo data is explicitly labeled when requested.')
