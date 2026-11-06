#!/usr/bin/env bash
# Run from the repository as root, after database migrations and seeding.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$EUID" -ne 0 ]]; then
  echo 'Run as root on the server.' >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  echo 'Missing .env. Configure the database and SECRET_KEY first.' >&2
  exit 1
fi
if ! id joinly >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/joinly --create-home --shell /usr/sbin/nologin joinly
fi
install -d -m 755 /opt/joinly/releases
release_dir=$(mktemp -d /opt/joinly/releases/v1-XXXXXXXX)
chmod 755 "$release_dir"
cp -R app "$release_dir/app"
chmod -R a+rX "$release_dir/app"
if [[ ! -x /opt/joinly/venv/bin/python ]]; then
  python3 -m venv /opt/joinly/venv
fi
/opt/joinly/venv/bin/pip install -q -r requirements.txt
if [[ ! -f /etc/joinly.env ]]; then
  install -o root -g joinly -m 640 .env /etc/joinly.env
fi
ln -s "$release_dir" /opt/joinly/current.new
mv -Tf /opt/joinly/current.new /opt/joinly/current
install -m 644 deploy/joinly.service /etc/systemd/system/joinly.service
systemctl daemon-reload
systemctl enable joinly.service
systemctl restart joinly.service
systemctl --no-pager --full status joinly.service
