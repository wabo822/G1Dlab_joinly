"""Configure Brevo interactively on the server without printing SMTP secrets."""
import getpass
import os
from pathlib import Path
import re
import smtplib
import ssl
import subprocess
import tempfile


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root on the Joinly server.')
    path = Path('/etc/joinly.env')
    if not path.exists():
        raise SystemExit('Joinly service configuration not found.')
    login = input('Brevo SMTP login: ').strip()
    sender = input('Verified sender email address: ').strip()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', sender):
        raise SystemExit('Invalid sender email address.')
    key = getpass.getpass('Brevo SMTP key (hidden): ')
    if not login or not key or any(ch in login + sender + key for ch in '\r\n\x00'):
        raise SystemExit('Invalid SMTP credentials.')
    try:
        with smtplib.SMTP('smtp-relay.brevo.com', 587, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(login, key)
    except (OSError, smtplib.SMTPException):
        raise SystemExit('SMTP connection or authentication failed; configuration unchanged.')
    values = {'SMTP_HOST':'smtp-relay.brevo.com', 'SMTP_PORT':'587',
              'SMTP_USER':login, 'SMTP_PASSWORD':key, 'MAIL_FROM':sender}
    # systemd EnvironmentFile double-quote escaping; no shell expansion is involved.
    def quoted(value):
        return '"' + value.replace('\\','\\\\').replace('"','\\"') + '"'
    content = path.read_text()
    lines = [line for line in content.splitlines() if line.split('=',1)[0] not in values]
    lines += [name+'='+quoted(value) for name,value in values.items()]
    stat = path.stat()
    fd, temp = tempfile.mkstemp(prefix='.joinly-mail-', dir=path.parent)
    try:
        with os.fdopen(fd,'w') as file:
            file.write('\n'.join(lines)+'\n')
        os.chown(temp, stat.st_uid, stat.st_gid)
        os.chmod(temp, stat.st_mode & 0o777)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    subprocess.run(['systemctl','restart','joinly'],check=True)
    print('SMTP authenticated and service restarted. No email was sent.')
    print('Sender/domain verification must be completed in Brevo. Test delivery using the password-reset page.')


if __name__ == '__main__':
    main()
