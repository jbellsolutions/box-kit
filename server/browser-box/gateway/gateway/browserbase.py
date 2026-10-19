"""Browserbase: the last rung. A second hosted browser for a public, logged-out read.

Browser Use Cloud comes first, every time. This module is for the cases where it cannot serve:

- ``engine_down``: Browser Use failed or is unavailable (out of credit, at its cap, an outage);
- ``blocked``: Browser Use's browser was refused by the site (a bot wall, not a login wall);
- ``no_browser_use``: this box has no Browser Use key, so Browserbase is the only engine;
- ``region``: the page has to be seen from one of Browserbase's regions;
- ``requested``: the caller asked for Browserbase by name (``read(engine="browserbase")``).

It is also the emergency browser for act's scratch browser and for task, when Browser Use cannot
open one (``browser`` and ``hosted`` below). Every browser, here and on Browser Use, is fresh and
logged out: this box keeps no logins.

What it never does:

- log in, carry cookies or reuse a session. Every read is a fresh session with no context, released
  in ``finally``. This box does no logged-in work anywhere;
- spend past its caps. ``BB_BROWSERBASE_MONTHLY_HOURS`` (default 100, the $20 Developer plan) is
  checked against Browserbase's own usage count for the project (``browserMinutes`` from
  ``/v1/projects/{id}/usage``) before each session, counting the sessions already running, and the
  read is refused when the cap is reached or the usage cannot be read. The API does not say whether
  that count resets each billing period; confirm it at the first live test. ``BB_BROWSERBASE_MAX_CONCURRENT``
  (default 25, the Developer plan's own ceiling; this is the plan's limit, not ours) bounds the sessions this gateway holds at once, and each session is
  created with a ``timeout`` (``BB_BROWSERBASE_TIMEOUT``, default 120 s) so a lost one stops billing.

The browser runs on Browserbase's machines, so it cannot reach services beside this box. The URL is
still checked as every other tool checks it, and a page that lands somewhere non-public is dropped.

Keys: ``BROWSERBASE_API_KEY`` (required), ``BROWSERBASE_PROJECT_ID`` (optional when the key has exactly
one project). Neither is ever returned, logged or put in an error.
"""
from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import os
import time
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import urlsplit

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .cloud import solve_captchas
from .security import UnsafeUrl, require_public_addresses, require_public_web, target_scope

API = "https://api.browserbase.com/v1"
REASONS = {
    "engine_down": "Browser Use failed or is unavailable",
    "blocked": "Browser Use's browser was refused by the site",
    "no_browser_use": "this box has no Browser Use key",
    "region": "the page had to be seen from a Browserbase region",
    "requested": "the caller asked for Browserbase",
}
REGIONS = ("us-west-2", "us-east-1", "eu-central-1", "ap-southeast-1")
MAX_TEXT = 100_000
LOAD_WAIT = 30.0


class BrowserbaseUnavailable(RuntimeError):
    """Not configured, over a cap, or Browserbase refused. The message says which, and never holds a key."""


Connect = Callable[[str], Any]


class Browserbase:
    def __init__(self, api_key: str, *, project_id: str | None = None, monthly_hours: float = 100.0,
                 max_concurrent: int = 25, timeout_s: int = 120,
                 transport: httpx.AsyncBaseTransport | None = None, cdp_connect: Connect | None = None):
        if not api_key:
            raise ValueError("api_key is required")
        self._key = api_key
        self._project = project_id or None
        self.monthly_hours = float(monthly_hours)
        self.max_concurrent = max(1, int(max_concurrent))
        self.timeout_s = max(60, int(timeout_s))
        self._transport = transport
        self._connect = cdp_connect or (lambda url: connect(url, max_size=32 * 1024 * 1024))
        self.running = 0
        self._plan_ceiling: tuple[float, int | None] = (0.0, None)
        self.reads = 0
        self.last_error: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Browserbase | None":
        key = (env.get("BROWSERBASE_API_KEY") or "").strip()
        if not key:
            return None
        return cls(key, project_id=(env.get("BROWSERBASE_PROJECT_ID") or "").strip() or None,
                   monthly_hours=float(env.get("BB_BROWSERBASE_MONTHLY_HOURS") or 100),
                   max_concurrent=int(env.get("BB_BROWSERBASE_MAX_CONCURRENT") or 25),
                   timeout_s=int(env.get("BB_BROWSERBASE_TIMEOUT") or 120))

    # ── REST ────────────────────────────────────────────────────────────────────────────────
    async def _api(self, method: str, path: str, body: dict | None = None) -> Any:
        try:
            async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
                response = await client.request(method, f"{API}{path}", json=body,
                                                headers={"X-BB-API-Key": self._key})
        except httpx.HTTPError as exc:
            raise BrowserbaseUnavailable(f"Browserbase is unreachable ({type(exc).__name__})") from None
        if response.status_code == 401:
            raise BrowserbaseUnavailable("Browserbase refused the API key (BROWSERBASE_API_KEY)")
        if response.status_code == 429:
            raise BrowserbaseUnavailable("Browserbase is at its concurrency limit for this plan; try again shortly")
        if response.status_code >= 400:
            try:
                detail = response.json().get("message") or response.json().get("error") or ""
            except ValueError:
                detail = ""
            raise BrowserbaseUnavailable(f"Browserbase returned {response.status_code} on {method} {path.split('/')[1]}"
                                         + (f": {str(detail)[:200]}" if detail else ""))
        return response.json() if response.content else None

    async def project_id(self) -> str:
        if self._project:
            return self._project
        projects = await self._api("GET", "/projects") or []
        if len(projects) != 1:
            raise BrowserbaseUnavailable(f"the key has {len(projects)} projects; set BROWSERBASE_PROJECT_ID to choose one")
        self._project = projects[0]["id"]
        return self._project

    async def ceiling(self) -> int:
        """How many sessions may run at once: the project's own concurrency as Browserbase reports it
        (the plan's real ceiling, e.g. 3 on Free, 25 on Developer), never more than our cap. Read, not
        assumed; cached for 5 minutes. If it cannot be read, our cap stands and Browserbase's own 429
        is the backstop."""
        fetched, value = self._plan_ceiling
        if value is None or time.monotonic() - fetched > 300:
            try:
                value = int((await self._api("GET", f"/projects/{await self.project_id()}")).get("concurrency") or 0) or None
            except (BrowserbaseUnavailable, TypeError, ValueError):
                value = None
            self._plan_ceiling = (time.monotonic(), value)
        return min(self.max_concurrent, value) if value else self.max_concurrent

    async def usage(self) -> dict:
        minutes = (await self._api("GET", f"/projects/{await self.project_id()}/usage"))["browserMinutes"]
        return {"hours_used": round(minutes / 60, 2), "hours_cap": self.monthly_hours,
                "minutes_left": max(0, int(self.monthly_hours * 60 - minutes))}

    async def status(self) -> dict:
        """For `status`. Never raises."""
        row: dict[str, Any] = {"configured": True, "running": self.running, "max_concurrent": self.max_concurrent,
                               "reads": self.reads, "role": "last rung: public, logged-out reads only"}
        try:
            row["at_once"] = await self.ceiling()
            if self._plan_ceiling[1]:
                row["plan_concurrency"] = self._plan_ceiling[1]
            row.update(await self.usage())
            row["up"] = True
        except BrowserbaseUnavailable as exc:
            row.update(up=False, reason=str(exc))
        if self.last_error:
            row["last_error"] = self.last_error
        return row

    # ── read ────────────────────────────────────────────────────────────────────────────────
    async def read(self, url: str, *, reason: str, region: str | None = None) -> dict:
        if reason not in REASONS:
            raise ValueError(f"reason must be one of {', '.join(REASONS)}: Browserbase is the last rung, not a default")
        if region is not None and region not in REGIONS:
            raise ValueError(f"region must be one of {', '.join(REGIONS)}")
        if reason == "region" and region is None:
            raise ValueError("reason 'region' needs a region")
        url = require_public_web(url)
        await asyncio.to_thread(require_public_addresses, urlsplit(url).hostname)

        started = time.monotonic()
        async with self._session(region=region) as session:
            page = await self._load(session["connectUrl"], url)
            session_id = session["id"]
        self.reads += 1
        final = page.get("url") or url
        if target_scope(final) != "public_web":
            raise UnsafeUrl(f"refused: the page ended at {final}, which is not the public web")
        text = page.get("text") or ""
        return {"engine": "browserbase", "reason": reason, "why": REASONS[reason], "region": region or "us-west-2",
                "url": url, "final_url": final, "title": page.get("title") or "", "links": list(page.get("links") or [])[:50],
                "text": text[:MAX_TEXT], "truncated": len(text) > MAX_TEXT,
                "seconds": round(time.monotonic() - started, 1), "session_id": session_id}

    @contextlib.asynccontextmanager
    async def _session(self, *, region: str | None = None, timeout_s: int | None = None) -> AsyncIterator[dict]:
        """One fresh, logged-out session inside the caps, released on the way out whatever happens."""
        timeout_s = timeout_s or self.timeout_s
        limit = await self.ceiling()
        if self.running >= limit:
            raise BrowserbaseUnavailable(f"all {limit} Browserbase sessions are in use"
                                         + (" (the Browserbase project's own limit; raise it with the plan)"
                                            if limit < self.max_concurrent else ""))
        self.running += 1  # taken before the next await, so two calls cannot both get the last slot
        session_id = None
        try:
            # Other sessions already running may each bill up to their timeout before Browserbase counts them.
            left = (await self.usage())["minutes_left"] - (self.running - 1) * self.timeout_s / 60
            if left < timeout_s / 60:
                raise BrowserbaseUnavailable(f"Browserbase hours for the month are used up ({self.monthly_hours:g} h cap); "
                                             "raise BB_BROWSERBASE_MONTHLY_HOURS only on purpose")
            body: dict[str, Any] = {"projectId": await self.project_id(), "keepAlive": False, "timeout": timeout_s,
                                    "browserSettings": {"solveCaptchas": solve_captchas(), "recordSession": False}}
            if region:
                body["region"] = region
            session = await self._api("POST", "/sessions", body)
            session_id = session["id"]
            yield session
        except BrowserbaseUnavailable as exc:
            self.last_error = str(exc)
            raise
        finally:
            self.running -= 1
            if session_id:
                await self._release(session_id)

    @contextlib.asynccontextmanager
    async def hosted(self, *, minutes: int | None = None) -> AsyncIterator[tuple[str, dict]]:
        """Emergency browser for someone else to drive (the task agent). Yields (connect URL, info).
        The URL is a credential: never log it."""
        async with self._session(timeout_s=(minutes or 5) * 60) as session:
            yield session["connectUrl"], {"session_id": session["id"], "live_url": None, "engine": "browserbase"}

    @contextlib.asynccontextmanager
    async def browser(self, *, minutes: int | None = None) -> AsyncIterator[tuple[Any, dict]]:
        """Emergency browser the gateway drives itself (act's scratch browser). Yields (cdp, info)."""
        from .cdp import Cdp
        async with self._session(timeout_s=(minutes or 5) * 60) as session:
            try:
                async with self._connect(session["connectUrl"]) as sock:
                    cdp = Cdp(sock)
                    try:
                        yield cdp, {"session_id": session["id"], "live_url": None, "engine": "browserbase"}
                    finally:
                        cdp.close()
            except (OSError, WebSocketException, asyncio.TimeoutError) as exc:
                raise BrowserbaseUnavailable(f"the Browserbase browser connection failed ({type(exc).__name__})") from None

    async def _release(self, session_id: str) -> None:
        try:
            await self._api("POST", f"/sessions/{session_id}",
                            {"projectId": await self.project_id(), "status": "REQUEST_RELEASE"})
        except BrowserbaseUnavailable:
            pass  # the session's own timeout ends it; a failed release must not mask the read's result

    async def _load(self, connect_url: str, url: str) -> dict:
        try:
            async with self._connect(connect_url) as ws:
                cdp = _Cdp(ws)
                try:
                    return await self._navigate(cdp, url)
                finally:
                    cdp.reader.cancel()
        except BrowserbaseUnavailable:
            raise
        except (OSError, WebSocketException, asyncio.TimeoutError, KeyError, ValueError) as exc:
            raise BrowserbaseUnavailable(f"the Browserbase browser connection failed ({type(exc).__name__})") from None

    async def _navigate(self, cdp: "_Cdp", url: str) -> dict:
        targets = (await cdp.send("Target.getTargets"))["targetInfos"]
        pages = [t for t in targets if t.get("type") == "page"]
        target = pages[0]["targetId"] if pages else (await cdp.send("Target.createTarget", {"url": "about:blank"}))["targetId"]
        sid = (await cdp.send("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]
        await cdp.send("Page.enable", session=sid)
        loaded = cdp.expect("Page.loadEventFired", sid)
        nav = await cdp.send("Page.navigate", {"url": url}, session=sid)
        if nav.get("errorText"):
            raise BrowserbaseUnavailable(f"the page did not open on Browserbase: {nav['errorText']}")
        try:
            await asyncio.wait_for(loaded, LOAD_WAIT)
        except asyncio.TimeoutError:
            pass  # read what rendered; a slow subresource should not lose the page
        out = await cdp.send("Runtime.evaluate", {
            "expression": "JSON.stringify({url: location.href, title: document.title, "
                          "text: document.body ? document.body.innerText : '', "
                          "links: Array.from(document.links, a => a.href).filter(h => /^https?:/.test(h)).slice(0, 50)})",
            "returnByValue": True}, session=sid)
        return json.loads(out["result"]["value"])


class _Cdp:
    """Just enough CDP over one websocket: numbered calls and one awaited event."""

    def __init__(self, ws: Any):
        self.ws = ws
        self.ids = itertools.count(1)
        self.waiting: dict[int, asyncio.Future] = {}
        self.events: list[tuple[str, str | None, asyncio.Future]] = []
        self.reader = asyncio.ensure_future(self._read())

    async def _read(self) -> None:
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in self.waiting:
                    self.waiting.pop(msg["id"]).set_result(msg)
                elif "method" in msg:
                    for name, sid, fut in list(self.events):
                        if name == msg["method"] and sid == msg.get("sessionId") and not fut.done():
                            fut.set_result(msg.get("params", {}))
        finally:
            for fut in self.waiting.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("CDP connection closed"))

    def expect(self, method: str, session: str | None) -> asyncio.Future:
        fut = asyncio.get_running_loop().create_future()
        self.events.append((method, session, fut))
        return fut

    async def send(self, method: str, params: dict | None = None, *, session: str | None = None) -> dict:
        call_id = next(self.ids)
        fut = asyncio.get_running_loop().create_future()
        self.waiting[call_id] = fut
        msg: dict[str, Any] = {"id": call_id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        try:
            await self.ws.send(json.dumps(msg))
            reply = await asyncio.wait_for(fut, LOAD_WAIT)
        finally:
            self.waiting.pop(call_id, None)
        if "error" in reply:
            raise BrowserbaseUnavailable(f"Browserbase's browser refused {method}: {reply['error'].get('message', '')[:200]}")
        return reply.get("result", {})

