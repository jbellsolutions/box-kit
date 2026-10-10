#!/bin/sh
# (Re)create a capped spike container that runs the CloakBrowser free binary (v146, arm64) headful under Xvfb,
# with a fixed fingerprint seed and a persistent user-data-dir, CDP on 127.0.0.1:3303. Public test pages only.
# Usage: cloak_up.sh <seed> [extra chrome args...]
SEED="$1"; shift
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! docker ps -a --format '{{.Names}}' | grep -q '^fleet-spike-antidetect$'; then
  docker create --name fleet-spike-antidetect -p 127.0.0.1:3303:3000 --memory 2g --cpus 1.5 --shm-size 1g --entrypoint sh ghcr.io/steel-dev/steel-browser-api:latest -c 'sleep infinity' >/dev/null
  docker cp "$HERE/fwd.js" fleet-spike-antidetect:/tmp/fwd.js
  docker cp "$HERE/dl-cloak/cloakbrowser-linux-arm64.tar.gz" fleet-spike-antidetect:/tmp/cb.tgz
  docker start fleet-spike-antidetect >/dev/null
  docker exec fleet-spike-antidetect sh -c 'mkdir -p /opt/cb && tar xzf /tmp/cb.tgz -C /opt/cb && rm /tmp/cb.tgz'
  docker exec -d fleet-spike-antidetect sh -c 'Xvfb :10 -screen 0 1920x1080x24 -nolisten tcp >/dev/null 2>&1'
  docker exec -d fleet-spike-antidetect node /tmp/fwd.js
fi
docker exec fleet-spike-antidetect sh -c 'pkill -f /opt/cb/chrome; sleep 2; true'
docker exec -d fleet-spike-antidetect sh -c "DISPLAY=:10 /opt/cb/chrome --no-sandbox --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir=/tmp/cbprofile --no-first-run --no-default-browser-check --password-store=basic --window-size=1920,1080 --fingerprint=$SEED --fingerprint-platform=windows $* about:blank >/tmp/cb.log 2>&1"
sleep 5
curl -s http://127.0.0.1:3303/json/version | grep -E '"(Browser|User-Agent)"'
