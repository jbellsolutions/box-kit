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

from . import VERSION, config, execution, fetch, planning
from .jobs import JobContext, Runner, answer
from .ledger import Conflict, Ledger
from .providers.firecrawl import Firecrawl, FirecrawlError
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
    """What handlers work with: the ledger, the job runner and the provider clients. One per server process."""

    def __init__(self, ledger: Ledger, runner: Runner, firecrawl: Callable[[], Firecrawl] | None = None):
        self.ledger = ledger
        self.runner = runner
        self.firecrawl = firecrawl or (lambda: Firecrawl())
        self.started = time.time()


def _plan_or_refuse(box: Box, plan_id: str) -> dict:
    try:
        return box.ledger.plan(plan_id)
    except KeyError:
        raise ValueError(f"no plan {plan_id!r}; plan action=list shows recent ones") from None


# --- scrape ----------------------------------------------------------------------------------

FORMATS = ("markdown", "text", "html", "links")


def _bounded(text: str, limit: int) -> tuple[str, bool]:
    return (text[:limit] + "…", True) if len(text) > limit else (text, False)


async def _scrape_work(args: dict, ctx: JobContext, box: Box) -> dict:
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
        made = None
        if config.configured("firecrawl"):
            # The free rung could not read it. The paid rungs are a plan the user approves, never a surprise.
            try:
                made = await planning.make_plan({"kind": "scrape", "url": args["url"], "format": fmt}, ctx.ledger,
                                                box.firecrawl())
            except (FirecrawlError, ValueError, Conflict) as exc:
                result["next"] = f"the free fetch was not enough, and a plan for the paid rungs could not be made: {exc}"[:300]
        if made:
            game = made["body"]["step_3_game_plan"]
            lane = (game.get("lanes") or [{}])[0]
            result["plan"] = {"plan_id": made["plan_id"], "status": made["status"], "budget_usd": made["budget_usd"],
                              "rungs": lane.get("ladder"), "credits": game.get("credits_total"),
                              "warnings": game.get("warnings")}
            result["next"] = (f"the free fetch was not enough; plan {made['plan_id']} takes it to Firecrawl (rung 1) for "
                              f"up to ${made['budget_usd']:.4f}. Show it to the user, and on a yes call execute with "
                              f"plan_id={made['plan_id']} and approve=true")
        elif "next" not in result:
            result["next"] = ("no paid rung is configured on this box, so the ladder stops at the free fetch; "
                              "status lists which providers would take the next step")
    result["_detail"] = f"{page.status_code} {page.final_url}"[:200]
    return result


async def scrape(args: dict, box: Box) -> dict:
    # Refuse a bad or private URL before a job exists; the DNS check runs inside the job.
    require_public_web(args["url"])
    cap = float(args.get("max_cost_usd", config.default_scrape_cap_usd()))
    job = await box.runner.start("scrape", args, lambda ctx: _scrape_work(args, ctx, box), cap_usd=cap)
    return answer(await box.runner.wait(job["job_id"], args.get("wait_seconds", 30)))


# --- job -------------------------------------------------------------------------------------

def _items(job: dict) -> list[Any]:
    result = job.get("result")
    if isinstance(result, dict) and result.get("records_file") and result.get("plan_id"):
        return execution.records_for(result["plan_id"])
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

WIRED: set[str] = {"firecrawl"}  # providers data-box calls today; a configured provider not in here is reported as waiting


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
            if name == "firecrawl" and configured:
                try:
                    client = box.firecrawl()
                    client.timeout = min(client.timeout, 10)
                    balance = await client.credits()
                    entry["balance_credits"] = balance.get("remaining")
                    entry["plan_credits"] = balance.get("plan")
                    entry["period_end"] = balance.get("period_end")
                    if (balance.get("remaining") or 0) <= 0:
                        entry["detail"] = "configured, but the balance is empty: paid plans cannot execute until credits are added"
                except FirecrawlError as exc:
                    entry["up"] = False
                    entry["detail"] = f"configured, but the balance could not be read: {exc}"[:240]
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
        "plans_awaiting_approval": box.ledger.plans(20, "awaiting_approval"),
        "plans_executing": box.ledger.plans(20, "executing"),
        "recent_calls": box.ledger.recent_calls(10),
    }


# --- sources, plan, execute: the four steps --------------------------------------------------

async def sources(args: dict, box: Box) -> dict:
    """Step 2 on its own: every source that could serve, free. Without a URL it surveys for a pull."""
    if not args.get("kind") and not (args.get("url") or args.get("urls")):
        args = {**args, "kind": "pull"}
    it = planning.intake(args)
    surveyed, _ = await planning.survey(it, box.firecrawl() if config.configured("firecrawl") else None)
    return {"intake": it, **surveyed}


async def _plan_work(args: dict, ctx: JobContext, box: Box) -> dict:
    made = await planning.make_plan(args, ctx.ledger, box.firecrawl(), ctx)
    game = made["body"].get("step_3_game_plan", {})
    return {"plan_id": made["plan_id"], "plan": made,
            "_detail": f"{made['plan_id']}: {len(game.get('lanes') or [])} lane(s), ${game.get('usd_total', 0):.4f}"}


async def plan(args: dict, box: Box) -> dict:
    action = args.get("action", "new")
    if action == "list":
        return {"plans": box.ledger.plans(args.get("limit", 20), args.get("status"))}
    if action in ("get", "cancel"):
        if not args.get("plan_id"):
            raise ValueError(f"plan action={action} needs a plan_id")
        current = _plan_or_refuse(box, args["plan_id"])
        if action == "get":
            return current
        if current["status"] in ("done", "expired", "cancelled"):
            return current
        if current["status"] == "executing" and current["jobs"]:
            await box.runner.cancel(current["jobs"][-1])
        box.ledger.set_plan_status(current["plan_id"], "cancelled")
        return box.ledger.plan(current["plan_id"])
    plan_args = {k: v for k, v in args.items() if k not in ("action", "plan_id", "wait_seconds", "status")}
    it = planning.intake(plan_args)  # refuse a bad request before a job exists
    planning.purge_old()
    rate = config.firecrawl_usd_per_credit()
    cap = config.preflight_max_credits() * rate if it["kind"] == "pull" and it["preflight"] else 0.0
    if it["max_cost_usd"] is not None:
        cap = min(cap, it["max_cost_usd"])
    job = await box.runner.start("plan", plan_args, lambda ctx: _plan_work(plan_args, ctx, box), cap_usd=round(cap, 6))
    return answer(await box.runner.wait(job["job_id"], args.get("wait_seconds", 60)))


async def execute(args: dict, box: Box) -> dict:
    if args.get("approve") is not True:
        raise ValueError("execute runs only an approved plan: show the plan to the user and, on their yes, "
                         "call execute again with approve=true")
    prior = box.ledger.job_by_request(args.get("request_id"))
    if prior:
        return answer(await box.runner.wait(prior["job_id"], args.get("wait_seconds", 30)))
    current = _plan_or_refuse(box, args["plan_id"])
    if current["status"] == "executing" and current["jobs"]:
        return answer(await box.runner.wait(current["jobs"][-1], args.get("wait_seconds", 30)))
    approved = float(args.get("max_cost_usd", current["budget_usd"]))
    plan_id = current["plan_id"]
    current = box.ledger.begin_execution(plan_id, approved)  # approved and executing, atomically
    try:
        left = round(approved - box.ledger.plan_spent(plan_id), 6)
        if left <= 0:
            raise Conflict(f"plan {plan_id} has already spent its approved ${approved:.4f}; make a new plan to go further")
        job_args = {"plan_id": plan_id, "max_cost_usd": approved, "drop_lanes": args.get("drop_lanes") or [],
                    "request_id": args.get("request_id")}
        fc = box.firecrawl()
        job = await box.runner.start(
            "execute", job_args, lambda ctx: execution.run(current, ctx, fc, box.ledger, job_args["drop_lanes"]), cap_usd=left)
        box.ledger.attach_job(plan_id, job["job_id"])  # no await since start: nothing can slip in between
    except BaseException:
        box.ledger.set_plan_status(plan_id, "approved")
        raise
    return answer(await box.runner.wait(job["job_id"], args.get("wait_seconds", 30)))


def _firecrawl_ready() -> bool:
    return config.configured("firecrawl")


PLAN_REQUEST = {
    "request": {"type": "string", "maxLength": 2000,
                "description": "What is wanted, in plain words: \"roofing contractors in Austin TX with phone and website\""},
    "kind": {"type": "string", "enum": list(planning.KINDS),
             "description": "pull (a list of records), search, scrape, crawl or extract; inferred when left out"},
    "entity": {"type": "string", "enum": list(planning.ENTITIES), "description": "pull: what each record is (default business)"},
    "count": {"type": "integer", "minimum": 1, "maximum": 50000, "description": "pull: how many unique records are wanted (default 100)"},
    "fields": {"type": "array", "items": {"type": "string"}, "maxItems": 20,
               "description": "pull: fields each record needs, e.g. [\"phone\", \"website\"]; lanes are ranked by how many they return"},
    "queries": {"type": "array", "items": {"type": "string"}, "maxItems": 20,
                "description": "pull/search: what to search for (default: the request); each is crossed with every place in geo"},
    "geo": {"type": "array", "items": {"type": "string"}, "maxItems": 100,
            "description": "pull: places to cover, e.g. [\"Austin, TX\", \"Dallas, TX\"]; each is a cell of the pull"},
    "sources": {"type": "array", "items": {"type": "string"}, "maxItems": 10,
                "description": "Sources the user named (e.g. \"bbb\", \"bing\", \"discolike\"): the plan uses only these, and says so when one cannot run"},
    "url": {"type": "string", "description": "scrape/crawl: the page or site"},
    "urls": {"type": "array", "items": {"type": "string"}, "maxItems": 100, "description": "extract: the pages"},
    "schema": {"type": "object", "description": "extract (or scrape): JSON schema of what to pull out"},
    "prompt": {"type": "string", "maxLength": 2000, "description": "extract: what to pull out, in words"},
    "format": {"type": "string", "enum": ["markdown", "html", "links"], "default": "markdown"},
    "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "description": "search: results per query; crawl: most pages"},
    "max_cost_usd": {"type": "number", "minimum": 0, "maximum": 500,
                     "description": "Most the whole plan may spend, preflight included (default: the estimate plus 20%)"},
    "preflight": {"type": "boolean", "default": True,
                  "description": "pull: spend one real call per lane (at most 25 credits) to prove it returns the entity"},
    "max_lanes": {"type": "integer", "minimum": 1, "maximum": 6, "default": 3},
    "oversample": {"type": "number", "minimum": 1, "maximum": 5, "default": 1.5,
                   "description": "pull: raw records planned per wanted record, to cover duplicates across lanes"},
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
            "It runs the free direct fetch at once. Paid rungs never run without approval: when the free fetch "
            "is blocked, gets a challenge or a JavaScript-only page, the result says what stopped it (`blocked`) "
            "and carries a `plan` for the paid ladder (Firecrawl first; then Decodo, Bright Data, Firecrawl's "
            "browser, Hyperbrowser and browser-box as they are wired) with its worst-case cost. Show that plan to "
            "the user; on a yes, call execute with its plan_id and approve=true.\n"
            "Do NOT use it to search or to walk a whole site (make a plan with kind search or crawl), or for private addresses: "
            "loopback, private, link-local and file targets are refused, on every redirect too.\n"
            "Returns: content (or links), title, description, status_code, final_url, rung, rungs_tried, "
            "blocked and plan when the page was not the real page, job_id and cost_usd (always 0: the free rung)."
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
    Card(
        name="sources",
        summary="Every source that could serve a need, tier by tier, and whether each can run (free)",
        description=(
            "Step 2 of the four-step workflow on its own: survey every source that could serve a request, without "
            "planning or spending anything. Tier 1 is Firecrawl (its Alexandria providers, read live: price, page "
            "size, pagination, inputs, terms, field fit), MoltSets and DiscoLike; tier 2 Decodo and Bright Data; "
            "tier 3 Apify, the expensive backup's backup. Each source says whether it can run on this box and, if "
            "not, why.\n"
            "Use it to answer \"where could this data come from?\". To get the data, call plan instead: it runs "
            "the same survey and turns it into a priced game plan.\n"
            "Free."
        ),
        input_schema={"type": "object", "properties": {k: PLAN_REQUEST[k] for k in (
            "request", "kind", "entity", "fields", "queries", "geo", "sources", "url", "urls", "schema", "prompt")},
            "additionalProperties": False},
    ),
    Card(
        name="plan",
        summary="Steps 1-3: take a request, survey every source, return a priced game plan to approve",
        description=(
            "Every paid pull starts here, whatever door it comes through. plan takes the request (step 1), surveys "
            "every source across the tiers and lists them all (step 2): for Firecrawl that means every tool in the "
            "Alexandria categories the request is about, read with its contract. Then it narrows them to a game "
            "plan (step 3): lanes ranked by records per credit x coverage x field fit, each proven by a preflight "
            "call (a lane whose preflight returns none of the entity is dropped and the next one tried), split into "
            "query x place cells and pages within the skill's caps, the dedupe keys, and the worst-case cost in "
            "credits and dollars against the live Firecrawl balance. A source the user named is honoured.\n"
            "Nothing but the preflight is spent (at most 25 credits, and never more than max_cost_usd). The plan "
            "waits for approval and expires after 24 hours.\n"
            "Then: SHOW THE WHOLE PLAN TO THE USER and wait for a yes. Only then call execute with its plan_id and "
            "approve=true. Never approve a plan on the user's behalf.\n"
            "action=get returns a plan, action=list recent plans, action=cancel withdraws one (stopping its job)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["new", "get", "list", "cancel"], "default": "new"},
                "plan_id": {"type": "string", "description": "get/cancel: which plan"},
                "status": {"type": "string", "enum": ["preparing", "awaiting_approval", "approved", "executing",
                                                      "done", "expired", "cancelled"], "description": "list: only plans in this status"},
                **PLAN_REQUEST,
                "wait_seconds": {**WAIT, "default": 60},
                "request_id": REQUEST_ID,
            },
            "additionalProperties": False,
        },
        offered=_firecrawl_ready,
    ),
    Card(
        name="execute",
        summary="Step 4: run a plan the user approved, within its budget, resumably",
        description=(
            "Runs a plan from `plan`, only after the user has approved it: pass its plan_id and approve=true. It "
            "spends at most the approved amount (the plan's budget, or a lower max_cost_usd), preflight included.\n"
            "A pull runs its lanes in order (base layer first, then top-ups), stops a cell at its first short page "
            "or once its pages mostly repeat, stops calling once the deduped list reaches the requested count, never "
            "lets the Firecrawl balance go below zero, and dedupes across lanes on name+phone and name+address. "
            "Calling execute again on the same plan resumes it without paying for finished pages twice.\n"
            "Returns counts, what each lane did, and a sample; the rows are read with job action=results or "
            "action=export (csv/json/jsonl). Records are deleted after the retention period (30 days).\n"
            "drop_lanes leaves out lanes the user struck from the plan."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "approve": {"type": "boolean", "description": "Must be true: the user said yes to this plan"},
                "max_cost_usd": {"type": "number", "minimum": 0, "maximum": 500,
                                 "description": "Approve less than the plan's budget (never more)"},
                "drop_lanes": {"type": "array", "items": {"type": "string"}, "description": "Lanes (provider/capability) to leave out"},
                "wait_seconds": WAIT,
                "request_id": REQUEST_ID,
            },
            "required": ["plan_id", "approve"],
            "additionalProperties": False,
        },
        offered=_firecrawl_ready,
    ),
]

HANDLERS: dict[str, Callable[[dict, Box], Awaitable[dict]]] = {
    "status": status, "scrape": scrape, "job": job, "sources": sources, "plan": plan, "execute": execute}


def card(name: str) -> Card | None:
    return next((c for c in TOOLS if c.name == name), None)


def offered_tools() -> list[dict[str, Any]]:
    return [c.as_tool() for c in TOOLS if c.offered()]
