#!/bin/sh
# Copy the persisted profile's Cookies DB out of the spike container and list example.com cookies.
# Usage: disk_cookies.sh <container> <profile-dir-in-container>
C=${1:-fleet-spike-steel}; D=${2:-/app/api/user-data-dir}
T=$(mktemp -d /tmp/fleet-spike-steel-ck.XXXX)
docker cp "$C:$D/Default/Cookies" "$T/Cookies" >/dev/null 2>&1 || { echo "no Cookies file"; rm -rf "$T"; exit 0; }
docker cp "$C:$D/Default/Cookies-journal" "$T/Cookies-journal" >/dev/null 2>&1
sqlite3 "$T/Cookies" "select host_key,name from cookies where host_key like '%example.com%' order by name;" | tr '\n' ' '; echo
rm -rf "$T"
