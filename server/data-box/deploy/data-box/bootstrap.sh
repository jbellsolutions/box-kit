#!/usr/bin/env bash
# One-time, idempotent host setup for data-box. Run as root on the droplet:
#   bash deploy/data-box/bootstrap.sh
# Creates the service user, directories, the source checkout and /etc/data-box.env (with a
# generated DATABOX_TOKEN, never printed). Caddy and provider keys are separate steps (docs/deploy.md).
# The droplet has no GitHub credentials: ship.sh copies origin/master over as a git bundle first,
# and the source checkout is a clone of that bundle.
set -euo pipefail

REPO="${DATABOX_REPO:-/opt/data-box/incoming/data-box.bundle}"

id databox >/dev/null 2>&1 || useradd --system --home-dir /var/lib/data-box --shell /usr/sbin/nologin databox
install -d -o root -g root -m 0755 /opt/data-box /opt/data-box/releases
install -d -o databox -g databox -m 0750 /var/lib/data-box

if [ ! -d /opt/data-box/source/.git ]; then
  git clone --quiet --no-checkout "$REPO" /opt/data-box/source
fi

if [ ! -f /etc/data-box.env ]; then
  install -o root -g databox -m 0640 /dev/null /etc/data-box.env
fi
chown root:databox /etc/data-box.env
chmod 0640 /etc/data-box.env

set_default() {  # set KEY only if the file does not already have it
  grep -q "^$1=" /etc/data-box.env || printf '%s=%s\n' "$1" "$2" >> /etc/data-box.env
}
grep -q '^DATABOX_TOKEN=.' /etc/data-box.env || {
  sed -i '/^DATABOX_TOKEN=/d' /etc/data-box.env
  printf 'DATABOX_TOKEN=%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" >> /etc/data-box.env
}
set_default DATABOX_HOST 127.0.0.1
set_default DATABOX_PORT 8092
set_default DATABOX_STATE_DIR /var/lib/data-box

echo "data-box host ready: /opt/data-box, /var/lib/data-box, /etc/data-box.env (token set)"
