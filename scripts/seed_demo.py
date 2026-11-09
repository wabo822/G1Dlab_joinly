"""Idempotent lived-in demonstration data.

Passwords and display names already stored are kept. Interests of demonstration
accounts and prices of demonstration activities are updated.

Usage, from the repository root, after migration 004_interests_pricing:

    .venv/bin/flask --app app seed-demo

The same data can be loaded with:

    .venv/bin/python scripts/seed_demo.py

Credentials are listed in docs/demo-accounts.md.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

from app.seed_demo import seed_demo

load_dotenv(ROOT / '.env')


def main():
    with psycopg.connect(row_factory=dict_row) as conn:
        stats = seed_demo(conn)
    print(
        'Demonstration data ready: '
        f"{stats['users_created']} new accounts, "
        f"{stats['events_created']} new activities, "
        f"{stats['bookings_created']} new registrations "
        f"({stats['demo_users']} demo accounts, {stats['demo_events']} demo activities in total)."
    )
    if stats['legal_published']:
        print('Legal pages published:', ', '.join(stats['legal_published']))
    print('Credentials: docs/demo-accounts.md')


if __name__ == '__main__':
    main()
