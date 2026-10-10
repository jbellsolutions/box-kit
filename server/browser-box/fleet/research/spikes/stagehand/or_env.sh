#!/bin/sh
# Load only OPENROUTER_API_KEY from the .env file (ENV_FILE, default .env) into this process env, then exec the command.
OPENROUTER_API_KEY="$(grep -E '^OPENROUTER_API_KEY=' "${ENV_FILE:-.env}" | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
export OPENROUTER_API_KEY
exec "$@"
