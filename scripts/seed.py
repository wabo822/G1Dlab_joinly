"""Seed reference content. Pass --demo to load the lived-in demonstration dataset.

Nothing is deleted. Existing accounts and non-placeholder legal pages are left
unchanged. Credentials for the demonstration accounts are in docs/demo-accounts.md.
"""
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
from app.legal_content import ensure_faqs, publish_legal_defaults
from app.seed_demo import CATEGORIES, seed_demo

parser = argparse.ArgumentParser()
parser.add_argument('--demo', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
load_dotenv(root / '.env')
with psycopg.connect(row_factory=dict_row) as db:
    for name, icon in CATEGORIES:
        db.execute(
            '''INSERT INTO categories(name, icon) VALUES (%s, %s)
               ON CONFLICT (name) DO UPDATE SET icon=EXCLUDED.icon''',
            (name, icon),
        )
    ensure_faqs(db)
    published = publish_legal_defaults(db, require_privacy=False)
    if published:
        print('Legal pages published:', ', '.join(published))
    if 'privacy' not in published and not db.execute(
        "SELECT 1 FROM legal_pages WHERE kind='privacy'"
    ).fetchone():
        print('Privacy page not stored yet. Apply database migration 003_privacy, then rerun this script.')
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
    if args.demo:
        stats = seed_demo(db)
        print(
            'Demonstration data ready: '
            f"{stats['users_created']} new accounts, {stats['events_created']} new activities, "
            f"{stats['bookings_created']} new registrations."
        )
print('Initial content ready.')
