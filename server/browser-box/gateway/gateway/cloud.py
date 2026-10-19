"""Browser Use Cloud: the box's default browser engine. A fresh hosted Chromium per call, driven over CDP.

Why it replaced Steel (measured 2026-10-12, bench/): Steel serves one browser per server; Browser Use
runs many at once (the plan's own ceiling, 10 at $0 spend, 50 after $100) at $0.02 per browser-hour
billed by the minute.

**Fresh, clean browsers only.** This box never sends a ``profileId`` and never calls the profiles API.
Other tools keep logged-in profiles on Browser Use; nothing here can open, change or
delete one, whatever it is tagged. The only browsers this box ever stops are ones it created itself,
recorded by id in ``BB_OWNED_BROWSERS`` the moment Browser Use answers.

Rules this module keeps, each learned on the live API:

- every browser is stopped with ``PATCH {"action": "stop"}`` in ``finally``. Closing the websocket
  does NOT stop it, and a lost one bills until its ``timeout``;
- ``timeout`` is small (``BB_BROWSERUSE_SESSION_MINUTES``, default 5): the whole timeout is charged
  up front and refunded pro rata when the browser stops;
- ``proxyCountryCode`` is sent as null: their default is "us", a residential proxy billed per GB.
  A proxy is used only when a caller's identity names one;
- ``solveCaptchas`` follows ``BB_SOLVE_CAPTCHAS`` (default on);
- every browser carries ``metadata`` ``owner=browser-box`` (for spend accounting only), and browsers
  left running by a crash are stopped when the gateway starts (``stop_strays``) by their recorded id,
  never by searching the account;
- how many run at once is the plan's ``concurrentSessionLimit``, read from the account and never
  more than ``BB_BROWSERUSE_MAX_CONCURRENT``. That is the plan's limit, not a lock of ours;
- spend is capped box-side too: ``BB_BROWSERUSE_MONTHLY_USD`` (default 10) against what Browser Use
  itself reports for this month's browser-box browsers, plus a minimum wallet balance.

The CDP URL Browser Use returns is an https DevTools base; the websocket comes from its
``/json/version``. Neither it nor the key is ever logged or returned.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import urlsplit

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .cdp import Cdp, CdpError
from .security import UnsafeUrl, require_public_addresses, require_public_web, target_scope

API = "https://api.browser-use.com/api"
OWNER = {"owner": "browser-box"}
MAX_TEXT = 100_000
USD_PER_HOUR = 0.02
OWNED = os.getenv("BB_OWNED_BROWSERS", "/tmp/browser-box/owned-browsers.json")


def solve_captchas() -> bool:
    return os.getenv("BB_SOLVE_CAPTCHAS", "1").strip().lower() not in ("0", "false", "no", "off")
MIN_BALANCE_USD = 0.02


class CloudUnavailable(RuntimeError):
    """Not configured, over a cap, out of credit, or Browser Use refused. Never holds a key or a CDP URL."""


Connect = Callable[[str], Any]


class BrowserUseCloud:
    def __init__(self, api_key: str, *, monthly_usd: float = 10.0, max_concurrent: int = 10,
                 session_minutes: int = 5, transport: httpx.AsyncBaseTransport | None = None,
                 cdp_connect: Connect | None = None, owned_path: str | None = None):
        if not api_key:
            raise ValueError("api_key is required")
        self._key = api_key
        self.owned_path = owned_path or os.getenv("BB_OWNED_BROWSERS") or OWNED
        self.monthly_usd = float(monthly_usd)
        self.max_concurrent = max(1, int(max_concurrent))
        self.session_minutes = min(240, max(1, int(session_minutes)))
        self._transport = transport
        self._connect = cdp_connect or (lambda url: connect(url, max_size=32 * 1024 * 1024, open_timeout=60))
        self.running = 0
        self.reads = 0
        self.last_error: str | None = None
        self._account: tuple[float, dict | None] = (0.0, None)
        self._month: tuple[float, float | None] = (0.0, None)

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "BrowserUseCloud | None":
        key = (env.get("BROWSER_USE_API_KEY") or "").strip()
        if not key:
            return None
        return cls(key, monthly_usd=float(env.get("BB_BROWSERUSE_MONTHLY_USD") or 10),
                   max_concurrent=int(env.get("BB_BROWSERUSE_MAX_CONCURRENT") or 10),
                   session_minutes=int(env.get("BB_BROWSERUSE_SESSION_MINUTES") or 5))

    # ── REST ────────────────────────────────────────────────────────────────────────────────
    async def _api(self, method: str, path: str, body: dict | None = None, params: dict | None = None) -> Any:
        if "profile" in path.lower():
            # Logged-in profiles belong to other tools on this account. This box has no reason to
            # read, open, change or delete one, so the call is refused before it is made.
            raise CloudUnavailable("browser-box never touches Browser Use profiles")
        try:
            async with httpx.AsyncClient(timeout=60.0, transport=self._transport) as client:
                response = await client.request(method, f"{API}{path}", json=body, params=params,
                                                headers={"X-Browser-Use-API-Key": self._key})
        except httpx.HTTPError as exc:
            raise CloudUnavailable(f"Browser Use is unreachable ({type(exc).__name__})") from None
        if response.status_code == 401:
            raise CloudUnavailable("Browser Use refused the API key (BROWSER_USE_API_KEY)")
        if response.status_code == 402:
            raise CloudUnavailable("Browser Use is out of credit; top up the account")
        if response.status_code == 429:
            raise CloudUnavailable("Browser Use is at its concurrency or rate limit for this plan; try again shortly")
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail") or ""
            except ValueError:
                detail = ""
            raise CloudUnavailable(f"Browser Use returned {response.status_code} on {method} {path.split('/')[2]}"
                                   + (f": {str(detail)[:200]}" if detail else ""))
        return response.json() if response.content else None

    async def account(self, *, fresh: bool = False) -> dict:
        fetched, value = self._account
        if fresh or value is None or time.monotonic() - fetched > 60:
            value = await self._api("GET", "/v2/billing/account")
            self._account = (time.monotonic(), value)
        return value

    async def ceiling(self) -> int:
        """The plan's own concurrency (``concurrentSessionLimit``), never more than our cap."""
        try:
            plan = int((await self.account()).get("concurrentSessionLimit") or 0)
        except (CloudUnavailable, TypeError, ValueError):
            plan = 0
        return min(self.max_concurrent, plan) if plan else self.max_concurrent

    async def month_spend(self) -> float:
        """What Browser Use reports for this month's browser-box browsers (browser + proxy), cached 5 min."""
        fetched, value = self._month
        if value is not None and time.monotonic() - fetched < 300:
            return value
        start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total, page = 0.0, 1
        while page <= 50:
            listing = await self._api("GET", "/v4/browsers", params={"metadata": "owner=browser-box",
                                                                     "pageSize": 100, "pageNumber": page})
            items = listing.get("items") or []
            older = False
            for item in items:
                started = _when(item.get("startedAt"))
                if started and started < start:
                    older = True
                    continue
                total += float(item.get("browserCost") or 0) + float(item.get("proxyCost") or 0)
            if older or len(items) < 100:
                break
            page += 1
        self._month = (time.monotonic(), total)
        return total

    async def _admit(self) -> None:
        limit = await self.ceiling()
        if self.running >= limit:
            raise CloudUnavailable(f"all {limit} Browser Use browsers are in use (the plan's limit); try again shortly")
        account = await self.account()
        if float(account.get("totalCreditsBalanceUsd") or 0) < MIN_BALANCE_USD:
            raise CloudUnavailable("Browser Use is out of credit; top up the account")
        spent = await self.month_spend()
        if spent + self.running * self.session_minutes * USD_PER_HOUR / 60 >= self.monthly_usd:
            raise CloudUnavailable(f"this month's Browser Use cap is reached (${self.monthly_usd:g}, "
                                   "BB_BROWSERUSE_MONTHLY_USD); raise it only on purpose")

    @contextlib.asynccontextmanager
    async def hosted(self, *, proxy: dict | None = None,
                     minutes: int | None = None) -> AsyncIterator[tuple[str, dict]]:
        """One hosted browser for someone else to drive (the task agent), stopped on the way out
        whatever happens. Yields (websocket URL, info). The URL is a credential: never log it."""
        await self._admit()
        self.running += 1
        session_id = None
        try:
            body: dict[str, Any] = {"timeout": minutes or self.session_minutes, "proxyCountryCode": None,
                                    "solveCaptchas": solve_captchas(), "metadata": OWNER}
            if proxy:
                body["customProxy"] = proxy
            made = await self._api("POST", "/v4/browsers", body)
            session_id = made["id"]
            self._own(session_id)
            yield await self._websocket(made.get("cdpUrl") or ""), {"session_id": session_id, "live_url": made.get("liveUrl")}
        except CloudUnavailable as exc:
            self.last_error = str(exc)
            raise
        finally:
            self.running -= 1
            self._account = (0.0, None)
            if session_id:
                await self._stop(session_id)

    @contextlib.asynccontextmanager
    async def browser(self, *, proxy: dict | None = None,
                      minutes: int | None = None) -> AsyncIterator[tuple[Cdp, dict]]:
        """One hosted browser, stopped on the way out whatever happens. Yields (cdp, info)."""
        await self._admit()
        self.running += 1  # taken before the next await, so two calls cannot both get the last slot
        session_id = None
        try:
            body: dict[str, Any] = {"timeout": minutes or self.session_minutes, "proxyCountryCode": None,
                                    "solveCaptchas": solve_captchas(), "metadata": OWNER}
            if proxy:
                body["customProxy"] = proxy
            made = await self._api("POST", "/v4/browsers", body)
            session_id = made["id"]
            self._own(session_id)
            ws = await self._websocket(made.get("cdpUrl") or "")
            try:
                async with self._connect(ws) as sock:
                    cdp = Cdp(sock)
                    try:
                        yield cdp, {"session_id": session_id, "live_url": made.get("liveUrl")}
                    finally:
                        cdp.close()
            except (OSError, WebSocketException, asyncio.TimeoutError) as exc:
                raise CloudUnavailable(f"the Browser Use browser connection failed ({type(exc).__name__})") from None
        except CloudUnavailable as exc:
            self.last_error = str(exc)
            raise
        finally:
            self.running -= 1
            self._account = (0.0, None)
            if session_id:
                await self._stop(session_id)

    async def _websocket(self, cdp_url: str) -> str:
        if cdp_url.startswith(("ws://", "wss://")):
            return cdp_url
        if not cdp_url.startswith("https://"):
            raise CloudUnavailable("Browser Use returned no CDP address")
        try:
            async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
                return (await client.get(f"{cdp_url.rstrip('/')}/json/version")).json()["webSocketDebuggerUrl"]
        except (httpx.HTTPError, ValueError, KeyError):
            raise CloudUnavailable("the Browser Use browser did not answer on its DevTools address") from None

    async def _stop(self, session_id: str) -> None:
        try:
            await self._api("PATCH", f"/v4/browsers/{session_id}", {"action": "stop"})
        except CloudUnavailable:
            pass  # its own timeout ends it; a failed stop must not mask the call's result
        self._disown(session_id)

    # The ids of browsers this box created and has not stopped yet. A file, so a restarted gateway
    # stops exactly its own leftovers and nothing else on the account.
    def _owned(self) -> set[str]:
        try:
            with open(self.owned_path) as fh:
                return set(json.load(fh))
        except (OSError, ValueError, TypeError):
            return set()

    def _write_owned(self, ids: set[str]) -> None:
        try:
            os.makedirs(os.path.dirname(self.owned_path) or ".", exist_ok=True)
            tmp = self.owned_path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(sorted(ids), fh)
            os.replace(tmp, self.owned_path)
        except OSError:
            pass  # losing the record only means a crashed browser runs to its own (short) timeout

    def _own(self, session_id: str) -> None:
        self._write_owned(self._owned() | {session_id})

    def _disown(self, session_id: str) -> None:
        self._write_owned(self._owned() - {session_id})

    async def stop_strays(self) -> int:
        """Stop browsers this box created and a crash left running, by recorded id only. The account is
        never searched: a browser some other tool tagged like ours is never touched. Never raises."""
        owned = self._owned()
        for session_id in owned:
            await self._stop(session_id)
        return len(owned)

    # ── read ────────────────────────────────────────────────────────────────────────────────
    async def read(self, url: str, *, screenshot: bool = False, delay_ms: int = 0) -> dict:
        url = require_public_web(url)
        await asyncio.to_thread(require_public_addresses, urlsplit(url).hostname)
        started = time.monotonic()
        async with self.browser() as (cdp, info):
            try:
                page = await cdp.open_and_read(url, delay_ms=delay_ms, screenshot=screenshot)
            except CdpError as exc:
                self.last_error = str(exc)
                raise CloudUnavailable(f"Browser Use: {exc}") from None
        self.reads += 1
        final = page.get("url") or url
        if target_scope(final) != "public_web":
            raise UnsafeUrl(f"refused: the page ended at {final}, which is not the public web")
        text = page.get("text") or ""
        return {"engine": "browseruse", "url": url, "final_url": final, "title": page.get("title") or "",
                "status_code": page.get("status_code"), "links": list(page.get("links") or [])[:50],
                "text": text[:MAX_TEXT], "truncated": len(text) > MAX_TEXT, "screenshot": page.get("screenshot"),
                "seconds": round(time.monotonic() - started, 1), "session_id": info["session_id"]}

    async def status(self) -> dict:
        """For `status`. Never raises."""
        row: dict[str, Any] = {"configured": True, "running": self.running, "reads": self.reads,
                               "role": "the default browser engine: a hosted Chromium per call",
                               "monthly_cap_usd": self.monthly_usd}
        try:
            account = await self.account(fresh=True)
            row.update(at_once=await self.ceiling(), balance_usd=round(float(account.get("totalCreditsBalanceUsd") or 0), 4),
                       month_spend_usd=round(await self.month_spend(), 4), up=True)
            if row["balance_usd"] < MIN_BALANCE_USD:
                row.update(up=False, reason="out of credit")
        except CloudUnavailable as exc:
            row.update(up=False, reason=str(exc))
        if self.last_error:
            row["last_error"] = self.last_error
        return row


def _when(stamp: Any) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)
