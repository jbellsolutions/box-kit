"""The guard inside the browser: one CDP client that pauses every request Chromium makes and
refuses the ones that are not the public web.

The gateway's pre-flight only sees the URL it is asked to open. A click (act), a browser
agent's own navigation (task), a redirect inside Steel's screenshot load, a popup's first
request and an iframe all happen inside Chromium, where only a CDP client can see them.

It intercepts on the BROWSER target, not tab by tab. Per-tab interception was the first
design and it leaked: a tab created with its URL already given (Target.createTarget, which
any CDP client here may call) starts that request before any client can switch interception
on for the tab, and a redirect rides the request already in flight. Verified 2026-09-23: a new
tab opened on a public URL that 302s to 127.0.0.1:3000 loaded Steel's session list past the
per-tab guard on every try (5 of 5, with and without another client attached). With one
Fetch.enable on the browser target the same tab was refused, first hop and redirect both
seen. There is no attach race left to win: interception is on for every tab, frame and
dedicated worker from the moment this client connects.

Service and shared workers are the exception: they run as targets of their own, and the
browser-level interceptor does not see their requests (verified: it never saw one of Steel's
recorder posts, which per-target interception had been refusing all along). So those two kinds
are also auto-attached, held with waitForDebuggerOnStart before their first line runs, and
intercepted on their own session.

Steel's own recorder extension posts session events from its background worker to Steel's API
on localhost. That is refused like any other request inward (this box does not run Steel's
replay viewer, and an exemption would give pages a write path into Steel through the
extension's messaging). Posts to that endpoint are counted apart so they cannot bury the rest.

It fails OPEN while detached: Chrome drops a departed client's interception and releases what
it held (verified: a held request loaded the moment the guard's socket closed). So the tools
that navigate on their own wait for it and refuse without it, and status reports it apart.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
import time
from typing import Any
from urllib.parse import urlsplit

from websockets.asyncio.client import connect

from . import steel
from .security import UnsafeUrl, require_public_addresses, target_scope

log = logging.getLogger("gateway.guard")

READY_WAIT = 15.0
DECIDE_TIMEOUT = 5.0
CALL_TIMEOUT = 15.0
HEARTBEAT = 15.0
DNS_TTL = 60.0
# Schemes that never leave the browser. chrome-extension is Steel's own recorder.
LOCAL_SCHEMES = frozenset({"data", "blob", "about", "chrome", "chrome-extension", "chrome-untrusted", "devtools"})
FETCH_ALL = {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]}
# Only the workers that run as their own targets; pages, frames and dedicated workers are
# already covered by the browser-level interceptor, and holding them too would only add a round trip.
AUTO_ATTACH = {"autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True,
               "filter": [{"type": "service_worker", "exclude": False},
                          {"type": "shared_worker", "exclude": False},
                          {"exclude": True}]}


def _steel_events(url: str) -> bool:
    """Steel's recorder endpoint on this host: the extension posts there on every page event."""
    parts = urlsplit(url)
    return parts.port == 3000 and parts.path.startswith("/v1/events") and \
        (parts.hostname or "") in ("localhost", "127.0.0.1", "0.0.0.0", "::1")


class GuardDown(RuntimeError):
    """The in-browser guard is not attached; a tool that navigates on its own must not run."""


class CdpError(RuntimeError):
    pass


async def dialable(cdp_url: str) -> str:
    """Chromium's DevTools endpoint refuses a Host header that is neither an IP nor localhost,
    and Steel passes ours through, so a compose name like ws://steel:3000/ is dialled by IP."""
    parts = urlsplit(cdp_url)
    host = parts.hostname or ""
    try:
        ipaddress.ip_address(host)
        return cdp_url
    except ValueError:
        if host == "localhost":
            return cdp_url
    infos = await asyncio.to_thread(socket.getaddrinfo, host, parts.port, socket.AF_INET, socket.SOCK_STREAM)
    address = infos[0][4][0]
    netloc = f"{address}:{parts.port}" if parts.port else address
    return parts._replace(netloc=netloc).geturl()


class Guard:
    def __init__(self, cdp_url: str | None = None) -> None:
        self.cdp_url = cdp_url or steel.CDP
        self.generation = 0
        self.since: float | None = None
        self.last_error: str | None = "not started"
        self.counts = {"allowed": 0, "refused": 0, "refused_steel_events": 0, "workers_watched": 0}
        self.refusals: list[dict[str, Any]] = []
        self._attached = asyncio.Event()
        self._ws: Any = None
        self._ids = 0
        self._waiters: dict[int, asyncio.Future] = {}
        self._send_lock = asyncio.Lock()
        self._dns: dict[str, tuple[float, str | None]] = {}
        self._tasks: set[asyncio.Task] = set()
        self._runner: asyncio.Task | None = None

    # ── lifecycle ────────────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._runner is None:
            self._runner = asyncio.create_task(self._run(), name="browser-guard")

    async def stop(self) -> None:
        if self._runner:
            self._runner.cancel()
            await asyncio.gather(self._runner, return_exceptions=True)
            self._runner = None

    @property
    def up(self) -> bool:
        return self._attached.is_set()

    async def wait_ready(self, timeout: float | None = None) -> None:
        try:
            await asyncio.wait_for(self._attached.wait(), READY_WAIT if timeout is None else timeout)
        except TimeoutError:
            raise GuardDown(
                f"the in-browser guard is not attached ({self.last_error or 'still connecting'}), so tools that "
                "navigate on their own are refused until it is. status shows it."
            ) from None

    async def reattached_after(self, generation: int, timeout: float | None = None) -> bool:
        """After a Steel relaunch: wait until the guard is attached to the NEW browser."""
        deadline = time.monotonic() + (READY_WAIT if timeout is None else timeout)
        while time.monotonic() < deadline:
            if self.up and self.generation > generation:
                return True
            await asyncio.sleep(0.2)
        return False

    def health(self) -> dict[str, Any]:
        return {
            "attached": self.up,
            "attached_for_seconds": round(time.time() - self.since) if self.since else None,
            **self.counts,
            "recent_refusals": self.refusals[-5:],
            **({"last_error": self.last_error} if not self.up and self.last_error else {}),
        }

    async def _run(self) -> None:
        delay = 0.5
        while True:
            try:
                await self._session()
                delay = 0.5
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"[:200]
                log.warning("browser guard detached: %s", self.last_error)
            finally:
                self._attached.clear()
                self.since = None
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5.0)

    async def _session(self) -> None:
        # max_size=None: a page chooses how big a paused request's URL is, and an oversize frame
        # would otherwise close this socket, which is exactly how to switch the guard off.
        # No protocol pings: liveness is checked with a real CDP call below instead.
        async with connect(await dialable(self.cdp_url), max_size=None, ping_interval=None,
                           compression=None, open_timeout=10) as ws:
            self._ws = ws
            reader = asyncio.create_task(self._read(ws))
            try:
                # No sessionId: the browser target. Every request in every tab, frame and worker,
                # including a tab whose first request is already on its way, is paused here.
                await self._call("Fetch.enable", FETCH_ALL)
                await self._call("Target.setAutoAttach", AUTO_ATTACH)
                self.generation += 1
                self.since = time.time()
                self.last_error = None
                self._attached.set()
                log.info("browser guard attached (generation %d)", self.generation)
                while True:
                    done, _ = await asyncio.wait({reader}, timeout=HEARTBEAT)
                    if done:
                        reader.result()
                        raise CdpError("the browser closed the connection")
                    await self._call("Browser.getVersion")
            finally:
                self._attached.clear()
                reader.cancel()
                self._ws = None

    # ── CDP plumbing ─────────────────────────────────────────────────────────────────
    async def _read(self, ws: Any) -> None:
        try:
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message:
                    waiter = self._waiters.get(message["id"])
                    if waiter and not waiter.done():
                        if "error" in message:
                            waiter.set_exception(CdpError(message["error"].get("message", "CDP error")))
                        else:
                            waiter.set_result(message.get("result") or {})
                    continue
                method = message.get("method")
                if method == "Fetch.requestPaused":
                    self._spawn(self._on_paused(message.get("sessionId"), message["params"]))
                elif method == "Target.attachedToTarget":
                    self._spawn(self._on_worker(message["params"]))
        finally:
            # Detached means unguarded: say so at once, not at the next heartbeat.
            self._attached.clear()
            for waiter in self._waiters.values():
                if not waiter.done():
                    waiter.set_exception(CdpError("the guard's connection closed"))

    def _spawn(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _call(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        ws = self._ws
        if ws is None:
            raise CdpError("not connected")
        self._ids += 1
        mid = self._ids
        waiter = asyncio.get_running_loop().create_future()
        self._waiters[mid] = waiter
        message: dict[str, Any] = {"id": mid, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        try:
            async with self._send_lock:
                await ws.send(json.dumps(message))
            return await asyncio.wait_for(waiter, CALL_TIMEOUT)
        finally:
            self._waiters.pop(mid, None)

    # ── the guard itself ─────────────────────────────────────────────────────────────
    async def _on_worker(self, params: dict) -> None:
        """A service or shared worker, held before its first line runs: intercept, then let it go."""
        session = params["sessionId"]
        info = params.get("targetInfo") or {}
        try:
            await self._call("Fetch.enable", FETCH_ALL, session)
        except Exception as exc:  # a timeout too: nothing may run unwatched
            log.warning("guard could not watch a %s (%s); closing it", info.get("type"), exc)
            try:
                await self._call("Target.closeTarget", {"targetId": info.get("targetId")})
            except Exception:
                pass
            return
        self.counts["workers_watched"] += 1
        try:
            await self._call("Runtime.runIfWaitingForDebugger", {}, session)
        except Exception:
            pass

    async def _on_paused(self, session: str | None, params: dict) -> None:
        request_id = params["requestId"]
        url = (params.get("request") or {}).get("url", "")
        try:
            refusal = await asyncio.wait_for(self.verdict(url), DECIDE_TIMEOUT)
        except Exception as exc:
            # A check that cannot finish is a refusal, never a pass and never a request left hanging.
            refusal = f"could not be checked ({type(exc).__name__})"
        try:
            if refusal is None:
                self.counts["allowed"] += 1
                await self._call("Fetch.continueRequest", {"requestId": request_id}, session)
            elif _steel_events(url):
                self.counts["refused_steel_events"] += 1
                await self._call("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"}, session)
            else:
                self.counts["refused"] += 1
                self.refusals.append({"url": url[:160], "why": refusal[:160], "kind": params.get("resourceType"), "at": time.time()})
                del self.refusals[:-20]
                await self._call("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"}, session)
        except Exception:
            pass  # the tab went away while we decided, or the connection did

    async def verdict(self, url: str) -> str | None:
        """None to allow, or why not. The same classifier as every other check in this box."""
        parts = urlsplit(url)
        if parts.scheme.lower() in LOCAL_SCHEMES:
            return None
        scope = target_scope(url)
        if scope != "public_web":
            return f"{scope} target"
        host = (parts.hostname or "").lower().rstrip(".")
        hit = self._dns.get(host)
        if hit and time.monotonic() - hit[0] < DNS_TTL:
            return hit[1]
        try:
            await asyncio.to_thread(require_public_addresses, host)
            refusal = None
        except UnsafeUrl as exc:
            refusal = str(exc)
        if len(self._dns) > 4096:
            self._dns.clear()
        self._dns[host] = (time.monotonic(), refusal)
        return refusal


GUARD = Guard()
