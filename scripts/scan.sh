#!/usr/bin/env bash
# The gate before anything is pushed: no secret values, no owner hosts or ids, no key-shaped strings.
#   scripts/scan.sh [secrets env file...]
set -uo pipefail
KIT=$(cd "$(dirname "$0")/.." && pwd); cd "$KIT"
fail=0
FILES=$(git ls-files -co --exclude-standard | grep -v '^scripts/scan.sh$')
for f in "$@"; do
  while IFS= read -r line; do
    v=${line#*=}; v=${v%\"}; v=${v#\"}; v=${v%\'}; v=${v#\'}
    [ ${#v} -ge 12 ] || continue
    if printf '%s\n' $FILES | xargs grep -lF -- "$v" 2>/dev/null | grep -q .; then
      echo "SECRET VALUE of ${line%%=*} (from $f) found"; fail=1; fi
  done < <(sed -E "s/^export //" "$f" | grep -E "^[A-Z_][A-Z0-9_]*=" | grep -E "^[A-Z0-9_]*(TOKEN|KEY|SECRET|PASSWORD|PASS|CREDENTIAL|COOKIE|AUTH)[A-Z0-9_]*=")
done
OWNER='64-225-11-38|64\.225\.11\.38|167-71-241-147|167\.71\.241\.147|superbrowser\.online|603021338|579103369|eed51fbb|Revenue Partner|ssh browser-box|/Users/home|jbellsolutions/jev-automation'
if printf '%s\n' $FILES | xargs grep -nE "$OWNER" 2>/dev/null | grep -v '^scripts/'; then echo "OWNER-SPECIFIC value found (above)"; fail=1; fi
KEYS='sk-or-v1-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|dop_v1_[a-f0-9]{40,}|apify_api_[A-Za-z0-9]{20,}'
if printf '%s\n' $FILES | xargs grep -nE "$KEYS" 2>/dev/null; then echo "KEY-SHAPED string found (above)"; fail=1; fi
[ $fail -eq 0 ] && echo "scan: clean ($(printf '%s\n' $FILES | wc -l | tr -d ' ') files)"
exit $fail
