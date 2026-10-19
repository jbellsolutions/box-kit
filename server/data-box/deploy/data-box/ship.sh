#!/usr/bin/env bash
# Ship origin/master to the droplet and activate it. Run from a checkout that can reach GitHub:
#   deploy/data-box/ship.sh [root@your-data-box.example.com]
# The droplet has no GitHub credentials, so the code travels as a git bundle. The activator's
# merged-to-master guard then checks against the bundle's master, which this script only builds
# when the local master is exactly origin/master.
set -euo pipefail
HOST="${1:-root@your-data-box.example.com}"
ssh_() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" "$@"; }

cd "$(git rev-parse --show-toplevel)"
git fetch -q origin
if [ "$(git rev-parse master)" != "$(git rev-parse origin/master)" ]; then
  echo "local master is not origin/master; run: git checkout master && git merge --ff-only origin/master" >&2
  exit 1
fi
REV=$(git rev-parse --short=7 origin/master)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
git bundle create -q "$TMP/data-box.bundle" master
ssh_ 'install -d -m 0755 /opt/data-box/incoming'
scp -q -o BatchMode=yes "$TMP/data-box.bundle" "$HOST:/opt/data-box/incoming/data-box.bundle"
echo "shipped $REV; activating"
ssh_ "git -C /opt/data-box/source fetch -q origin \
  && git -C /opt/data-box/source show $REV:deploy/data-box/activate_release.py > /root/activate-data-box.py \
  && python3 /root/activate-data-box.py $REV"
