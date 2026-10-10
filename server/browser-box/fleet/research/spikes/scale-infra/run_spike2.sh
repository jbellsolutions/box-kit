#!/usr/bin/env bash
# Follow-up to run_spike.sh:
#  1. restore the slim profile tarball into a new container WITHOUT Chromium's Singleton* lock files
#  2. fingerprint stability across real relaunches (new container, persist relaunch, container restart)
# Usage: run_spike2.sh <workdir-of-run1> <workdir>
set -uo pipefail
R1="${1:?run1 dir}"; W="${2:?workdir}"; mkdir -p "$W"; cd "$W"
HERE="$(cd "$(dirname "$0")" && pwd)"
IMG="ghcr.io/steel-dev/steel-browser-api:latest"
export PW_CORE="${PW_CORE:?}"
UDD=/app/api/user-data-dir
log(){ echo "[$(date -u +%H:%M:%S)] $*" | tee -a spike2.log; }
mem(){ docker stats --no-stream --format '{{.MemUsage}}' "$1"; }
probe(){ node "$HERE/probe.mjs" "$1" "$2" 2>&1 | tail -1; }
fpshort(){ python3 -c 'import json,sys;d=json.loads(sys.argv[1]);f=d.get("fp",{});print(f.get("ua","?")[-40:],f.get("platform"),"hc=",f.get("hc"),"dm=",f.get("dm"),"screen=",f.get("screen"),"gl=",(f.get("gl") or ["",""])[1][:40])' "$1" 2>/dev/null || echo "$1"; }
create(){ curl -sS -o /dev/null -w '%{http_code} %{time_total}s' -X POST -H 'content-type: application/json' "http://127.0.0.1:$1/v1/sessions" -d "$2"; }
health(){ for i in $(seq 1 120); do curl -fsS "http://127.0.0.1:$1/v1/health" >/dev/null 2>&1 && return 0; sleep 0.5; done; return 1; }
cleanup(){ docker rm -f fleet-spike-scale-d fleet-spike-scale-e >/dev/null 2>&1; }
trap cleanup EXIT
cleanup; rm -rf profD; mkdir -p profD

zstd -q -d -c "$R1/profA-slim.tar.zst" | tar -C profD -xf -
rm -f profD/SingletonLock profD/SingletonSocket profD/SingletonCookie
log "restored slim profile without Singleton* files: $(du -sk profD | cut -f1) KB"

docker run -d --name fleet-spike-scale-d --memory 1536m --cpus 1.2 -p 127.0.0.1:3311:3000 \
  -e DOMAIN=localhost:3311 -e CDP_DOMAIN=localhost:3311 -e NODE_OPTIONS=--unhandled-rejections=warn \
  -v "$W/profD:$UDD" "$IMG" >/dev/null; health 3311
log "D create persist: $(create 3311 '{"persist":true}')"
log "D getstate (restore w/o lock files): $(probe 3311 getstate)"
FP_D1=$(probe 3311 fp); log "D fp (persist launch #1): $(fpshort "$FP_D1")"
curl -sS -o /dev/null -X POST http://127.0.0.1:3311/v1/sessions/release -H 'content-type: application/json' -d '{}'; sleep 2

docker restart fleet-spike-scale-d >/dev/null; health 3311
log "D after container restart, create persist: $(create 3311 '{"persist":true}')"
log "D getstate after restart: $(probe 3311 getstate)"
FP_D2=$(probe 3311 fp); log "D fp (after container restart): $(fpshort "$FP_D2")"

docker run -d --name fleet-spike-scale-e --memory 1536m --cpus 1.2 -p 127.0.0.1:3312:3000 \
  -e DOMAIN=localhost:3312 -e CDP_DOMAIN=localhost:3312 -e NODE_OPTIONS=--unhandled-rejections=warn "$IMG" >/dev/null; health 3312
log "E create {}: $(create 3312 '{}')"; FP_E1=$(probe 3312 fp); log "E fp #1: $(fpshort "$FP_E1")"
log "E create persist (forces relaunch): $(create 3312 '{"persist":true}')"; FP_E2=$(probe 3312 fp); log "E fp #2: $(fpshort "$FP_E2")"
log "E create with pinned userAgent+dimensions+timezone: $(create 3312 '{"persist":true,"userAgent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36","dimensions":{"width":1366,"height":768},"timezone":"America/Chicago"}')"
FP_E3=$(probe 3312 fp); log "E fp #3 (pinned UA): $(fpshort "$FP_E3")"
log "raw: D1=$FP_D1"; log "raw: D2=$FP_D2"; log "raw: E1=$FP_E1"; log "raw: E2=$FP_E2"; log "raw: E3=$FP_E3"
log "done"
