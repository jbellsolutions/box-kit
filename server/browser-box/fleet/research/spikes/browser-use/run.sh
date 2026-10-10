#!/usr/bin/env bash
# Runs spike_bu.py with OPENROUTER_API_KEY loaded from browser-box/.env into THIS process env only.
# Usage: run.sh <subcommand> [args...]   (outputs go wherever --out / --history / --state point)
set -euo pipefail
ENV_FILE="${ENV_FILE:-.env}"
VENV="${VENV:-.venv}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OPENROUTER_API_KEY="$(grep -E '^OPENROUTER_API_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d "\"'")" \
ANONYMIZED_TELEMETRY=false BROWSER_USE_SETUP_LOGGING=false \
  exec "$VENV/bin/python" "$HERE/spike_bu.py" "$@"
