"""The tools. If one is listed it works; if part of it cannot work right now, `status` says why.

Every door (MCP, HTTP/JSON, the CLIs) is built from TOOLS, and the OpenAPI document is generated
from it, so the doors cannot drift apart. A verb whose provider is not configured is not listed:
advertising a tool that cannot run is the lie Super Browser's 29-tool surface told, and the reason
this box exists.
"""
from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from . import VERSION, config, fetch
from .jobs import JobContext, Runner, answer
from .ledger import Ledger
from .security import require_public_web

WAIT = {"type": "integer", "minimum": 0, "maximum": 60, "default": 30,
        "description": "How long to wait for the result (seconds). If it is not done by then you get a job_id to poll with `job`."}
REQUEST_ID = {"type": "string", "minLength": 1, "maxLength": 100,
              "description": "Idempotency key: retrying with the same request_id returns the first call's job instead of running (and paying) again."}
MAX_COST = {"type": "number", "minimum": 0, "maximum": 25,
            "description": "Most this call may spend, in US dollars. Paid steps that would exceed it are not started."}


@dataclass
class Card:
    name: str
    summary: str
    description: str
    input_schema: dict[str, Any]
    offered: Callable[[], bool] = field(default=lambda: True)

    def as_tool(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "inputSchema": self.input_schema}


class Box:
    """What handlers work with: the ledger and the job runner. One per server process."""

    def __init__(self, ledger: Ledger, runner: Runner):
        self.ledger = ledger
        self.runner = runner
        self.started = time.time()


# --- scrape ----------------------------------------------------------------------------------

FORMATS = ("markdown", "text", "html", "links")


def _bounded(text: str, limit: int) -> tuple[str, bool]:
    return (text[:limit] + "…", True) if len(text) > limit else (text, False)


async def _scrape_work(args: dict, ctx: JobContext) -> dict:
    fmt = args.get("format", "markdown")
    limit = config.text_limit()
    started = time.monotonic()
    page = await fetch.get(args["url"])
    reading = fetch.read(page)
    verdict = fetch.judge(page, reading)
    rung = {"rung": "fetch", "ok": verdict is None, "seconds": round(time.monotonic() - started, 2), "cost_usd": 0.0}
    if verdict:
        rung["reason"] = verdict["reason"]
    result: dict[str, Any] = {
        "url": page.url, "final_url": page.final_url, "status_code": page.status_code, "rung": "fetch",
        "format": fmt, "title": reading.title, "description": reading.description,
        "rungs_tried": [rung],
    }
    if fmt == "links":
        result["links"] = reading.links[:500]
        result["links_count"] = len(reading.links)
    else:
        content = {"markdown": reading.markdown, "text": reading.text, "html": page.text()}[fmt]
        result["content"], cut = _bounded(content, limit)
        result["content_chars"] = len(content)
        result["content_truncated"] = cut or page.truncated
    if verdict:
        result["blocked"] = verdict
        result["next"] = ("no paid rung is configured on this box yet, so the ladder stops at the free fetch; "
                          "status lists which providers would take the next step")
    result["_detail"] = f"{page.status_code} {page.final_url}"[:200]
    return result


async def scrape(args: dict, box: Box) -> dict:
    # Refuse a bad or private URL before a job exists; the DNS check runs inside the job.
    require_public_web(args["url"])
    cap = float(args.get("max_cost_usd", config.default_scrape_cap_usd()))
    job = await box.runner.start("scrape", args, lambda ctx: _scrape_work(args, ctx), cap_usd=cap)
    return answer(await box.runner.wait(job["job_id"], args.get("wait_seconds", 30)))


# --- job -------------------------------------------------------------------------------------

def _items(job: dict) -> list[Any]:
    result = job.get("result")
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return result["items"]
    if isinstance(result, dict) and isinstance(result.get("links"), list):
        return result["links"]
    return [] if result is None else [result]


def _export(items: list[Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(items, ensure_ascii=False, indent=2, default=str)
    if fmt == "jsonl":
        return "\n".join(json.dumps(item, ensure_ascii=False, default=str) for item in items)
    rows = [item if isinstance(item, dict) else {"value": item} for item in items]
    columns: list[str] = []
    for row in rows:
        columns += [k for k in row if k not in columns]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, default=str) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    return out.getvalue()


async def job(args: dict, box: Box) -> dict:
    action = args["action"]
    if action == "list":
        return {"jobs": box.ledger.jobs(args.get("limit", 20), args.get("status"), args.get("tool"))}
    if not args.get("job_id"):
        raise ValueError(f"job action={action} needs a job_id")
    job_id = args["job_id"]
    try:
        current = box.ledger.job(job_id)
    except KeyError:
        raise ValueError(f"no job {job_id!r}; job action=list shows recent ones") from None
    if action == "get":
        return await box.runner.wait(job_id, args.get("wait_seconds", 0))
    if action == "cancel":
        return await box.runner.cancel(job_id)
    items = _items(current)
    if action == "results":
        offset, limit = args.get("offset", 0), args.get("limit", 50)
        return {"job_id": job_id, "status": current["status"], "total": len(items), "offset": offset,
                "items": items[offset:offset + limit]}
    fmt = args.get("format", "json")
    content = _export(items, fmt)
    if len(content) > 5_000_000:
        raise ValueError(f"the export is {len(content)} characters; page through it with action=results instead")
    return {"job_id": job_id, "format": fmt, "rows": len(items), "content": content}


# --- status ----------------------------------------------------------------------------------

WIRED: set[str] = set()  # providers data-box calls today; a configured provider not in here is reported as waiting


async def status(_args: dict, box: Box) -> dict:
    components: list[dict[str, Any]] = [
        {"name": "fetch (scrape rung 0, free)", "up": True, "detail": "direct pinned HTTP GET of public pages"},
    ]
    try:
        running = len(box.ledger.jobs(200, "running"))
        components.append({"name": "ledger", "up": True, "detail": f"{running} job(s) running"})
    except Exception as exc:
        components.append({"name": "ledger", "up": False, "detail": str(exc)[:200]})
    for name, spec in config.PROVIDERS.items():
        configured = config.configured(name)
        entry: dict[str, Any] = {"name": name, "configured": configured, "for": spec["for"]}
        if name in WIRED:
            entry["up"] = configured
            entry["detail"] = "ready" if configured else "not configured: set " + ", ".join(spec["env"])
        else:
            entry["up"] = False
            entry["detail"] = ("configured, but data-box does not call it yet" if configured
                               else "not configured (set " + ", ".join(spec["env"]) + "); data-box does not call it yet")
        components.append(entry)
    offered = [c.name for c in TOOLS if c.offered()]
    unavailable = [] if components[1]["up"] else [{"tool": t, "reason": "the ledger is unusable"} for t in offered if t != "status"]
    down = {u["tool"] for u in unavailable}
    return {
        "service": "data-box", "version": VERSION, "revision": config.revision(),
        "components": components,
        "tools_working_now": [t for t in offered if t not in down],
        "tools_unavailable": unavailable,
        "spend_last_24h_usd": box.ledger.spend_since(time.time() - 86400),
        "recent_calls": box.ledger.recent_calls(10),
    }


# --- the cards -------------------------------------------------------------------------------

TOOLS: list[Card] = [
    Card(
        name="status",
        summary="What works, what does not and why, and what recent calls cost",
        description=(
            "What this box can do right now. Lists every provider (configured or not, and what it is for), "
            "the tools working now, any tool that is down with a one-line reason, spend over the last 24 hours, "
            "and the last 10 calls. Call it first when something fails, and report its reason instead of guessing.\n"
            "Free; touches no provider."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    Card(
        name="scrape",
        summary="One public URL to markdown, text, HTML or links",
        description=(
            "Read one public web page and return its content as markdown (default), plain text, raw HTML, or "
            "its list of links. Use it for any single URL you already have.\n"
            "It climbs a ladder and stops at the first rung that returns the real page: a free direct fetch "
            "first, then paid unblockers and finally a real browser, never spending past max_cost_usd "
            "(default $0.05). rungs_tried shows each rung, its cost and why it was left. On this box today only "
            "the free fetch is wired: a blocked, challenge or JavaScript-only page comes back with `blocked` "
            "saying what stopped it.\n"
            "Do NOT use it to search (use websearch), to walk a whole site (crawl), or for private addresses: "
            "loopback, private, link-local and file targets are refused, on every redirect too.\n"
            "Returns: content (or links), title, description, status_code, final_url, rung, rungs_tried, "
            "blocked when the page was not the real page, job_id and cost_usd."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Public http(s) URL"},
                "format": {"type": "string", "enum": list(FORMATS), "default": "markdown"},
                "max_cost_usd": MAX_COST,
                "wait_seconds": WAIT,
                "request_id": REQUEST_ID,
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    ),
    Card(
        name="job",
        summary="Get, list, cancel, page through or export a job",
        description=(
            "Every call that can take a while is a job, and this is how you follow one.\n"
            "get -> the job and its result (wait_seconds to wait for it to finish). list -> recent jobs "
            "(filter by status or tool). cancel -> stop it; paid steps already taken stay charged. "
            "results -> page through its items (offset, limit). export -> all items as csv, json or jsonl.\n"
            "Free."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["get", "list", "cancel", "results", "export"]},
                "job_id": {"type": "string", "description": "Required for everything but list"},
                "wait_seconds": {**WAIT, "default": 0},
                "status": {"type": "string", "enum": ["queued", "running", "succeeded", "failed", "cancelled", "interrupted"]},
                "tool": {"type": "string", "description": "list: only jobs of this tool"},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                "format": {"type": "string", "enum": ["csv", "json", "jsonl"], "default": "json"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    ),
]

HANDLERS: dict[str, Callable[[dict, Box], Awaitable[dict]]] = {"status": status, "scrape": scrape, "job": job}


def card(name: str) -> Card | None:
    return next((c for c in TOOLS if c.name == name), None)


def offered_tools() -> list[dict[str, Any]]:
    return [c.as_tool() for c in TOOLS if c.offered()]
