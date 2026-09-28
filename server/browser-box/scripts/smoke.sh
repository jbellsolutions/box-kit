#!/usr/bin/env bash
# M3 gate: one real page, read end to end through the MCP endpoint.
set -euo pipefail
cd "$(dirname "$0")/.."

TOKEN="${BB_TOKEN:-$(grep -E '^BB_TOKEN=' .env | cut -d= -f2-)}"
BASE="${BB_BASE:-http://127.0.0.1:8080}"
URL="${1:-https://example.com}"

if [ -z "$TOKEN" ]; then echo "BB_TOKEN is empty" >&2; exit 1; fi

call() {
  curl -fsS -X POST "$BASE/mcp" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d "$1"
}

echo "── tools/list ─────────────────────────────"
call '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 -c 'import json,sys; d=json.load(sys.stdin); print("\n".join(t["name"] for t in d["result"]["tools"]))'

echo
echo "── status ─────────────────────────────────"
call '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"status","arguments":{}}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["content"][0]["text"][:1200])'

echo
echo "── read $URL ──────────────────────────────"
start=$(date +%s)
call "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"read\",\"arguments\":{\"url\":\"$URL\",\"screenshot\":true}}}" \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
blocks=d["result"]["content"]
body=json.loads(blocks[0]["text"])
if "error" in body:
    print("FAILED:", body["error"]); sys.exit(1)
print("chars:", len(body.get("text") or ""))
images=[b for b in blocks if b.get("type")=="image"]
assert images, "asked for a screenshot and got no image block"
assert "screenshot_base64" not in body, "base64 leaked into the text block"
print("screenshot: image block,", body["screenshot_bytes"], "bytes", images[0]["mimeType"])
print((body.get("text") or "")[:400])
'
echo "wall: $(( $(date +%s) - start ))s"

echo
echo "── loopback must be refused ───────────────"
call '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"read","arguments":{"url":"http://0x7f000001/"}}}' \
  | python3 -c '
import json,sys
b=json.loads(json.load(sys.stdin)["result"]["content"][0]["text"])
assert "error" in b, "SSRF guard did not refuse obfuscated loopback"
print("refused:", b["error"])
'
echo
echo "── a public redirect into our own loopback must be refused ──"
REDIRECT='https://httpbin.org/redirect-to?url=http%3A%2F%2F127.0.0.1%3A3000%2Fv1%2Fsessions'
call "{\"jsonrpc\":\"2.0\",\"id\":5,\"method\":\"tools/call\",\"params\":{\"name\":\"read\",\"arguments\":{\"url\":\"$REDIRECT\"}}}" \
  | python3 -c '
import json,sys
b=json.loads(json.load(sys.stdin)["result"]["content"][0]["text"])
blob=json.dumps(b)
assert "sessionViewerUrl" not in blob and "debuggerUrl" not in blob, "SSRF: the browser read Steel'"'"'s own API"
if "error" in b and "redirected" in b["error"]:
    print("refused at the redirect hop")
else:
    print("WARNING: the redirector did not redirect (httpbin down?) — this check proved nothing")
'

echo
echo "── the in-browser guard: Steel's own screenshot, aimed straight at the redirect ──"
# read pre-flights its URL, but a screenshot is a second navigation inside Chromium that only the
# guard sees. Steel is on loopback here, so ask it directly, bypassing the gateway's pre-flight.
STEEL="${BB_STEEL_BASE:-http://127.0.0.1:3000}"
code=$(curl -sS -o /tmp/bb-smoke-shot -w '%{http_code}' -X POST "$STEEL/v1/screenshot" -H 'Content-Type: application/json' -d "{\"url\":\"$REDIRECT\"}")
if [ "$code" = "200" ]; then echo "FAILED: Steel photographed a redirect into its own API: the guard is not attached" >&2; exit 1; fi
grep -q ERR_BLOCKED_BY_CLIENT /tmp/bb-smoke-shot && echo "refused inside the browser (HTTP $code)" || { echo "FAILED: HTTP $code, but not the guard's refusal:" >&2; head -c 300 /tmp/bb-smoke-shot >&2; exit 1; }
rm -f /tmp/bb-smoke-shot

echo
echo "── the in-browser guard: a new tab created with the redirect already in flight ──"
PY=$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
BB_STEEL_CDP="${BB_STEEL_CDP:-ws://127.0.0.1:3000/}" "$PY" scripts/guard_probe.py

echo
echo "── act, when agent-jev is configured ──────"
if call '{"jsonrpc":"2.0","id":6,"method":"tools/list"}' | python3 -c 'import json,sys; sys.exit(0 if "act" in [t["name"] for t in json.load(sys.stdin)["result"]["tools"]] else 1)'; then
  act() {
    call "{\"jsonrpc\":\"2.0\",\"id\":7,\"method\":\"tools/call\",\"params\":{\"name\":\"act\",\"arguments\":$1}}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["content"][0]["text"])'
  }
  act "{\"command\":\"open $REDIRECT\"}" | python3 -c '
import json,sys
b=json.loads(sys.stdin.read())
assert "127.0.0.1" not in (b.get("url") or ""), "act: the browser landed on loopback"
assert b.get("refused"), "act: a redirect into loopback was not refused: " + json.dumps(b)[:300]
print("refused inside the browser:", b["steps"][-1]["did"][:90])
'
  act '{"command":"open https://example.com"}' | python3 -c '
import json,sys
b=json.loads(sys.stdin.read())
assert b["status"] == "done" and "example.com" in (b["url"] or ""), json.dumps(b)[:300]
print("opened:", b["url"], "|", b["steps"][-1]["did"])
'
else
  echo "act is not offered on this box (no jev in COMPOSE_PROFILES): skipped"
fi

echo
echo "── task on the browser, when agent-browseruse is configured ──"
if call '{"jsonrpc":"2.0","id":8,"method":"tools/list"}' | python3 -c 'import json,sys; t=[t for t in json.load(sys.stdin)["result"]["tools"] if t["name"]=="task"]; sys.exit(0 if t and "browser" in t[0]["inputSchema"]["properties"]["surface"]["enum"] else 1)'; then
  tool() {
    call "{\"jsonrpc\":\"2.0\",\"id\":9,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["content"][0]["text"])'
  }
  has_act=$(call '{"jsonrpc":"2.0","id":10,"method":"tools/list"}' | python3 -c 'import json,sys; print("yes" if "act" in [t["name"] for t in json.load(sys.stdin)["result"]["tools"]] else "no")')
  [ "$has_act" = yes ] && tool act '{"command":"open https://example.com"}' >/dev/null
  tool task '{"surface":"browser","goal":"Open https://example.com and report the page main heading, exactly.","max_steps":4,"timeout_seconds":150}' | python3 -c '
import json,sys
b=json.loads(sys.stdin.read())
assert b.get("status") == "done" and "Example Domain" in (b.get("answer") or ""), json.dumps(b)[:400]
print("done in", b["steps_taken"], "steps,", b["seconds"], "s, ~$", b["estimated_cost_usd"], "|", repr(b["answer"][:70]))
'
  if [ "$has_act" = yes ]; then
    # Browser-Use once took over the first tab it found, which was act's. It must not touch it.
    tool act '{"command":"scroll down"}' | python3 -c '
import json,sys
b=json.loads(sys.stdin.read())
assert "example.com" in (b.get("url") or ""), "task moved act'"'"'s tab: " + json.dumps(b)[:300]
print("act'"'"'s tab untouched by the task:", b["url"])
'
  fi
  tool task "{\"surface\":\"browser\",\"goal\":\"Open $REDIRECT and report exactly what the page says.\",\"max_steps\":3,\"timeout_seconds\":90}" | python3 -c '
import json,sys
b=json.loads(sys.stdin.read())
blob=json.dumps(b)
assert "websocketUrl" not in blob and "\"sessions\"" not in blob and "createdAt" not in blob, "SSRF: the task read Steel'"'"'s own API: " + blob[:300]
print("the task could not reach Steel'"'"'s API:", (b.get("answer") or b.get("status") or "")[:90].replace("\n", " "))
'
else
  echo "task on the browser is not offered on this box (no browseruse in COMPOSE_PROFILES): skipped"
fi

echo
echo "── a real MCP client (initialize, session headers, SSE) ──"
"$PY" scripts/mcp_check.py

echo "smoke OK"
