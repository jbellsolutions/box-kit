"""The one door: an MCP server over streamable HTTP, bearer-gated (plus the same tools as
HTTP/JSON under /api/v1, see rest.py).

No embedded LLM. The agent calling this is the brain; the box executes. That is the
whole design correction over the system this replaces, which tried to put a model
inside the tool and spent a year failing to connect it to its own hands.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import sys
from contextlib import asynccontextmanager

import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import ImageContent, TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from . import browseruse, rest, tools
from .browserbase import BrowserbaseUnavailable
from .cloud import CloudUnavailable
from .decide import DecisionUnavailable
from .browseruse import BrowserUseUnavailable
from .lock import LaneBusy
from .orgo import OrgoUnavailable
from .security import UnsafeUrl
from .tools import HANDLERS, offered_tools, status

# A refusal or an outage the caller can act on. These come back as {"error": ...} answers.
EXPECTED = (UnsafeUrl, LaneBusy, CloudUnavailable, BrowserbaseUnavailable, ValueError, OrgoUnavailable, BrowserUseUnavailable, DecisionUnavailable)

log = logging.getLogger("browser-box")
TOKEN = os.getenv("BB_TOKEN", "")
PORT = int(os.getenv("BB_PORT", "8080"))

server: Server = Server("browser-box")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"]) for t in offered_tools()]


def render(result: dict) -> list[TextContent | ImageContent]:
    """JSON for the facts; a real image block for any screenshot.

    A base64 string inside JSON is text to the caller — it cannot see it. An ImageContent
    block is what lets a vision-capable caller actually look at the page or the desktop,
    which is the whole premise of caller-driven computer use.
    """
    image = result.pop("screenshot_base64", None) if isinstance(result, dict) else None
    blocks: list[TextContent | ImageContent] = [
        TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))
    ]
    if image:
        blocks.append(ImageContent(type="image", data=image, mimeType=result.get("screenshot_media_type") or "image/jpeg"))
    return blocks


async def run_tool(name: str, arguments: dict) -> dict:
    """The one dispatch both doors use (MCP here, HTTP/JSON in rest.py)."""
    try:
        return await HANDLERS[name](arguments or {})
    except EXPECTED as exc:
        # Refusals are answers, not crashes: the model must see the reason and adapt.
        return {"error": str(exc), "tool": name}
    except Exception as exc:
        # Same reasoning one level out. A stack trace in a transport error tells the
        # calling agent nothing it can act on; a named failure lets it pick another route.
        log.exception("tool %s failed", name)
        return {"error": f"{type(exc).__name__}: {exc}"[:400], "tool": name, "unexpected": True}


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    if name not in HANDLERS:
        raise ValueError(f"unknown tool {name}")
    if name not in {t["name"] for t in offered_tools()}:
        return render({"error": f"{name} is not offered on this box — status says what is missing", "tool": name})
    return render(await run_tool(name, arguments))


class NormalizeMcpPath:
    """Serve /mcp and /mcp/ identically.

    Starlette's Mount 307-redirects the bare path to the trailing-slash one. Clients are
    configured with .../mcp by convention, and a redirect on a streaming POST is a
    coin-flip across MCP client implementations. Rewrite instead of redirect.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = {**scope, "path": "/mcp/", "raw_path": b"/mcp/"}
        await self.app(scope, receive, send)


def authorized(request) -> bool:
    return _token_matches(request.headers.get("authorization", ""))


def _token_matches(header: str) -> bool:
    presented = header[7:] if header.lower().startswith("bearer ") else ""
    return bool(TOKEN) and hmac.compare_digest(presented, TOKEN)


async def health(_request):
    """Unauthenticated liveness only — never capability detail."""
    return JSONResponse({"ok": True, "service": "browser-box"})


async def status_route(request):
    if not authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(await status({}))


def build_app() -> Starlette:
    if not TOKEN:
        log.error("BB_TOKEN is not set; refusing to start an unauthenticated browser endpoint")
        raise SystemExit(2)

    # One manager per app: its run() is single-use, so a module-level singleton
    # cannot be started twice (which is also what makes this testable).
    manager = StreamableHTTPSessionManager(server, stateless=True, json_response=True, max_request_body_size=1_000_000)

    async def mcp_endpoint(scope, receive, send):
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        if not _token_matches(headers.get("authorization", "")):
            await Response("unauthorized", status_code=401)(scope, receive, send)
            return
        await manager.handle_request(scope, receive, send)

    @asynccontextmanager
    async def lifespan(_app):
        async with manager.run():
            if browseruse.configured():
                # A browser task still running now belongs to a gateway that died: its caller is gone,
                # so stop it rather than let it spend on nobody's behalf.
                orphan = await browseruse.cancel()
                if orphan and orphan.get("cancelled"):
                    log.warning("stopped a browser task left running by a previous gateway")
            cloud = tools.cloud_client()
            if cloud is not None:
                # Hosted browsers a previous gateway created and never stopped still bill: stop them.
                strays = await cloud.stop_strays()
                if strays:
                    log.warning("stopped %d Browser Use browser(s) left running by a previous gateway", strays)
            try:
                yield
            finally:
                store = tools.sessions_store()
                if store is not None:
                    await store.close_all()      # stopping a browser is what saves its profile's logins

    return Starlette(
        routes=[Route("/health", health), Route("/status", status_route), *rest.routes(authorized, run_tool),
                Mount("/mcp", app=mcp_endpoint)],
        middleware=[Middleware(NormalizeMcpPath)],
        lifespan=lifespan,
    )


def main() -> None:
    logging.basicConfig(level=os.getenv("BB_LOG_LEVEL", "INFO"), stream=sys.stderr)
    uvicorn.run(build_app(), host="0.0.0.0", port=PORT, access_log=False)


if __name__ == "__main__":
    main()
