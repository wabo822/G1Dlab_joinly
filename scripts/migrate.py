"""Apply pending SQL migrations as the local postgres administrator (run as root)."""
from pathlib import Path
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--database', default='joinly', choices=['joinly', 'joinly_test'])
args = parser.parse_args()
base = ['runuser', '-u', 'postgres', '--', 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-At', '-d', args.database]
result = subprocess.run(base + ['-c', 'SELECT version FROM schema_migrations'], capture_output=True, text=True)
if result.returncode:
    raise SystemExit('Initialize the database with database/scripts/setup-local.py first.')
applied = set(result.stdout.splitlines())
for path in sorted((Path(__file__).resolve().parents[1] / 'database/migrations').glob('*.sql')):
    if path.stem in applied:
        continue
    subprocess.run(base, input='SET ROLE joinly_owner;\n' + path.read_text(), text=True, check=True)
    print('Applied:', path.stem)
