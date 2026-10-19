"""A plain HTTP/JSON door beside MCP, for command lines, scripts and anything without an MCP client.

Same bearer token, same handlers, same checks: each tool is one POST whose body is the
tool's arguments. It exists so the box has an OpenAPI description, which is what CLI generators
(and curl users) work from. The spec is built from the tool cards themselves, so it cannot drift
from what MCP callers are told.

  POST /api/v1/<tool>   the tool's arguments as JSON → its result as JSON
  GET  /api/v1/status   status, as a GET
  GET  /api/v1/tools    the tools this box offers right now, with their input schemas
  GET  /openapi.json    this API, described (no token: it says what exists, not what is up)

A result carrying "error" (a refusal, or a part of the box that is down) is HTTP 422 with the
same JSON body, so a command line exits non-zero and still gets the reason.
"""
from __future__ import annotations

import json
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .tools import TASK_SURFACES, TOOLS, offered_tools

VERSION = "1.0.0"
REFUSED = 422

# One line each, for the spec's operation summaries (the full card is the description).
SUMMARIES = {
    "fetch": "Plain HTTP GET of a public URL, no browser",
    "read": "Open a URL in the real browser and return its text, links and optionally a screenshot",
    "session": "Create, list or release a persistent browser session (logins survive between calls)",
    "act": "Drive the browser in plain-words steps; Jev picks each element",
    "computer": "Drive an Orgo cloud desktop: screenshot, click, type, key, scroll, bash, start, stop",
    "task": "Hand a whole goal to an agent (Browser-Use in the browser, or Orgo on a desktop)",
    "status": "What is up, what is down and why, and what recent calls cost",
}


def _card_for_spec(card: dict[str, Any]) -> dict[str, Any]:
    """The task card names only this box's surfaces at runtime; the spec describes them all."""
    if card["name"] != "task":
        return card
    text = "\n".join(desc for _, desc in TASK_SURFACES.values())
    return {**card, "description": card["description"].replace("{surfaces}", text)}


def openapi() -> dict[str, Any]:
    paths: dict[str, Any] = {}
    result = {"description": "The tool's result", "content": {"application/json": {"schema": {"type": "object"}}}}
    refused = {"description": "Refused, or the part of the box it needs is down: the body's error says which",
               "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}
    unauthorized = {"description": "Missing or wrong bearer token"}
    for card in map(_card_for_spec, TOOLS):
        name = card["name"]
        operation = {
            "operationId": name,
            "summary": SUMMARIES[name],
            "description": card["description"],
            "tags": ["tools"],
            "responses": {"200": result, "401": unauthorized, "422": refused,
                          "404": {"description": "This box does not offer the tool (its integration is not configured)"}},
        }
        if name == "status":
            paths["/api/v1/status"] = {"get": {**operation, "operationId": "status"}}
            continue
        paths[f"/api/v1/{name}"] = {"post": {
            **operation,
            "requestBody": {"required": True, "content": {"application/json": {"schema": card["inputSchema"]}}},
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
            "title": "browser-box",
            "version": VERSION,
            "description": ("Hosted browsers (Browser Use Cloud, Browserbase as the fallback) behind one door. The same tools are "
                            "served over MCP at /mcp. The calling agent is the brain; the box executes."),
        },
        "servers": [{"url": "https://{host}", "variables": {"host": {"default": "your-box.example.com"}}}],
        "security": [{"bearer": []}],
        "components": {
            "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer",
                                           "description": "BB_TOKEN from the box's .env"}},
            "schemas": {"Error": {"type": "object", "required": ["error"], "properties": {
                "error": {"type": "string"}, "tool": {"type": "string"}}}},
        },
        "paths": paths,
    }


def routes(authorized, run_tool) -> list[Route]:
    """authorized(request) -> bool and run_tool(name, args) -> dict come from the server, so
    both doors share one token check and one dispatch."""

    def unauthorized() -> JSONResponse:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    def answer(result: dict) -> JSONResponse:
        return JSONResponse(result, status_code=REFUSED if isinstance(result, dict) and "error" in result else 200)

    async def call(request: Request) -> JSONResponse:
        if not authorized(request):
            return unauthorized()
        name = request.path_params["tool"]
        if name == "status" or name not in {t["name"] for t in TOOLS}:
            return JSONResponse({"error": f"no tool {name!r}: POST one of " + ", ".join(
                t["name"] for t in TOOLS if t["name"] != "status")}, status_code=404)
        if name not in {t["name"] for t in offered_tools()}:
            return JSONResponse({"error": f"{name} is not offered on this box: GET /api/v1/status says what is missing",
                                 "tool": name}, status_code=404)
        try:
            body = await request.body()
            args = json.loads(body) if body.strip() else {}
        except ValueError:
            return JSONResponse({"error": "the body must be a JSON object of the tool's arguments", "tool": name},
                                status_code=400)
        if not isinstance(args, dict):
            return JSONResponse({"error": "the body must be a JSON object of the tool's arguments", "tool": name},
                                status_code=400)
        return answer(await run_tool(name, args))

    async def status(request: Request) -> JSONResponse:
        if not authorized(request):
            return unauthorized()
        return answer(await run_tool("status", {}))

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
