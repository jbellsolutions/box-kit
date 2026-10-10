#!/bin/sh
# Recreate the spike container on the same volume(s). Extra docker args are passed through.
# Usage: recreate.sh [extra docker run args...]
docker rm -f fleet-spike-steel >/dev/null 2>&1
docker run -d --name fleet-spike-steel -p 127.0.0.1:3300:3000 --memory 1536m --cpus 1.2 \
  -e NODE_OPTIONS=--unhandled-rejections=warn -e DOMAIN=localhost:3300 -e CDP_DOMAIN=localhost:3300 \
  "$@" ghcr.io/steel-dev/steel-browser-api:latest >/dev/null
for i in $(seq 1 40); do curl -sf -m 2 http://127.0.0.1:3300/v1/health >/dev/null && break; sleep 1; done
echo "recreated; health=$(curl -s -m 3 http://127.0.0.1:3300/v1/health) hostname=$(docker exec fleet-spike-steel hostname)"
