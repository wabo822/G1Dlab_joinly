#!/usr/bin/env python3
"""Initialize a fresh local development database on Ubuntu; run as root."""
import os
from pathlib import Path
import secrets
import subprocess

root = Path(__file__).resolve().parents[2]

def sql(statement, database='postgres'):
    return subprocess.run(
        ['runuser', '-u', 'postgres', '--', 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-At', '-d', database],
        input=statement, text=True, capture_output=True, check=True,
    ).stdout

if os.geteuid() != 0:
    raise SystemExit('Run this script as root on the database server.')
if (root / '.env').exists():
    raise SystemExit('Existing .env found; refusing to overwrite credentials.')
if sql("SELECT 1 FROM pg_database WHERE datname='joinly';").strip() or sql(
    "SELECT 1 FROM pg_roles WHERE rolname IN ('joinly_owner', 'joinly_app');"
).strip():
    raise SystemExit('Joinly database/roles already exist; refusing to overwrite.')
password = secrets.token_hex(32)
# Persist credentials before creating roles; never print them or pass them as arguments.
fd = os.open(root / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as env:
    env.write(f'PGHOST=127.0.0.1\nPGPORT=5432\nPGDATABASE=joinly\nPGUSER=joinly_app\nPGPASSWORD={password}\n')
sql(f"CREATE ROLE joinly_owner NOLOGIN; CREATE ROLE joinly_app LOGIN PASSWORD '{password}';")
sql('CREATE DATABASE joinly OWNER joinly_owner;')
sql("ALTER DATABASE joinly SET timezone TO 'UTC'; REVOKE ALL ON DATABASE joinly FROM PUBLIC; GRANT CONNECT ON DATABASE joinly TO joinly_app;")
sql('REVOKE CREATE ON SCHEMA public FROM PUBLIC;', 'joinly')
sql('SET ROLE joinly_owner;\n' + (root / 'database/migrations/001_initial.sql').read_text(), 'joinly')
sql('''GRANT USAGE ON SCHEMA public TO joinly_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON users, user_roles, categories, member_preferences, events, reservations, faqs, legal_pages TO joinly_app;
GRANT SELECT ON roles TO joinly_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO joinly_app;''', 'joinly')
print('Created joinly database, owner and application role. Credentials saved to .env (mode 600).')
