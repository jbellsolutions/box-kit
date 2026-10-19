#!/usr/bin/env bash
# Deploy gate: every offered tool end to end through the MCP endpoint, on hosted browsers.
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
assert "error" in b, "the URL check did not refuse obfuscated loopback"
print("refused:", b["error"])
'
echo
echo "── a public redirect into loopback must not be read ──"
REDIRECT='https://httpbin.org/redirect-to?url=http%3A%2F%2F127.0.0.1%3A8080%2Fstatus'
call "{\"jsonrpc\":\"2.0\",\"id\":5,\"method\":\"tools/call\",\"params\":{\"name\":\"read\",\"arguments\":{\"url\":\"$REDIRECT\"}}}" \
  | python3 -c '
import json,sys
b=json.loads(json.load(sys.stdin)["result"]["content"][0]["text"])
assert "tools_working_now" not in json.dumps(b), "a read returned this box'"'"'s own status"
print("refused:", (b.get("error") or "page dropped")[:100])
'

tool() {
  call "{\"jsonrpc\":\"2.0\",\"id\":9,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["content"][0]["text"])'
}
offered() {
  call '{"jsonrpc":"2.0","id":6,"method":"tools/list"}' | python3 -c "import json,sys; sys.exit(0 if '$1' in [t['name'] for t in json.load(sys.stdin)['result']['tools']] else 1)"
}
PY=$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

echo
echo "── act, when offered ──────────────────────"
if offered act; then
  tool act '{"command":"open https://example.com"}' | python3 -c '
import json,sys
b=json.loads(sys.stdin.read())
assert b["status"] == "done" and "example.com" in (b["url"] or ""), json.dumps(b)[:300]
print("opened:", b["url"], "|", b["steps"][-1]["did"])
'
  tool act "{\"command\":\"open $REDIRECT\"}" | python3 -c '
import json,sys
b=json.loads(sys.stdin.read())
assert "127.0.0.1" not in (b.get("url") or "") and b.get("status") != "done", "act landed on loopback: " + json.dumps(b)[:300]
print("refused:", (b.get("error") or b["steps"][-1]["did"])[:90])
'
  tool session '{"action":"release"}' >/dev/null
else
  echo "act is not offered on this box (needs BROWSER_USE_API_KEY and TYPESAFE_API_KEY): skipped"
fi

echo
echo "── task on the browser, when offered ──────"
if call '{"jsonrpc":"2.0","id":8,"method":"tools/list"}' | python3 -c 'import json,sys; t=[t for t in json.load(sys.stdin)["result"]["tools"] if t["name"]=="task"]; sys.exit(0 if t and "browser" in t[0]["inputSchema"]["properties"]["surface"]["enum"] else 1)'; then
  tool task '{"surface":"browser","goal":"Open https://example.com and report the page main heading, exactly.","max_steps":4,"timeout_seconds":150}' | python3 -c '
import json,sys
b=json.loads(sys.stdin.read())
assert b.get("status") == "done" and "Example Domain" in (b.get("answer") or ""), json.dumps(b)[:400]
print("done in", b["steps_taken"], "steps,", b["seconds"], "s, ~$", b["estimated_cost_usd"], "|", repr(b["answer"][:70]))
'
else
  echo "task on the browser is not offered on this box: skipped"
fi

echo
echo "── a real MCP client (initialize, session headers, SSE) ──"
"$PY" scripts/mcp_check.py

echo "smoke OK"
