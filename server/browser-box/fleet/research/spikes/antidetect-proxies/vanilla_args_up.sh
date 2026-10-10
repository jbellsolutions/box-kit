#!/bin/sh
# (Re)create the vanilla headful Chromium spike container on 127.0.0.1:3303 (capped) with extra Chromium args. No secrets.
# Usage: vanilla_args_up.sh "<extra chromium args>" [TZ]
EXTRA="$1"; TZV="${2:-UTC}"
docker rm -f fleet-spike-antidetect >/dev/null 2>&1
docker create --name fleet-spike-antidetect -p 127.0.0.1:3303:3000 --memory 2g --cpus 1.5 -e TZ="$TZV" --entrypoint sh ghcr.io/steel-dev/steel-browser-api:latest -c "Xvfb :10 -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1 & sleep 1; DISPLAY=:10 chromium --no-sandbox --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir=/tmp/vanilla --no-first-run --no-default-browser-check --password-store=basic --window-size=1920,1080 $EXTRA about:blank >/tmp/chrome.log 2>&1 & exec node /tmp/fwd.js" >/dev/null
docker cp "$(dirname "$0")/fwd.js" fleet-spike-antidetect:/tmp/fwd.js
docker start fleet-spike-antidetect >/dev/null
sleep 4
curl -s http://127.0.0.1:3303/json/version | grep -o '"Browser": "[^"]*"'
