"""The HTTP/JSON door beside MCP, and the OpenAPI document generated from the same tool cards.

  POST /api/v1/<tool>   the tool's arguments as JSON -> its result as JSON
  GET  /api/v1/status   status, as a GET
  GET  /api/v1/tools    the tools this box offers right now, with their input schemas
  GET  /openapi.json    this API, described (no token: it says what exists, not what is up)

A result carrying "error" is HTTP 422 with the same body, so a command line exits non-zero and
still gets the reason. Same shape as browser-box, so one client pattern drives both boxes.
"""
from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from . import VERSION
from .tools import TOOLS, offered_tools

REFUSED = 422
DEFAULT_HOST = "your-data-box.example.com"


def openapi() -> dict[str, Any]:
    paths: dict[str, Any] = {}
    result = {"description": "The tool's result", "content": {"application/json": {"schema": {"type": "object"}}}}
    refused = {"description": "Refused, or the provider it needs is down: the body's error says which",
               "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}
    unauthorized = {"description": "Missing or wrong bearer token"}
    for card in TOOLS:
        operation = {
            "operationId": card.name,
            "summary": card.summary,
            "description": card.description,
            "tags": ["tools"],
            "responses": {"200": result, "401": unauthorized, "422": refused,
                          "404": {"description": "This box does not offer the tool (its provider is not configured)"}},
        }
        if card.name == "status":
            paths["/api/v1/status"] = {"get": operation}
            continue
        paths[f"/api/v1/{card.name}"] = {"post": {
            **operation,
            "requestBody": {"required": True, "content": {"application/json": {"schema": card.input_schema}}},
        }}
    paths["/api/v1/tools"] = {"get": {
        "operationId": "tools",
        "summary": "The tools this box offers right now, with their input schemas",
        "tags": ["meta"],
        "responses": {"200": {"description": "Offered tools", "content": {"application/json": {"schema": {
            "type": "object", "properties": {"tools": {"type": "array", "items": {"type": "object"}}}}}}},
            "401": unauthorized},
    }}
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "data-box",
            "version": VERSION,
            "description": ("Data and scraping behind one door: scrape, search, crawl, extract and run data sources "
                            "(Firecrawl, Apify, Bright Data, Decodo and more), every paid call capped and metered. "
                            "The same tools are served over MCP at /mcp."),
        },
        "servers": [{"url": "https://{host}", "variables": {"host": {"default": DEFAULT_HOST}}}],
        "security": [{"bearer": []}],
        "components": {
            "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer",
                                           "description": "DATABOX_TOKEN from the box's environment"}},
            "schemas": {"Error": {"type": "object", "required": ["error"], "properties": {
                "error": {"type": "string"}, "tool": {"type": "string"}}}},
        },
        "paths": paths,
    }


def spec_text() -> str:
    return json.dumps(openapi(), indent=2) + "\n"


def routes(authorized, run_tool) -> list[Route]:
    """authorized(request) -> bool and run_tool(name, args) -> dict come from the server, so every
    door shares one token check and one dispatch."""

    def unauthorized() -> JSONResponse:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    def reply(body: dict) -> JSONResponse:
        return JSONResponse(body, status_code=REFUSED if isinstance(body, dict) and "error" in body else 200)

    async def call(request: Request) -> JSONResponse:
        if not authorized(request):
            return unauthorized()
        name = request.path_params["tool"]
        names = [c.name for c in TOOLS]
        if name == "status" or name not in names:
            return JSONResponse({"error": f"no tool {name!r}: POST one of " + ", ".join(n for n in names if n != "status")},
                                status_code=404)
        if name not in {t["name"] for t in offered_tools()}:
            return JSONResponse({"error": f"{name} is not offered on this box: GET /api/v1/status says what is missing",
                                 "tool": name}, status_code=404)
        try:
            raw = await request.body()
            args = json.loads(raw) if raw.strip() else {}
        except ValueError:
            args = None
        if not isinstance(args, dict):
            return JSONResponse({"error": "the body must be a JSON object of the tool's arguments", "tool": name},
                                status_code=400)
        return reply(await run_tool(name, args))

    async def status(request: Request) -> JSONResponse:
        if not authorized(request):
            return unauthorized()
        return reply(await run_tool("status", {}))

    async def tools(request: Request) -> JSONResponse:
        if not authorized(request):
            return unauthorized()
        return JSONResponse({"tools": offered_tools()})

    async def spec(_request: Request) -> JSONResponse:
        return JSONResponse(openapi())

    return [
        Route("/openapi.json", spec, methods=["GET"]),
        Route("/api/v1/status", status, methods=["GET"]),
        Route("/api/v1/tools", tools, methods=["GET"]),
        Route("/api/v1/{tool}", call, methods=["POST"]),
    ]
