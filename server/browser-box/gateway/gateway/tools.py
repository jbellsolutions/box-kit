"""The tools. If one is listed it works; if it cannot work right now, `status` says why.

The browsers are hosted: Browser Use Cloud runs them (a browser per read, task or session, many at
once), Browserbase is read's fallback. This host runs no Chromium and holds no browser lock.

Two rules decide what is listed. fetch and status are always listed. Everything else is listed
only when what it needs is configured: read with a hosted browser engine, session with Browser Use,
act with Browser Use and a decision model (Jev), task per surface, computer with Orgo. A box without
an Orgo key has no computers, and advertising one would be the exact lie this repo exists to stop.

There is deliberately no provider catalog, no readiness walkthrough, no plan/verify/resume
and no doctor variants. That surface is what made the previous system unusable: 29 tools
of which 22 could not reach a browser.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import time
from typing import Any

import httpx

from . import browseruse, decide, orgo, stepper
from .cdp import PAGE_JS, CdpError
from .sessions import DEFAULT as DEFAULT_SESSION, Held, Sessions
from .lock import lane
from . import browserbase as bbase
from . import cloud as bucloud
from .security import UnsafeUrl, require_public_addresses, require_public_web, target_scope

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
            "Each read gets its own hosted browser (Browser Use Cloud, when status shows it), so reads run side by "
            "side up to the plan's limit; there is no queue on this host. If that browser fails or the site blocks "
            "it, engine=\"auto\" falls back to Browserbase when configured; the result's engine and fallback_reason "
            "say which ran and why. Reads are public and logged out: never for a page that needs a session.\n"
            "The screenshot is of the same page load the text came from. Ask for it when the picture is the evidence.\n"
            "Returns: text, title, links, status_code, and screenshot_base64 (JPEG) when asked for."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Public http(s) URL"},
                "screenshot": {"type": "boolean", "description": "Also return a full-page JPEG of the page that was read.", "default": False},
                "delay_ms": {"type": "integer", "minimum": 0, "maximum": 15000, "description": "Wait this long after load for late content."},
                "engine": {"type": "string", "enum": ["auto", "browseruse", "browserbase"], "default": "auto",
                           "description": "auto: Browser Use Cloud, then Browserbase as the fallback when it is configured. "
                                          "browseruse: Browser Use only. browserbase: go straight to Browserbase (paid hours; "
                                          "public, logged-out pages only)."},
                "session_id": {"type": "string", "description": "Read in this session's browser, in a tab of its own (act's "
                               "tab is left where it was). Hosted engine only"},
                "region": {"type": "string", "enum": list(bbase.REGIONS),
                           "description": "Browserbase only: read the page from this region. Implies engine=browserbase."},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    },
    {
        "name": "session",
        "description": (
            "A browser of your own that stays open between calls, so act can work a page step by step and "
            "several agents can each drive their own at the same time. Every session starts fresh and clean, "
            "logged out, and is forgotten when it closes: this box keeps no logins and never uses a saved profile.\n"
            "create  -> a new session with its browser open: returns session_id and live_url (a view of that browser).\n"
            "list    -> the sessions open now.\n"
            "release -> close the session's browser; the session is gone. An idle session closes itself after a few "
            "minutes.\n"
            "Calls on one session_id wait for each other; different sessions run side by side. live_url lets whoever "
            "holds it drive that browser: keep it to yourself.\n"
            "Do NOT create a session for a one-off read: read opens and closes its own browser. Do NOT use this for "
            "logged-in work: it has no logins, by design."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create", "list", "release"]},
                "session_id": {"type": "string", "description": "release: the session to close; without it, act's scratch browser"},
                "name": {"type": "string", "maxLength": 80, "description": "create only: a label for your own bookkeeping"},
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
            "or read is cheaper. The tab stays where you left it between calls. Give session_id to use a browser of your "
            "own (see session); without it act uses one shared scratch browser that closes after a few idle minutes. "
            "Every browser is fresh and logged out.\n"
            "Private and internal addresses are refused: every URL is checked before it opens, and a step that lands off "
            "the public web is undone and reported as refused.\n"
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
                "session_id": {"type": "string", "description": "Work in this session's browser (see session). Without it, "
                               "act uses one shared scratch browser, fresh and forgotten when it closes"},
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


# Signs a bot wall answered instead of the page. Short pages only: a long article that mentions
# "captcha" is a page, not a wall.
BLOCK_STATUSES = {403, 429, 503}
BLOCK_MARKERS = ("just a moment", "attention required", "access denied", "verify you are human", "are you a robot",
                 "captcha", "enable javascript and cookies", "request unsuccessful", "pardon our interruption",
                 "checking your browser", "unusual traffic")
_BB: dict[str, Any] = {}
_BU: dict[str, Any] = {}


def cloud_client() -> "bucloud.BrowserUseCloud | None":
    """The Browser Use Cloud client for the key in the environment, or None. One per key, so its caps hold."""
    key = os.getenv("BROWSER_USE_API_KEY", "").strip()
    if not key:
        return None
    if _BU.get("key") != key:
        _BU.update(key=key, client=bucloud.BrowserUseCloud.from_env())
    return _BU["client"]


def browserbase_client() -> "bbase.Browserbase | None":
    """The Browserbase client for the key in the environment, or None. One per key, so its caps hold."""
    key = os.getenv("BROWSERBASE_API_KEY", "").strip()
    if not key:
        return None
    if _BB.get("key") != key:
        _BB.update(key=key, client=bbase.Browserbase.from_env())
    return _BB["client"]


def looks_blocked(status_code: Any, text: str) -> bool:
    if status_code in BLOCK_STATUSES:
        return True
    head = (text or "")[:2000].lower()
    return len(text or "") < 2000 and any(marker in head for marker in BLOCK_MARKERS)


async def _read_on_browserbase(client: "bbase.Browserbase", url: str, reason: str, region: str | None, started: float,
                               *, want_shot: bool, engine_error: str | None = None) -> dict:
    try:
        page = await client.read(url, reason=reason, region=region)
    except bbase.BrowserbaseUnavailable as exc:
        _record("read", started, False, f"browserbase: {str(exc)[:80]}")
        raise bbase.BrowserbaseUnavailable(f"{engine_error}; the Browserbase fallback also failed: {exc}" if engine_error else str(exc)) from None
    out: dict[str, Any] = {
        "title": page["title"], "final_url": page["final_url"], "status_code": None, "links": page["links"],
        **_bounded(page["text"]),
        "engine": "browserbase", "fallback_reason": reason, "why": page["why"], "region": page["region"],
        "browserbase_seconds": page["seconds"],
    }
    if engine_error:
        out["engine_error"] = engine_error
    if want_shot:
        out["screenshot_note"] = "not taken: Browserbase reads return text and links only"
    _record("read", started, True, f"browserbase ({reason})")
    return out


async def read(args: dict) -> dict:
    started = time.monotonic()
    region = args.get("region")
    engine = "browserbase" if region else (args.get("engine") or "auto")
    if engine not in ("auto", "browseruse", "browserbase"):
        raise ValueError("engine must be auto, browseruse or browserbase")
    if args.get("session_id"):
        store = sessions_store()
        if store is None or engine not in ("auto", "browseruse"):
            raise ValueError("session_id reads need Browser Use Cloud (BROWSER_USE_API_KEY) and engine auto or browseruse")
        return await _read_in_session(store, args, started)
    client = browserbase_client() if engine in ("auto", "browserbase") else None
    cloud = cloud_client() if engine in ("auto", "browseruse") else None
    if engine == "browseruse" and cloud is None:
        raise bucloud.CloudUnavailable("Browser Use is not configured on this box (BROWSER_USE_API_KEY is unset)")
    if cloud is not None:
        return await _read_on_cloud(cloud, client, args, started)
    if engine == "browserbase" and client is None:
        raise bbase.BrowserbaseUnavailable("Browserbase is not configured on this box (BROWSERBASE_API_KEY is unset); "
                                           "use engine=\"auto\"")
    if client is None:
        raise bucloud.CloudUnavailable("no browser engine is configured: set BROWSER_USE_API_KEY (or BROWSERBASE_API_KEY)")
    url = await safe_target(args["url"])
    reason = "region" if region else "requested" if engine == "browserbase" else "no_browser_use"
    return await _read_on_browserbase(client, url, reason, region, started, want_shot=bool(args.get("screenshot")))


async def _read_on_cloud(cloud: "bucloud.BrowserUseCloud", client: "bbase.Browserbase | None", args: dict,
                         started: float) -> dict:
    want_shot = bool(args.get("screenshot"))
    url = await safe_target(args["url"])
    try:
        page = await cloud.read(url, screenshot=want_shot, delay_ms=int(args.get("delay_ms") or 0))
    except bucloud.CloudUnavailable as exc:
        if client is None:
            _record("read", started, False, f"browseruse: {str(exc)[:80]}")
            raise
        return await _read_on_browserbase(client, url, "engine_down", None, started, want_shot=want_shot,
                                          engine_error=f"Browser Use: {exc}")
    shot = page.pop("screenshot", None)
    out: dict[str, Any] = {"title": page["title"], "final_url": page["final_url"], "status_code": page["status_code"],
                           "links": page["links"], **_bounded(page["text"]), "engine": "browseruse",
                           "browser_seconds": page["seconds"]}
    if shot:
        out["screenshot_media_type"] = "image/jpeg"
        out["screenshot_bytes"] = len(shot)
        out["screenshot_base64"] = base64.b64encode(shot).decode()
    if client is not None and looks_blocked(out.get("status_code"), out.get("text") or ""):
        try:
            return await _read_on_browserbase(client, out["final_url"], "blocked", None, started, want_shot=want_shot)
        except bbase.BrowserbaseUnavailable as exc:
            out["fallback_error"] = f"the page looked blocked and the Browserbase fallback failed: {exc}"
    _record("read", started, True, f"browseruse {out.get('status_code') or ''}".strip())
    return out


async def _read_in_session(store: Sessions, args: dict, started: float) -> dict:
    url = await safe_target(args["url"])
    held = store.get(args["session_id"])
    want_shot = bool(args.get("screenshot"))
    async with holding(held):
        await store.ensure_open(held)
        cdp = held.cdp
        try:
            target = (await cdp.send("Target.createTarget", {"url": "about:blank"}))["targetId"]
            try:
                tab = (await cdp.send("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]
                page = await cdp.open_and_read(url, delay_ms=int(args.get("delay_ms") or 0), screenshot=want_shot, session=tab)
            finally:
                with contextlib.suppress(Exception):
                    await cdp.send("Target.closeTarget", {"targetId": target})
        except CdpError as exc:
            await store._close(held)
            _record("read", started, False, "session browser lost")
            raise bucloud.CloudUnavailable(f"the session's browser stopped ({exc}); call read again") from None
        held.last_used = time.monotonic()
    if page.get("url") and not page["url"].startswith("about:") and target_scope(page["url"]) != "public_web":
        raise UnsafeUrl("the page led off the public web")
    shot = page.pop("screenshot", None)
    out: dict[str, Any] = {"title": page.get("title"), "final_url": page.get("url"), "status_code": page.get("status_code"),
                           "links": page.get("links") or [], **_bounded(page.get("text") or ""), "engine": "browseruse",
                           "session_id": held.session_id}
    if shot:
        out.update(screenshot_media_type="image/jpeg", screenshot_bytes=len(shot), screenshot_base64=base64.b64encode(shot).decode())
    _record("read", started, True, f"session {out.get('status_code') or ''}".strip())
    return out


_SESSIONS: dict[str, Any] = {}
SESSION_WAIT = float(os.getenv("BB_SESSION_WAIT_SECONDS", "30"))


def sessions_store() -> Sessions | None:
    """Sessions live on Browser Use Cloud when it is configured; one store per client."""
    cloud = cloud_client()
    if cloud is None:
        return None
    bb = browserbase_client()
    if _SESSIONS.get("cloud") is not cloud or _SESSIONS.get("bb") is not bb:
        _SESSIONS.update(cloud=cloud, bb=bb, store=Sessions(cloud, fallback=bb))
    return _SESSIONS["store"]


def hosted_act() -> bool:
    return cloud_client() is not None and decide.configured()


@contextlib.asynccontextmanager
async def holding(held: Held):
    """A session's lock, waited for briefly: a long task on the session answers busy rather than hanging the caller."""
    try:
        await asyncio.wait_for(held.lock.acquire(), SESSION_WAIT)
    except asyncio.TimeoutError:
        raise ValueError(f"session {held.session_id} is busy (another call is using its browser); try again shortly") from None
    try:
        yield held
    finally:
        held.lock.release()


async def _session_hosted(store: Sessions, args: dict, started: float) -> dict:
    action = args["action"]
    if action == "create":
        held = store.create(args.get("name"))
        try:
            async with holding(held):
                await store.ensure_open(held)
        except BaseException:
            store.items.pop(held.session_id, None)
            raise
        _record("session", started, True, "create")
        return {"session_id": held.session_id, "name": held.name, "live_url": held.live_url, "engine": held.engine,
                "note": "A fresh, logged-out browser. Pass this session_id to act and read; release it when done."}
    if action == "list":
        _record("session", started, True, "list")
        return {"sessions": store.listing()}
    held = store.get(args.get("session_id"))
    if held.lock.locked():
        await asyncio.wait_for(held.lock.acquire(), SESSION_WAIT)
        held.lock.release()
    was_open = await store.release(held.session_id)
    _record("session", started, True, "release")
    return {"released": True, "session_id": held.session_id, "was_open": was_open}


async def session(args: dict) -> dict:
    started = time.monotonic()
    action = args["action"]
    store = sessions_store()
    if store is not None:
        return await _session_hosted(store, args, started)
    raise bucloud.CloudUnavailable("sessions run on Browser Use Cloud: set BROWSER_USE_API_KEY")


async def act(args: dict) -> dict:
    started = time.monotonic()
    given = [k for k in ("command", "pick", "confirm") if args.get(k) not in (None, "")]
    if len(given) != 1:
        raise ValueError("act takes exactly one of: command, pick (answering a clarification), confirm (answering a confirmation)")
    kind = given[0]
    if hosted_act():
        return await _act_hosted(sessions_store(), args, kind, started)
    raise decide.DecisionUnavailable("act needs Browser Use Cloud and a decision model: set BROWSER_USE_API_KEY and "
                                     "TYPESAFE_API_KEY")


async def _act_hosted(store: Sessions, args: dict, kind: str, started: float) -> dict:
    """act on the session's hosted browser: Jev picks each element, the box does it over CDP."""
    held = store.get(args.get("session_id"))
    async with holding(held):
        pending = held.pending
        if kind == "command":
            steps, pending, held.pending = stepper.split_steps(args["command"]), None, None
        else:
            if not pending:
                raise ValueError("nothing is waiting for an answer on this session: send a command")
            if time.monotonic() - pending["at"] > stepper.PENDING_SECONDS:
                held.pending = None
                raise ValueError("that question expired; send the command again")
            wanted = "pick" if pending["kind"] == "clarify" else "confirm"
            if kind != wanted:
                raise ValueError(f"the waiting question is answered with {wanted}")
            steps = []
        await store.ensure_open(held)
        engine = stepper.Stepper(held.cdp, held.page, check_url=safe_target)
        try:
            out, held.pending = await engine.run(steps, pending=pending, pick=args.get("pick"), confirm=args.get("confirm"))
            if args.get("read_page") and out["status"] in ("done", "failed"):
                page = await held.cdp.send("Runtime.evaluate", {"expression": PAGE_JS, "returnByValue": True}, session=held.page)
                out.update(_bounded(json.loads(page["result"]["value"]).get("text") or ""))
        except CdpError as exc:
            # The hosted browser went away under us (its own timeout, or the network): start clean next call.
            await store._close(held)
            _record("act", started, False, "browser lost")
            raise bucloud.CloudUnavailable(f"the session's browser stopped ({exc}); call act again to open a fresh one") from None
        held.last_used = time.monotonic()
        out.update(session_id=held.session_id, engine=held.engine or "browseruse", live_url=held.live_url)
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


async def _cancel_browser_task() -> dict:
    """Stops every browser task this box is running. Each task's own call then answers with status
    cancelled and what it did, and its hosted browser is stopped."""
    started = time.monotonic()
    stopped = await browseruse.cancel()
    cancelled = bool(stopped and stopped.get("cancelled"))
    _record("task", started, cancelled, "browser: cancel")
    if stopped is None:
        return {"surface": "browser", "cancelled": False, "detail": "agent-browseruse did not answer; status shows it"}
    return {"surface": "browser", "cancelled": cancelled, "detail": stopped.get("detail") or
            "stopped; the task's own call answers with status cancelled and what it did"}


async def _browser_task(args: dict) -> dict:
    cloud = cloud_client()
    if cloud is not None:
        return await _browser_task_hosted(cloud, args)
    raise bucloud.CloudUnavailable("browser tasks run on Browser Use Cloud: set BROWSER_USE_API_KEY")


async def _browser_task_hosted(cloud: "bucloud.BrowserUseCloud", args: dict) -> dict:
    """The task gets a hosted browser of its own: no lane, no shared tab, nothing to guard on this host.
    Tasks run side by side up to the agent's BU_PARALLEL and the plan's browser ceiling."""
    import uuid
    started = time.monotonic()
    timeout = int(args.get("timeout_seconds", 300))
    task_id = uuid.uuid4().hex[:12]
    minutes = timeout // 60 + 2
    engine, fallback_error = "browseruse", None
    try:
        async with contextlib.AsyncExitStack() as stack:
            try:
                ws, info = await stack.enter_async_context(cloud.hosted(minutes=minutes))
            except bucloud.CloudUnavailable as exc:
                # Emergency lane: Browser Use could not open a browser, so the task runs on Browserbase.
                bb = browserbase_client()
                if bb is None:
                    raise
                engine, fallback_error = "browserbase", str(exc)
                ws, info = await stack.enter_async_context(bb.hosted(minutes=minutes))
            try:
                result = await browseruse.run(args["goal"], int(args.get("max_steps", 25)), timeout,
                                              cdp_url=ws, task_id=task_id)
            except BaseException:
                # The caller gave up or the call failed: the agent must be dead before its browser is stopped.
                await browseruse.cancel(task_id)
                raise
    except BaseException:
        _record("task", started, False, "browser: stopped")
        raise
    result.pop("tabs_closed", None)
    cost = result.get("estimated_cost_usd")
    _record("task", started, result.get("status") == "done", f"browser: {result.get('status')}", cost_usd=cost)
    return {"surface": "browser", "engine": engine, **({"fallback_reason": fallback_error} if fallback_error else {}), **result}


TASK_SURFACES: dict[str, tuple[Any, str]] = {
    "browser": (lambda: browseruse.configured() and cloud_client() is not None, (
        "surface=\"browser\": Browser-Use works the goal in a hosted browser of its own, with a model choosing each "
        "step (one model call per step; a few steps take ~10-40 s). Several tasks run side by side, each in "
        "a fresh, logged-out browser. Its browser is stopped when it finishes: to look at the last page again, read "
        "final_url. Returns status (done | failed | incomplete | timed_out | cancelled | stopped), answer, steps, "
        "urls, final_url, tokens and estimated_cost_usd.\n"
        "It runs until it finishes even if you stop waiting: this endpoint cannot hear a client give up. "
        "task(cancel=true) stops every running browser task, and each still reports what it did.")),
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
OPTIONAL: dict[str, Any] = {
    "read": lambda: cloud_client() is not None or browserbase_client() is not None,
    "session": lambda: cloud_client() is not None,
    "act": hosted_act,
    "computer": orgo.configured,
    "task": lambda: bool(task_surfaces()),
}


def offered_tools() -> list[dict[str, Any]]:
    return [_task_card(t) if t["name"] == "task" else t
            for t in TOOLS if t["name"] not in OPTIONAL or OPTIONAL[t["name"]]()]


async def status(_args: dict) -> dict:
    components: list[dict[str, Any]] = []
    unavailable: list[dict[str, str]] = []
    cloud, cloud_up = cloud_client(), False
    if cloud is not None:
        row = await cloud.status()
        cloud_up = row.pop("up")
        components.append({"name": "browser-use cloud (the browsers)", "up": cloud_up, "detail": row})
        if not cloud_up:
            why = "Browser Use Cloud is not usable: " + str(row.get("problem") or row)[:120]
            unavailable += [{"tool": t, "reason": why} for t in ("session", "act")]
            unavailable.append({"tool": "task", "surface": "browser", "reason": why})
    else:
        components.append({"name": "browser-use cloud (the browsers)", "up": False, "configured": False,
                           "detail": "not configured — set BROWSER_USE_API_KEY: read, session, act and task run on its browsers"})
    client, base_up = browserbase_client(), False
    if client is not None:
        row = await client.status()
        base_up = row.pop("up")
        components.append({"name": "browserbase (the emergency lane)", "up": base_up, "detail": row})
    else:
        components.append({"name": "browserbase (the emergency lane)", "up": False, "configured": False,
                           "detail": "not configured — set BROWSERBASE_API_KEY so read, act and task have an emergency browser when Browser Use cannot serve"})
    if (cloud is not None or client is not None) and not (cloud_up or base_up):
        unavailable.append({"tool": "read", "reason": "no hosted browser engine is usable right now"})
    if decide.configured():
        components.append({"name": "decision model (act: which element)", "up": True,
                           "detail": {"url": os.getenv("BB_DECISION_URL") or decide.URL,
                                      "model": os.getenv("BB_DECISION_MODEL") or "jev-latest"}})
    else:
        components.append({"name": "decision model (act: which element)", "up": False, "configured": False,
                           "detail": "not configured — set TYPESAFE_API_KEY (with BROWSER_USE_API_KEY) to offer act"})
    if browseruse.configured():
        try:
            detail = await browseruse.health()
            up = detail.pop("up")
            components.append({"name": "browser-use agent (task on the browser)", "up": up, "detail": detail})
            if not up:
                unavailable.append({"tool": "task", "surface": "browser", "reason": detail["problem"]})
        except Exception as exc:
            components.append({"name": "browser-use agent (task on the browser)", "up": False, "detail": str(exc)[:200]})
            unavailable.append({"tool": "task", "surface": "browser", "reason": "agent-browseruse is down: " + str(exc)[:120]})
    else:
        components.append({"name": "browser-use agent (task on the browser)", "up": False, "configured": False,
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
    unavailable = [u for u in unavailable if u["tool"] in offered]
    # A tool is down when nothing of it works: task stays up while one of its surfaces does.
    down = {item["tool"] for item in unavailable if "surface" not in item}
    if "task" in offered and set(task_surfaces()) <= {i["surface"] for i in unavailable if i["tool"] == "task" and "surface" in i}:
        down.add("task")
    spent = [c["cost_usd"] for c in _CALLS if c.get("cost_usd") is not None]
    return {
        "components": components,
        "tools_working_now": [t for t in offered if t not in down],
        "tools_unavailable": unavailable,
        "recent_calls": list(reversed(_CALLS[-10:])),
        **({"model_spend_recent_usd": round(sum(spent), 6)} if spent else {}),
    }


HANDLERS = {"fetch": fetch, "read": read, "session": session, "act": act, "computer": computer, "task": task, "status": status}
