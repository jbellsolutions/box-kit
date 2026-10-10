#!/usr/bin/env bash
# Starts fleet-spike-browseruse (127.0.0.1:3302) [and fleet-spike-browseruse2 on 3303 with TWO=1],
# waits for health, runs "$@", and ALWAYS removes the spike containers on exit (trap).
# Never touches browser-box-* or any other project's containers, or the Steel on 127.0.0.1:3000.
set -uo pipefail
IMG=ghcr.io/steel-dev/steel-browser-api:latest
VENV="${VENV:?set VENV to the scratch py/.venv}"
cleanup() { docker rm -f fleet-spike-browseruse fleet-spike-browseruse2 >/dev/null 2>&1 || true; }
trap cleanup EXIT
start() {  # name port
  docker run -d --name "$1" -p "127.0.0.1:$2:3000" --memory 1536m --cpus 1.2 \
    -e NODE_OPTIONS=--unhandled-rejections=warn -e DOMAIN="localhost:$2" -e CDP_DOMAIN="localhost:$2" "$IMG" >/dev/null
  for i in $(seq 1 60); do
    curl -fsS "http://127.0.0.1:$2/v1/health" >/dev/null 2>&1 && break; sleep 1
  done
  # /v1/health answers before Chromium is reachable: probe a real CDP round trip too
  for i in $(seq 1 60); do
    "$VENV/bin/python" -I -c "
import asyncio, json, sys, websockets
async def m():
    async with websockets.connect('ws://127.0.0.1:$2/', open_timeout=5) as w:
        await w.send(json.dumps({'id': 1, 'method': 'Browser.getVersion'}))
        r = json.loads(await asyncio.wait_for(w.recv(), 5)); sys.exit(0 if 'result' in r else 1)
asyncio.run(m())" >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "steel $1 did not become healthy" >&2; return 1
}
cleanup
start fleet-spike-browseruse 3302 || exit 1
if [ "${TWO:-0}" = "1" ]; then start fleet-spike-browseruse2 3303 || exit 1; fi
"$@"
