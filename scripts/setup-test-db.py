"""Create/reset only the explicitly dedicated joinly_test database, never joinly."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
def psql(sql, database='postgres'):
    subprocess.run(['runuser','-u','postgres','--','psql','-X','-v','ON_ERROR_STOP=1','-d',database], input=sql, text=True, check=True, stdout=subprocess.DEVNULL)
exists = subprocess.check_output(['runuser','-u','postgres','--','psql','-At','-c',"SELECT 1 FROM pg_database WHERE datname='joinly_test'"], text=True).strip()
if exists:
    raise SystemExit('joinly_test already exists. Run pytest against it; this script does not reset an existing database.')
psql('CREATE DATABASE joinly_test OWNER joinly_owner;')
psql('REVOKE ALL ON DATABASE joinly_test FROM PUBLIC; GRANT CONNECT ON DATABASE joinly_test TO joinly_app;')
for path in sorted((root/'database/migrations').glob('*.sql')):
    psql('SET ROLE joinly_owner;\n'+path.read_text(), 'joinly_test')
psql('GRANT USAGE ON SCHEMA public TO joinly_app; GRANT SELECT,INSERT,UPDATE,DELETE,TRUNCATE ON ALL TABLES IN SCHEMA public TO joinly_app; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO joinly_app;', 'joinly_test')
print('Isolated joinly_test database created.')
