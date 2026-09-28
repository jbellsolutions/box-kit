#!/usr/bin/env bash
# Refresh server/ from the private repos at pinned commits, strip owner-specific values, and
# refuse to finish if anything that looks like a secret or an owner's host is left.
#   scripts/export.sh <browser-box clone> <bb ref> <data-box clone> <db ref> [secrets file...]
# Each secrets file is a KEY=value env file whose values must not appear anywhere in the kit.
set -euo pipefail
BB=$1 BB_REF=$2 DB=$3 DB_REF=$4; shift 4
KIT=$(cd "$(dirname "$0")/.." && pwd)
rm -rf "$KIT/server/browser-box" "$KIT/server/data-box"
mkdir -p "$KIT/server/browser-box" "$KIT/server/data-box"

# browser-box: the whole repo minus its own plugin copy (the kit ships the plugins) and bench data.
git -C "$BB" archive "$BB_REF" | tar -x -C "$KIT/server/browser-box" \
  --exclude='.claude-plugin' --exclude='.mcp.json' --exclude='skills' --exclude='commands' --exclude='bench' --exclude='tests/test_plugin.py'

# data-box: only its own package; the repo still carries the legacy Super Browser tree.
git -C "$DB" archive "$DB_REF" src/data_box tests/databox deploy/data-box docs/how-it-works.md \
  docs/sources docs/openapi.json docs/tools.md | tar -x -C "$KIT/server/data-box"
rm -f "$KIT/server/data-box/tests/databox/test_drift.py"  # checks the source repo's own doc set

# Kit-owned packaging for data-box (its repo deploys with systemd; the kit runs it in Docker).
cp -R "$KIT/overlays/data-box/." "$KIT/server/data-box/"

# Owner-specific values -> placeholders.
find "$KIT/server" -type f \( -name '*.py' -o -name '*.md' -o -name '*.json' -o -name '*.yml' -o -name 'Caddyfile*' -o -name '*.example' \) -print0 |
  xargs -0 sed -i '' -E \
    -e 's/64-225-11-38\.sslip\.io/your-box.example.com/g' \
    -e 's/167-71-241-147\.sslip\.io/your-data-box.example.com/g' \
    -e 's/167\.71\.241\.147\.nip\.io/your-data-box.example.com/g'

echo "$BB_REF" > "$KIT/server/browser-box/.exported-from"
echo "$DB_REF" > "$KIT/server/data-box/.exported-from"
"$KIT/scripts/scan.sh" "$@"
