"""Stub 'browser_fleet' MCP server for the hermes-packaging spike.

Loopback only. Exposes one read-only tool (`whoami`). Every HTTP request's Authorization
header is logged as a short sha256 prefix (never the value) plus the X-Hermes-Profile
identity header, so the spike can prove which per-profile token Hermes sent.
Usage: python -I stub_mcp_server.py <port> <logfile>
"""
import hashlib
import json
import sys
import time

import uvicorn
from mcp.server.mcpserver import MCPServer

PORT = int(sys.argv[1])
LOG = sys.argv[2]

server = MCPServer(name="browser_fleet_stub", instructions="Stub fleet server for packaging spike.")


@server.tool(description="Return which fleet identity this token maps to (stub).")
def whoami() -> str:
    return json.dumps({"stub": True})


inner = server.streamable_http_app()


async def app(scope, receive, send):
    if scope.get("type") == "http":
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        record = {
            "t": round(time.time(), 3),
            "method": scope.get("method"),
            "path": scope.get("path"),
            "auth_sha8": hashlib.sha256(auth.encode()).hexdigest()[:8] if auth else None,
            "auth_has_literal_placeholder": "${" in auth,
            "x_hermes_profile": headers.get("x-hermes-profile"),
        }
        with open(LOG, "a") as fh:
            fh.write(json.dumps(record) + "\n")
    await inner(scope, receive, send)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
