"""The one door: MCP over streamable HTTP at /mcp and the same tools as HTTP/JSON under /api/v1,
both behind one bearer token. data-box refuses to start without it.

One dispatch (run_tool) serves every door: arguments are checked against the tool's schema, and
a refusal or an outage comes back as {"error": ...} the caller can read and act on, never as a
stack trace.
"""
from __future__ import annotations

import hmac
import json
import logging
import sys
from contextlib import asynccontextmanager

import httpx
import jsonschema
import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from . import VERSION, config, planning, rest
from .jobs import Runner
from .ledger import Conflict, Ledger
from .providers.firecrawl import FirecrawlError
from .security import UnsafeUrl
from .tools import HANDLERS, Box, card, offered_tools

# A refusal, or a target that would not answer: things the caller can act on. They come back as
# {"error": ...} answers without a stack trace in the log.
EXPECTED = (UnsafeUrl, ValueError, Conflict, ConnectionError, httpx.HTTPError, FirecrawlError)

log = logging.getLogger("data-box")


def _check(name: str, args: dict) -> None:
    try:
        jsonschema.validate(args, card(name).input_schema)
    except jsonschema.ValidationError as exc:
        where = ".".join(str(p) for p in exc.absolute_path)
        raise ValueError(f"{name}: {where + ': ' if where else ''}{exc.message}") from None


def make_dispatch(box: Box):
    async def run_tool(name: str, arguments: dict) -> dict:
        try:
            _check(name, arguments or {})
            return await HANDLERS[name](arguments or {}, box)
        except EXPECTED as exc:
            return {"error": str(exc), "tool": name}
        except Exception as exc:
            log.exception("tool %s failed", name)
            return {"error": f"{type(exc).__name__}: {exc}"[:400], "tool": name, "unexpected": True}
    return run_tool


def _token_matches(header: str) -> bool:
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    expected = config.token()
    return bool(expected) and hmac.compare_digest(presented.encode(), expected.encode())


class NormalizeMcpPath:
    """Serve /mcp and /mcp/ identically: a 307 on a streaming POST is a coin flip across MCP clients."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = {**scope, "path": "/mcp/", "raw_path": b"/mcp/"}
        await self.app(scope, receive, send)


def build_app(state_dir=None) -> Starlette:
    if not config.token():
        log.error("DATABOX_TOKEN is not set; refusing to start an unauthenticated data endpoint")
        raise SystemExit(2)
    ledger = Ledger((state_dir or config.state_dir()) / "data-box.sqlite")
    runner = Runner(ledger, expected=EXPECTED)
    box = Box(ledger, runner)
    run_tool = make_dispatch(box)

    mcp = Server("data-box", version=VERSION)

    @mcp.list_tools()
    async def list_tools() -> list[Tool]:
        return [Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"]) for t in offered_tools()]

    @mcp.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name not in HANDLERS:
            raise ValueError(f"unknown tool {name}")
        if name not in {t["name"] for t in offered_tools()}:
            result = {"error": f"{name} is not offered on this box: status says what is missing", "tool": name}
        else:
            result = await run_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]

    manager = StreamableHTTPSessionManager(mcp, stateless=True, json_response=True)

    async def mcp_endpoint(scope, receive, send):
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        if not _token_matches(headers.get("authorization", "")):
            await Response("unauthorized", status_code=401)(scope, receive, send)
            return
        await manager.handle_request(scope, receive, send)

    def authorized(request) -> bool:
        return _token_matches(request.headers.get("authorization", ""))

    async def health(_request):
        """Unauthenticated liveness and the deployed revision only, never capability detail."""
        return JSONResponse({"ok": True, "service": "data-box", "version": VERSION, "revision": config.revision()})

    @asynccontextmanager
    async def lifespan(_app):
        interrupted = ledger.recover()
        if interrupted:
            log.warning("marked %d job(s) interrupted: they were running when data-box last stopped", interrupted)
        purged = planning.purge_old()
        if purged:
            log.info("deleted %d plan folder(s) past the %g-day retention period", purged, config.retention_days())
        async with manager.run():
            try:
                yield
            finally:
                await runner.shutdown()

    app = Starlette(
        routes=[Route("/health", health), *rest.routes(authorized, run_tool), Mount("/mcp", app=mcp_endpoint)],
        middleware=[Middleware(NormalizeMcpPath)],
        lifespan=lifespan,
    )
    app.state.box = box
    app.state.run_tool = run_tool
    return app


def main() -> None:
    logging.basicConfig(level=config.env("DATABOX_LOG_LEVEL", "INFO"), stream=sys.stderr)
    uvicorn.run(build_app(), host=config.host(), port=config.port(), access_log=False)


if __name__ == "__main__":
    main()
