#!/usr/bin/env bash
# Scale-infra spike: self-hosted Steel (steel-browser-api image) as a per-profile unit.
# Measures cold start, idle/active memory, profile-at-rest size, cross-container restore,
# which session-create fields the OSS server honors, fingerprint stability across launches,
# headful launch, and 3-container density. Public test pages only. No secrets used.
#
# Usage: run_spike.sh <workdir>     (workdir = scratch dir for profiles, tarballs and raw logs)
# Every container is named fleet-spike-scale-*, capped, loopback-only, and removed at the end.
set -uo pipefail
W="${1:?workdir}"; mkdir -p "$W"; cd "$W"
HERE="$(cd "$(dirname "$0")" && pwd)"
IMG="ghcr.io/steel-dev/steel-browser-api:latest"
export PW_CORE="${PW_CORE:?set PW_CORE to the absolute path of playwright-core}"
MEM=1536m; CPUS=1.2
PA=3311; PB=3312; PC=3313
UDD=/app/api/user-data-dir           # the fixed path persist:true resolves to inside the image
log(){ echo "[$(date -u +%H:%M:%S)] $*" | tee -a spike.log; }
now(){ python3 -c 'import time;print(time.time())'; }
mem(){ docker stats --no-stream --format '{{.MemUsage}} cpu={{.CPUPerc}}' "$1"; }
api(){ # api <port> <method> <path> [json]
  local out; out=$(curl -sS -o /tmp/fleetspike_body.$$ -w '%{http_code} %{time_total}' -X "$2" \
    -H 'content-type: application/json' "http://127.0.0.1:$1/v1$3" ${4:+-d "$4"});
  echo "$out $(head -c 300 /tmp/fleetspike_body.$$ | tr '\n' ' ')"; }
probe(){ node "$HERE/probe.mjs" "$1" "$2" 2>&1 | tail -1; }
cleanup(){ docker rm -f fleet-spike-scale-a fleet-spike-scale-b fleet-spike-scale-c >/dev/null 2>&1; rm -f /tmp/fleetspike_body.$$; }
trap cleanup EXIT

start(){ # start <name> <port> [hostdir-for-user-data-dir]
  local t0 t1; t0=$(now)
  docker run -d --name "$1" --memory $MEM --cpus $CPUS -p 127.0.0.1:$2:3000 \
    -e DOMAIN=localhost:$2 -e CDP_DOMAIN=localhost:$2 -e NODE_OPTIONS=--unhandled-rejections=warn \
    ${3:+-v "$3:$UDD"} "$IMG" >/dev/null || return 1
  for i in $(seq 1 120); do curl -fsS "http://127.0.0.1:$2/v1/health" >/dev/null 2>&1 && break; sleep 0.5; done
  t1=$(now); log "$1 healthy after $(python3 -c "print(round($t1-$t0,1))") s; idle mem: $(mem "$1")"
}

cleanup; rm -rf profA profB; mkdir -p profA profB
log "image: $(docker image inspect $IMG --format '{{.Id}} {{.Created}}')"
log "host: $(docker info --format 'cpus={{.NCPU}} mem={{.MemTotal}} arch={{.Architecture}} {{.OperatingSystem}}')"

### Phase 1: container A with a host dir mounted at the fixed user-data-dir path
start fleet-spike-scale-a $PA "$W/profA"

log "--- fingerprint stability: two plain launches in the same container"
log "create#1: $(api $PA POST /sessions '{}')"; log "fp#1: $(probe $PA fp)"
log "create#2: $(api $PA POST /sessions '{}')"; log "fp#2: $(probe $PA fp)"
log "mem after 2 launches + 1 page: $(mem fleet-spike-scale-a)"

log "--- browser-box's Cloud-style fields (persistProfile/profileId) against OSS"
log "create: $(api $PA POST /sessions '{"persistProfile":true,"profileId":"fleet-spike"}')"
log "set: $(probe $PA setstate)"; log "release: $(api $PA POST /sessions/release '{}' | cut -c1-80)"; sleep 2
log "mounted dir after persistProfile session: $(du -sk profA | cut -f1) KB, entries=$(ls -A profA | wc -l | tr -d ' ')"
log "/tmp/steel-chrome in container: $(docker exec fleet-spike-scale-a sh -c 'du -sk /tmp/steel-chrome 2>/dev/null || echo none')"

log "--- userDataDir:/tmp/custom-udd (expect: ignored, fixed path used instead)"
log "create: $(api $PA POST /sessions '{"userDataDir":"/tmp/custom-udd"}')"; sleep 1
log "/tmp/custom-udd exists? $(docker exec fleet-spike-scale-a sh -c 'test -d /tmp/custom-udd && echo yes || echo no'); mounted dir entries=$(ls -A profA | wc -l | tr -d ' ')"
log "release: $(api $PA POST /sessions/release '{}' | cut -c1-80)"; sleep 2
rm -rf profA/* profA/.[!.]* 2>/dev/null

log "--- persist:true, set state, browse with memory sampling, export context, release"
SID=$(curl -sS -X POST -H 'content-type: application/json' http://127.0.0.1:$PA/v1/sessions -d '{"persist":true}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
log "session $SID; mem: $(mem fleet-spike-scale-a)"
log "set: $(probe $PA setstate)"
( while :; do docker stats --no-stream --format '{{.Name}},{{.MemUsage}},{{.CPUPerc}}' fleet-spike-scale-a >> statsA.csv; done ) & SAMP=$!
log "browse: $(probe $PA browse)"
kill $SAMP 2>/dev/null; wait $SAMP 2>/dev/null
log "mem after browse: $(mem fleet-spike-scale-a)"
curl -sS http://127.0.0.1:$PA/v1/sessions/$SID/context -o contextA.json; log "context export: $(wc -c < contextA.json) bytes; cookies=$(python3 -c 'import json;d=json.load(open("contextA.json"));print(len(d.get("cookies",[])))')"
log "release: $(api $PA POST /sessions/release '{}' | cut -c1-80)"; sleep 3
log "profile dir on host: $(du -sk profA | cut -f1) KB, files=$(find profA -type f | wc -l | tr -d ' ')"
T0=$(now); tar -C profA -cf - . | zstd -q -3 -o profA.tar.zst -f; T1=$(now)
log "tar+zstd -3: $(wc -c < profA.tar.zst) bytes in $(python3 -c "print(round($T1-$T0,2))") s"
T0=$(now); tar -C profA --exclude='*/Cache' --exclude='*/Code Cache' --exclude='*/GPUCache' --exclude='*/Service Worker/CacheStorage' --exclude='*/DawnGraphiteCache' --exclude='*/DawnWebGPUCache' --exclude='GrShaderCache' --exclude='ShaderCache' -cf - . | zstd -q -3 -o profA-slim.tar.zst -f; T1=$(now)
log "slim (caches excluded) tar+zstd -3: $(wc -c < profA-slim.tar.zst) bytes in $(python3 -c "print(round($T1-$T0,2))") s"
( cd profA && du -sk * .[!.]* 2>/dev/null | sort -rn | head -8 ) > profA-top.txt; ( cd profA/Default 2>/dev/null && du -sk * 2>/dev/null | sort -rn | head -12 ) >> profA-top.txt

log "--- headful launch (headless:false)"
log "create: $(api $PA POST /sessions '{"headless":false}')"
sleep 2; log "mem headful: $(mem fleet-spike-scale-a)"
log "release: $(api $PA POST /sessions/release '{}' | cut -c1-80)"

### Phase 2: container B restored from the slim tarball (different container, empty start)
zstd -q -d -c profA-slim.tar.zst | tar -C profB -xf -
start fleet-spike-scale-b $PB "$W/profB"
log "create B persist: $(api $PB POST /sessions '{"persist":true}' | cut -c1-60)"
log "restore-from-tarball getstate B: $(probe $PB getstate)"

### Phase 2b: container C, no mount, state injected as sessionContext from A's export
start fleet-spike-scale-c $PC
python3 -c 'import json;d=json.load(open("contextA.json"));print(json.dumps({"sessionContext":d}))' > ctxbody.json
log "create C with sessionContext: $(curl -sS -o /dev/null -w '%{http_code}' -X POST -H 'content-type: application/json' http://127.0.0.1:$PC/v1/sessions -d @ctxbody.json)"
log "restore-from-context getstate C: $(probe $PC getstate)"

### Phase 3: density, three containers browsing at once
log "--- density: 3 containers idle with one session each"
api $PA POST /sessions '{"persist":true}' >/dev/null
log "idle: A=$(mem fleet-spike-scale-a) | B=$(mem fleet-spike-scale-b) | C=$(mem fleet-spike-scale-c)"
( while :; do docker stats --no-stream --format '{{.Name}},{{.MemUsage}},{{.CPUPerc}}' fleet-spike-scale-a fleet-spike-scale-b fleet-spike-scale-c >> stats3.csv; done ) & SAMP=$!
T0=$(now)
probe $PA browse > bA.json & P1=$!; probe $PB browse > bB.json & P2=$!; probe $PC browse > bC.json & P3=$!
wait $P1 $P2 $P3; T1=$(now)
kill $SAMP 2>/dev/null; wait $SAMP 2>/dev/null
log "3 concurrent browse runs wall: $(python3 -c "print(round($T1-$T0,1))") s"
for f in bA bB bC; do log "$f: $(python3 -c "import json;d=json.load(open('$f.json'));print(d['ms'],'ms', sum(1 for p in d['pages'] if 'err' in p),'errors')")"; done
log "after: A=$(mem fleet-spike-scale-a) | B=$(mem fleet-spike-scale-b) | C=$(mem fleet-spike-scale-c)"
log "done; cleanup runs on exit"
