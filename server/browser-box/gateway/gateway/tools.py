"""The tools. If one is listed it works; if it cannot work right now, `status` says why.

Two rules decide what is listed. Core tools (fetch, read, session, status) are always
listed, and an outage of the browser behind them is reported by `status`. Optional
integrations (Jev's act, Browser-Use's and Orgo's task surfaces, Orgo's computers) are listed
only when configured: a box without an Orgo key has no computers, and advertising one would be
the exact lie this repo exists to stop. `task` lists only the surfaces this box has.

There is deliberately no provider catalog, no readiness walkthrough, no plan/verify/resume
and no doctor variants. That surface is what made the previous system unusable: 29 tools
of which 22 could not reach a browser.
"""
from __future__ import annotations

import asyncio
import base64
import os
import time
from typing import Any

import httpx

from . import browseruse, jev, orgo, steel
from .guard import GUARD
from .lock import LaneBusy, lane
from .security import UnsafeUrl, require_public_addresses, require_public_web

TEXT_LIMIT = int(os.getenv("BB_TEXT_LIMIT", "24000"))
FETCH_TIMEOUT = float(os.getenv("BB_FETCH_TIMEOUT_SECONDS", "30"))
USER_AGENT = os.getenv("BB_USER_AGENT", "browser-box/1.0 (+https://github.com/jbellsolutions/browser-box)")

TOOLS: list[dict[str, Any]] = [
    {
        "name": "fetch",
        "description": (
            "Plain HTTP GET, no browser. Fastest and free. Use it FIRST for any page that is "
            "server-rendered HTML, JSON or plain text — news sites, docs, APIs, RSS.\n"
            "Do NOT use when: the page needs JavaScript to render, is behind a login, or blocks bots.\n"
            "Returns: text (HTML stripped to readable text), status_code, final_url."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Public http(s) URL"}},
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "read",
        "description": (
            "Open a URL in the real browser and return its rendered text, links and optionally a "
            "screenshot. Use when fetch returned nothing useful because the page renders with JavaScript.\n"
            "Do NOT use when: fetch already answered (this costs a browser slot), or the task needs "
            "clicking and typing rather than reading.\n"
            "One browser runs at a time on this host; this call waits for the lane and then holds it.\n"
            "The screenshot is a SECOND, independent page load, so on a page that changes between "
            "loads the picture and the text may not agree, and that navigation is NOT pre-flighted. "
            "Ask for it when the picture is the evidence.\n"
            "Returns: text, title, links, status_code, and screenshot_base64 (JPEG) when asked for."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Public http(s) URL"},
                "screenshot": {"type": "boolean", "description": "Also return a full-page JPEG. Costs a SECOND page load, and that one is NOT redirect-checked — ask for it only when the picture is the evidence.", "default": False},
                "delay_ms": {"type": "integer", "minimum": 0, "maximum": 15000, "description": "Wait this long after load for late content."},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "session",
        "description": (
            "Create, list or release a persistent browser session. A session keeps cookies and a "
            "profile across calls, which is how logged-in work is done.\n"
            "create -> returns session_id and the live view URL so a human can sign in once.\n"
            "list   -> what is currently open. release -> closes it and frees the lane.\n"
            "Creating or releasing a session restarts the browser: act's tab starts again at about:blank.\n"
            "Do NOT create a session for one-off public reads; `read` is cheaper and releases itself."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "list", "release"]},
                "session_id": {"type": "string", "description": "Required for release"},
                "timeout_seconds": {"type": "integer", "minimum": 60, "maximum": 3600, "default": 900},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    {
        "name": "act",
        "description": (
            "Drive the browser step by step in plain words: \"open https://…\", \"click the Pricing link\", "
            "\"type 'running shoes' into the search box and press enter\", \"scroll down\", \"go back\". "
            "You plan the steps; Jev, a decision model that never writes text, picks which element on the "
            "page each step means (typically ~0.3 s; page loads take longer). Up to 4 steps joined by \"then\" or \"and\" run in order.\n"
            "When Jev is unsure it asks instead of guessing: status needs_clarification with options — answer "
            "with act(pick=<option pick>). Anything that looks hard to undo (buy, delete, send, post) comes back "
            "as needs_confirmation — answer with act(confirm=true) or act(confirm=false). Nothing risky runs unconfirmed.\n"
            "Prefer act over task whenever you can say the steps: measured on search, forms, pagination, state and "
            "a JS app, it was 10–60x faster and as or more accurate on all but search (see the README). Read each "
            "step's did: a click on a link marked (page does not exist) is a wrong pick, so say which one you meant.\n"
            "Use for clicking, typing, forms and multi-page flows. Do NOT use just to read a public page: fetch "
            "or read is cheaper. The tab stays where you left it between calls; creating or releasing a session "
            "restarts the browser and the tab starts again at about:blank.\n"
            "Private and internal addresses are refused inside the browser itself, on every request and redirect.\n"
            "Returns: status (done | failed | needs_clarification | needs_confirmation), steps (what ran and how "
            "each went), url, title, and the page's text when read_page=true."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "minLength": 1, "description": "One step, or up to 4 joined by then/and"},
                "pick": {"type": "string", "description": "Answer to needs_clarification: one option's pick"},
                "confirm": {"type": "boolean", "description": "Answer to needs_confirmation"},
                "read_page": {"type": "boolean", "default": False, "description": "Also return the page's readable text afterwards"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "computer",
        "description": (
            "Drive an Orgo cloud computer: a full Linux desktop with a browser and a shell, running "
            "OFF this box. You are the eyes — take a screenshot, decide, act, screenshot again. "
            "Coordinates are pixels in the most recent screenshot.\n"
            "Actions: screenshot | click(x, y[, button, double]) | type(text) | key(key, e.g. \"Return\", "
            "\"ctrl+c\") | scroll(x, y[, direction, amount]) | bash(command) | start | stop.\n"
            "Do NOT use for a web page that fetch or read can answer: this is a whole computer, billed per hour.\n"
            "bash is a real shell on that computer, inside your Orgo account.\n"
            "A computer bills until it is stopped. Call action=stop when you are finished."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["screenshot", "click", "type", "key", "scroll", "bash", "start", "stop"]},
                "x": {"type": "integer", "minimum": 0},
                "y": {"type": "integer", "minimum": 0},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
                "double": {"type": "boolean", "default": False},
                "text": {"type": "string", "description": "For type"},
                "key": {"type": "string", "description": "For key: a key or a +-joined combination"},
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "default": "down"},
                "amount": {"type": "integer", "minimum": 1, "maximum": 50, "default": 3},
                "command": {"type": "string", "description": "For bash"},
                "screenshot_after": {"type": "boolean", "default": False,
                                     "description": "Return a screenshot after the action, saving a round trip"},
                "computer_id": {"type": "string", "description": "Omit to use the pinned or running computer"},
                "screen_id": {"type": "string", "description": "Target this exact Orgo screen; unknown ids fail closed"},
                "context": {"type": "boolean", "default": False, "description": "Include screen and focused Chrome element context"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    {
        "name": "task",
        # The description and the surface enum are narrowed to the configured surfaces by offered_tools().
        "description": "\n".join((
            "Hand a whole goal to an agent and wait for its answer. Use it when you would rather not plan "
            "the steps yourself; you lose sight of each step, and every step costs model time.",
            "Measured against act: 30–130 s per job, and less reliable. It failed a two-URL cookie job 2 of 3 "
            "times and a JS to-do app 3 of 3. Check its answer before trusting it.",
            "{surfaces}",
            "Do NOT use when one fetch or read answers it, or when you can drive the steps yourself with "
            "act or computer: that is faster, cheaper and you see every step.",
        )),
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "minLength": 1, "description": "What to achieve and what to report back, in plain words. Required to start a task"},
                "cancel": {"type": "boolean", "description": "browser only: stop the running task instead of starting one"},
                "surface": {"type": "string", "enum": ["browser", "computer"]},
                "max_steps": {"type": "integer", "minimum": 1, "maximum": 50, "default": 25,
                              "description": "browser only: the most model steps it may take"},
                "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 1800,
                                    "description": "Hitting it stops the run. Default 300 on the browser (at most 900), 600 on a computer"},
                "computer_id": {"type": "string", "description": "computer only"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "status",
        "description": (
            "What is running, what is healthy, and what the last calls cost. Call this when a tool "
            "fails, before assuming a capability is missing. It answers honestly: a component that "
            "is down is reported as down, with the reason."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

_CALLS: list[dict[str, Any]] = []


def _record(name: str, started: float, ok: bool, detail: str = "", cost_usd: float | None = None) -> None:
    row = {"tool": name, "seconds": round(time.monotonic() - started, 2), "ok": ok, "detail": detail[:160], "at": time.time()}
    if cost_usd is not None:
        row["cost_usd"] = cost_usd
    _CALLS.append(row)
    del _CALLS[:-25]


def strip_html(raw: str) -> str:
    """Readable text from an HTML body: drops script/style, keeps visible text lines."""
    if "<" not in raw[:2000]:
        return raw
    from html.parser import HTMLParser

    class Text(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.parts: list[str] = []
            self.hidden = 0

        def handle_starttag(self, tag: str, attrs: Any) -> None:
            if tag in ("script", "style", "noscript", "template"):
                self.hidden += 1

        def handle_endtag(self, tag: str) -> None:
            if tag in ("script", "style", "noscript", "template") and self.hidden:
                self.hidden -= 1

        def handle_data(self, data: str) -> None:
            if not self.hidden and data.strip():
                self.parts.append(data.strip())

    parser = Text()
    parser.feed(raw)
    return "\n".join(parser.parts)


def _bounded(text: str) -> dict[str, Any]:
    return {"text": text[:TEXT_LIMIT] + ("…" if len(text) > TEXT_LIMIT else ""), "text_chars": len(text)}


MAX_HOPS = int(os.getenv("BB_MAX_REDIRECTS", "8"))


async def safe_target(url: str) -> str:
    """The URL as written must be public, and every address it resolves to must be too."""
    target = require_public_web(url)
    host = httpx.URL(target).host
    await asyncio.to_thread(require_public_addresses, host)
    return target


async def follow_public_chain(client: "httpx.AsyncClient", url: str, *, method: str = "GET"):
    """Walk the redirect chain by hand, clearing every hop before the connection is made.

    httpx's follow_redirects checks nothing, so by the time you inspect response.history the
    request to the internal address has already happened. Proven necessary on 2026-09-22: a
    public page that 302s to 127.0.0.1:3000 made the browser read Steel's own session list
    and hand it back as page content.
    """
    target = await safe_target(url)
    for _hop in range(MAX_HOPS):
        response = await client.request(method, target, follow_redirects=False)
        location = response.headers.get("location")
        if not (300 <= response.status_code < 400 and location):
            return response, target
        nxt = str(httpx.URL(target).join(location))
        try:
            target = await safe_target(nxt)
        except (UnsafeUrl, ValueError) as exc:
            raise UnsafeUrl(f"refused: {url} redirected to {nxt} — {exc}") from None
    raise UnsafeUrl(f"refused: {url} redirected more than {MAX_HOPS} times")


async def fetch(args: dict) -> dict:
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        try:
            response, final = await follow_public_chain(client, args["url"])
        except UnsafeUrl:
            _record("fetch", started, False, "refused: left the public web")
            raise
    body = response.text
    text = strip_html(body) if "html" in response.headers.get("content-type", "").lower() else body
    _record("fetch", started, True, f"{response.status_code}")
    return {"status_code": response.status_code, "final_url": final, **_bounded(text)}


async def read(args: dict) -> dict:
    started = time.monotonic()
    want_shot = bool(args.get("screenshot"))
    delay = args.get("delay_ms")
    # Resolve the redirect chain BEFORE the browser sees it, and hand Steel the cleared
    # final URL. Steel's metadata.urlSource echoes the request, so the browser's own
    # landing address is not observable from here; this is the only pre-flight there is.
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        try:
            _, url = await follow_public_chain(client, args["url"], method="HEAD")
        except UnsafeUrl:
            _record("read", started, False, "refused: left the public web")
            raise
        except httpx.HTTPError:
            # The site refused our pre-flight. We learned nothing, so fall back to the URL as
            # written — already validated — rather than failing a page that only talks to browsers.
            url = await safe_target(args["url"])
    async with lane(label=f"read {url[:60]}"):
        payload = await steel.scrape(url, delay=delay)
        # The screenshot is a separate navigation inside Chromium. It follows its own
        # redirects and Steel reports no landing URL, so the pre-flight above does not
        # reach it — verified 2026-09-22: /v1/screenshot photographed Steel's own API
        # through a redirect. The host egress rule is what covers this, not this code.
        # The picture is a second navigation that only the in-browser guard can vet.
        shot = await steel.screenshot(url, delay=delay) if want_shot and GUARD.up else None
    content = payload.get("content") or {}
    meta = payload.get("metadata") or {}
    text = content.get("markdown") or strip_html(content.get("html") or "")
    out: dict[str, Any] = {
        "title": meta.get("title"),
        "final_url": url,
        "status_code": meta.get("statusCode"),
        "links": [link.get("url") for link in (payload.get("links") or [])[:50] if link.get("url")],
        **_bounded(text or ""),
    }
    if want_shot and not shot:
        out["screenshot_note"] = ("withheld: the in-browser guard is not attached, and the screenshot is a second "
                                  "page load that only it can vet. status shows the guard.")
    if shot:
        out["screenshot_media_type"] = "image/jpeg"
        out["screenshot_bytes"] = len(shot)
        out["screenshot_base64"] = base64.b64encode(shot).decode()
    _record("read", started, True, str(out.get("status_code") or ""))
    return out


async def session(args: dict) -> dict:
    started = time.monotonic()
    action = args["action"]
    if action == "create":
        # Creating a session relaunches Steel's Chromium, killing whatever read or act is mid-step.
        async with lane(label="session create"):
            generation, guarded = GUARD.generation, GUARD.up
            created = await steel.create_session(timeout_seconds=int(args.get("timeout_seconds", 900)))
            # The relaunched browser is unguarded until the guard reattaches: hold the lane till then.
            reattached = await GUARD.reattached_after(generation) if guarded else False
        _record("session", started, True, "create")
        return {
            "session_id": created.get("id") or created.get("sessionId"),
            "status": created.get("status"),
            # The API image serves the DevTools inspector; sessionViewerUrl points at the
            # separate Steel UI image, which this box does not run. Report what exists.
            "devtools_url": created.get("debuggerUrl"),
            "cdp_url": steel.CDP,
            "guard_reattached": reattached,
            "note": (
                "Nothing here is published beyond loopback. To sign in by hand, tunnel first — "
                "ssh -L 3000:127.0.0.1:3000 <host> — then open devtools_url and log in once. "
                "Later read calls reuse the cookies until the session is released."
            ),
        }
    if action == "list":
        listed = await steel.sessions()
        rows = listed.get("sessions") if isinstance(listed, dict) else listed
        _record("session", started, True, "list")
        return {
            "sessions": [
                {
                    "session_id": row.get("id"),
                    "status": row.get("status"),
                    "created_at": row.get("createdAt"),
                    "duration_ms": row.get("duration"),
                }
                for row in (rows or [])
                if isinstance(row, dict)
            ]
        }
    async with lane(label="session release"):  # relaunches Chromium too
        generation, guarded = GUARD.generation, GUARD.up
        released = await steel.release_session(args.get("session_id"))
        reattached = await GUARD.reattached_after(generation) if guarded else False
    _record("session", started, True, "release")
    return {"released": True, "detail": released, "guard_reattached": reattached}


async def act(args: dict) -> dict:
    started = time.monotonic()
    given = [k for k in ("command", "pick", "confirm") if args.get(k) not in (None, "")]
    if len(given) != 1:
        raise ValueError("act takes exactly one of: command, pick (answering a clarification), confirm (answering a confirmation)")
    kind = given[0]
    async with lane(label=f"act {str(args[kind])[:50]}"):
        await GUARD.wait_ready()
        try:
            if kind == "command":
                raw = await jev.command(args["command"])
            elif kind == "pick":
                raw = await jev.pick(args["pick"])
            else:
                raw = await jev.confirm(bool(args["confirm"]))
        except jev.JevUnavailable:
            # A step still running inside Jev would otherwise go on holding the page.
            await jev.cancel()
            _record("act", started, False, "jev unavailable")
            raise
        out = jev.summarize(raw)
        if args.get("read_page") and out["status"] in ("done", "failed"):
            page = await jev.read(TEXT_LIMIT)
            if page is None:
                out["text_note"] = "this Jev build cannot read page text; call read on the url (a fresh load of it)"
            else:
                out.update(_bounded(page.get("text") or ""))
    _record("act", started, out["status"] == "done", out["status"])
    return out


def _need(args: dict, *names: str) -> None:
    missing = [n for n in names if args.get(n) in (None, "")]
    if missing:
        raise ValueError(f"action={args['action']} needs {', '.join(missing)}")


async def computer(args: dict) -> dict:
    started = time.monotonic()
    action = args["action"]
    cid, how = await orgo.resolve(args.get("computer_id"))
    screen = orgo.screen_id_or_raise(args.get("screen_id"))
    if screen and action in ("start", "stop", "bash"):
        raise ValueError(f"{action} is computer-wide; it cannot target one screen")
    out: dict[str, Any] = {"action": action, "computer_id": cid, "computer": how,
                           **({"screen_id": screen} if screen else {})}
    lane_name = f"computer-{cid}-screen-{screen}" if screen else f"computer-{cid}"
    async with lane(name=lane_name, label=f"computer {action}"):
        if action == "screenshot":
            shot = await orgo.screenshot(cid, screen_id=screen, context=bool(args.get("context")))
        else:
            if action == "click":
                _need(args, "x", "y")
                detail = await orgo.click(cid, args["x"], args["y"], button=args.get("button", "left"),
                                          double=bool(args.get("double")), screen_id=screen,
                                          context=bool(args.get("context")))
            elif action == "type":
                _need(args, "text")
                detail = await orgo.type_text(cid, args["text"], screen_id=screen,
                                              context=bool(args.get("context")))
            elif action == "key":
                _need(args, "key")
                detail = await orgo.press(cid, args["key"], screen_id=screen,
                                          context=bool(args.get("context")))
            elif action == "scroll":
                _need(args, "x", "y")
                detail = await orgo.scroll(cid, args["x"], args["y"], direction=args.get("direction", "down"),
                                           amount=args.get("amount", 3), screen_id=screen,
                                           context=bool(args.get("context")))
            elif action == "bash":
                _need(args, "command")
                detail = await orgo.bash(cid, args["command"])
                out["output"] = detail.get("output")
            elif action == "start":
                detail = await orgo.start(cid)
                out["note"] = "running — it bills until you call action=stop"
            else:
                detail = await orgo.stop(cid)
                out["note"] = "stopped (Orgo reports it as frozen); billing ends"
            out["ok"] = bool(detail.get("success", True)) if isinstance(detail, dict) else True
            shot = await orgo.screenshot(cid, screen_id=screen, context=bool(args.get("context"))) if args.get("screenshot_after") and action not in ("stop",) else None
            if args.get("context") and isinstance(detail, dict):
                out["context"] = detail.get("context")
    if shot and shot.get("image"):
        out.update(screenshot_base64=shot["image"], screenshot_media_type=shot["mime_type"],
                   screenshot_bytes=len(shot["image"]) * 3 // 4, width=shot.get("width"), height=shot.get("height"))
        if args.get("context"):
            out["context"] = shot.get("context")
    _record("computer", started, True, action)
    return out


async def task(args: dict) -> dict:
    available = task_surfaces()
    if args.get("cancel"):
        if args.get("goal"):
            raise ValueError("task takes a goal to start a task, or cancel=true to stop the running one, not both")
        if "browser" not in available:
            raise ValueError("cancel stops a browser task, and this box has no browser surface")
        return await _cancel_browser_task()
    if not args.get("goal"):
        raise ValueError("task needs a goal (or cancel=true to stop the running browser task)")
    surface = args.get("surface")
    if surface is None:
        if len(available) != 1:
            raise ValueError('task needs surface: "browser" (this box\'s browser) or "computer" (an Orgo desktop)')
        surface = available[0]
    if surface not in available:
        raise ValueError(f"surface={surface} is not configured on this box; it has: {', '.join(available) or 'none'}")
    return await (_browser_task(args) if surface == "browser" else _computer_task(args))


async def _computer_task(args: dict) -> dict:
    started = time.monotonic()
    goal = args["goal"]
    cid, how = await orgo.resolve(args.get("computer_id"))
    async with lane(name=f"computer-{cid}", label=f"task {goal[:40]}"):
        result = await orgo.agent(cid, goal, timeout_seconds=float(args.get("timeout_seconds", 600)))
    _record("task", started, result["status"] == "done", f"computer: {result['status']}")
    return {"surface": "computer", "computer_id": cid, "computer": how, **result}


async def _guard_lost(generation: int) -> None:
    while GUARD.up and GUARD.generation == generation:
        await asyncio.sleep(0.5)


async def _stop_browser_agent() -> Any:
    """Stop the agent and wait until it has: the browser lane must not be released while it is
    still driving the browser. Its /cancel call is bounded (30 s), so this cannot hold forever."""
    stopping = asyncio.ensure_future(browseruse.cancel())
    while not stopping.done():
        try:
            await asyncio.shield(stopping)
        except asyncio.CancelledError:
            continue
    return stopping.result()


async def _cancel_browser_task() -> dict:
    """No lane: the lane is exactly what the running task holds. The container answers once the
    agent is dead and its tabs are closed; the task's own call then returns and frees the lane."""
    started = time.monotonic()
    stopped = await browseruse.cancel()
    cancelled = bool(stopped and stopped.get("cancelled"))
    _record("task", started, cancelled, "browser: cancel")
    if stopped is None:
        return {"surface": "browser", "cancelled": False, "detail": "agent-browseruse did not answer; status shows it"}
    return {"surface": "browser", "cancelled": cancelled, "detail": stopped.get("detail") or
            "stopped; the task's own call answers with status cancelled and what it did"}


async def _browser_task(args: dict) -> dict:
    started = time.monotonic()
    goal = args["goal"]
    async with lane(label=f"task {goal[:40]}"):
        await GUARD.wait_ready()
        running = asyncio.create_task(browseruse.run(goal, int(args.get("max_steps", 25)), int(args.get("timeout_seconds", 300))))
        watching = asyncio.create_task(_guard_lost(GUARD.generation))
        try:
            done, _ = await asyncio.wait({running, watching}, return_when=asyncio.FIRST_COMPLETED)
            if running in done:
                result = running.result()
            else:
                # The guard fails open: an agent left running now would be browsing unguarded.
                # Stop it first; its own call then answers with what it did before it was stopped.
                await _stop_browser_agent()
                try:
                    result = await asyncio.wait_for(running, 30)
                except Exception:
                    result = {}
                result = {**result, "status": "stopped", "reason": "the in-browser guard detached mid-task, so the "
                          "task was stopped rather than left running unguarded; status shows the guard"}
        except BaseException:
            # The caller gave up (a cancelled tool call), the HTTP call timed out, or it failed:
            # whatever it was, the agent must be dead before this lane is released. Stop it before
            # dropping our own call to it, so the container is never left serving nobody.
            await _stop_browser_agent()
            running.cancel()
            _record("task", started, False, "browser: stopped")
            raise
        finally:
            watching.cancel()
    cost = result.get("estimated_cost_usd")
    _record("task", started, result.get("status") == "done", f"browser: {result.get('status')}", cost_usd=cost)
    return {"surface": "browser", **result}


TASK_SURFACES: dict[str, tuple[Any, str]] = {
    "browser": (browseruse.configured, (
        "surface=\"browser\": Browser-Use works the goal in this box's browser, with a model choosing each "
        "step (one model call per step; a few steps take ~10-40 s). It gets a tab of its own and never touches "
        "act's tab. Private and internal addresses are refused inside the browser. Its tab is closed when it "
        "finishes: to look at the last page again, read final_url. Returns status (done | failed | incomplete | "
        "timed_out | cancelled | stopped), answer, steps, urls, final_url, tokens and estimated_cost_usd.\n"
        "It holds the browser until it finishes, even if you stop waiting: this endpoint cannot hear a client give "
        "up. task(cancel=true) stops it, and the stopped task still reports what it did.")),
    "computer": (orgo.configured, (
        "surface=\"computer\": Orgo's hosted computer-use agent (Claude) works an Orgo desktop until the goal is "
        "done. Orgo ignores max_steps and caps its loop at 250 steps; timeout_seconds is the real bound, and "
        "hitting it aborts the run.")),
}


def task_surfaces() -> list[str]:
    return [name for name, (ready, _) in TASK_SURFACES.items() if ready()]


def _task_card(card: dict[str, Any]) -> dict[str, Any]:
    surfaces = task_surfaces()
    text = "\n".join(TASK_SURFACES[name][1] for name in surfaces)
    if len(surfaces) > 1:
        text += "\nsurface is required to start a task: this box has both."
    schema = {**card["inputSchema"], "properties": dict(card["inputSchema"]["properties"])}
    schema["properties"]["surface"] = {"type": "string", "enum": surfaces, **({"default": surfaces[0]} if len(surfaces) == 1 else {})}
    if "browser" not in surfaces:
        schema["properties"].pop("max_steps")
        schema["properties"].pop("cancel")
    if "computer" not in surfaces:
        schema["properties"].pop("computer_id")
    return {**card, "description": card["description"].replace("{surfaces}", text), "inputSchema": schema}


# Optional integrations and the check that decides whether they are listed at all.
OPTIONAL: dict[str, Any] = {"act": jev.configured, "computer": orgo.configured, "task": lambda: bool(task_surfaces())}


def offered_tools() -> list[dict[str, Any]]:
    return [_task_card(t) if t["name"] == "task" else t
            for t in TOOLS if t["name"] not in OPTIONAL or OPTIONAL[t["name"]]()]


async def status(_args: dict) -> dict:
    components: list[dict[str, Any]] = []
    try:
        components.append({"name": "steel (the browser)", "up": True, "detail": await steel.health()})
    except Exception as exc:
        components.append({"name": "steel (the browser)", "up": False, "detail": str(exc)[:200]})
    lane_free: bool | None = True
    lane_detail = "free"
    try:
        async with lane(wait_seconds=0, label="status probe"):
            pass
    except LaneBusy:
        lane_free, lane_detail = False, "busy — one browser runs at a time on this host"
    except OSError as exc:
        # status is the one tool that must never fail: it is what you call when
        # something else already did. A broken lock is reported, not raised.
        lane_free, lane_detail = None, f"unknown — the lane lock is unusable: {exc}"
    browser_up = components[0]["up"] and lane_free is not None

    unavailable: list[dict[str, str]] = []
    if not browser_up:
        why = "the browser is down: " + str(components[0]["detail"])[:120]
        unavailable += [{"tool": t, "reason": why} for t in ["read", "session"] + (["act"] if jev.configured() else [])]
        if browseruse.configured():
            unavailable.append({"tool": "task", "surface": "browser", "reason": why})
    components.append({"name": "guard (in-browser URL check)", "up": GUARD.up, "detail": GUARD.health()})
    if not GUARD.up:
        why = "the in-browser guard is not attached: " + str(GUARD.last_error)[:100]
        if jev.configured():
            unavailable.append({"tool": "act", "reason": why})
        if browseruse.configured():
            unavailable.append({"tool": "task", "surface": "browser", "reason": why})
    if jev.configured():
        try:
            detail = await jev.health()
            components.append({"name": "jev (act: step decisions)", "up": not detail["paused"], "detail": detail})
            if detail["paused"]:
                unavailable.append({"tool": "act", "reason": "agent-jev is paused"})
        except Exception as exc:
            components.append({"name": "jev (act: step decisions)", "up": False, "detail": str(exc)[:200]})
            unavailable.append({"tool": "act", "reason": "agent-jev is down: " + str(exc)[:120]})
    else:
        components.append({"name": "jev (act: step decisions)", "up": False, "configured": False,
                           "detail": "not configured — set BB_JEV_URL and BB_JEV_TOKEN to offer the act tool"})
    if browseruse.configured():
        try:
            detail = await browseruse.health()
            up = detail.pop("up")
            components.append({"name": "browser-use (task on the browser)", "up": up, "detail": detail})
            if not up:
                unavailable.append({"tool": "task", "surface": "browser", "reason": detail["problem"]})
        except Exception as exc:
            components.append({"name": "browser-use (task on the browser)", "up": False, "detail": str(exc)[:200]})
            unavailable.append({"tool": "task", "surface": "browser", "reason": "agent-browseruse is down: " + str(exc)[:120]})
    else:
        components.append({"name": "browser-use (task on the browser)", "up": False, "configured": False,
                           "detail": "not configured — add browseruse to COMPOSE_PROFILES and set BB_BROWSERUSE_URL, "
                                     "BB_BROWSERUSE_TOKEN and OPENROUTER_API_KEY to offer task(surface=\"browser\")"})
    if orgo.configured():
        try:
            components.append({"name": "orgo (computers, off-box)", "up": True, "detail": await orgo.health()})
        except Exception as exc:
            components.append({"name": "orgo (computers, off-box)", "up": False, "detail": str(exc)[:200]})
            why = "orgo is down: " + str(exc)[:120]
            unavailable += [{"tool": "computer", "reason": why}, {"tool": "task", "surface": "computer", "reason": why}]
    else:
        components.append({"name": "orgo (computers, off-box)", "up": False, "configured": False,
                           "detail": "not configured — set ORGO_API_KEY to offer the computer tool and task(surface=\"computer\")"})

    offered = [t["name"] for t in offered_tools()]
    # A tool is down when nothing of it works: task stays up while one of its surfaces does.
    down = {item["tool"] for item in unavailable if "surface" not in item}
    if "task" in offered and set(task_surfaces()) <= {i["surface"] for i in unavailable if i["tool"] == "task" and "surface" in i}:
        down.add("task")
    spent = [c["cost_usd"] for c in _CALLS if c.get("cost_usd") is not None]
    return {
        "components": components,
        "browser_lane": lane_detail,
        "tools_working_now": [t for t in offered if t not in down],
        "tools_unavailable": unavailable,
        "recent_calls": list(reversed(_CALLS[-10:])),
        **({"model_spend_recent_usd": round(sum(spent), 6)} if spent else {}),
    }


HANDLERS = {"fetch": fetch, "read": read, "session": session, "act": act, "computer": computer, "task": task, "status": status}
