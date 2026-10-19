"""Browsers a caller keeps for a while: fresh, clean, and forgotten when they close.

A session here is a handle on one hosted browser that stays open between calls, so act can work a
page step by step and several agents can each have their own. It is never a login store: no profile
is ever created, opened or touched (cloud.py refuses the profiles API outright). Logged-in work
belongs to tools built for it, on their own profiles, never here.

Rules kept here:
- one open browser per session; each session has its own lock, and there is no lock across sessions;
- a session's browser closes after ``BB_SESSION_IDLE_SECONDS`` of no use (default 300), and then the
  session is gone: the next call with its id is refused, a new one starts clean;
- the live-view URL lets anyone holding it drive the browser: it is returned only to the caller.

The ``default`` session is act's scratch browser when no session_id is given.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .cdp import Cdp
from .cloud import BrowserUseCloud, CloudUnavailable

log = logging.getLogger("gateway.sessions")

DEFAULT = "default"


@dataclass
class Held:
    session_id: str
    name: str = ""
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    stack: contextlib.AsyncExitStack | None = None
    cdp: Cdp | None = None
    page: str | None = None
    live_url: str | None = None
    browser_id: str | None = None
    engine: str | None = None            # browseruse, or browserbase when it fell back
    last_used: float = 0.0
    pending: dict | None = None          # act's question waiting for an answer

    @property
    def open(self) -> bool:
        return self.stack is not None


class Sessions:
    def __init__(self, cloud: BrowserUseCloud, fallback: Any = None):
        self.cloud = cloud
        self.fallback = fallback        # Browserbase: the emergency browser when Browser Use cannot open one
        self.items: dict[str, Held] = {DEFAULT: Held(DEFAULT, "scratch")}
        self.idle_seconds = float(os.getenv("BB_SESSION_IDLE_SECONDS", "300"))
        self.hold_minutes = int(os.getenv("BB_SESSION_MAX_MINUTES", "60"))
        self._reaper: asyncio.Task | None = None

    def create(self, name: str | None = None) -> Held:
        held = Held(uuid.uuid4().hex[:16], (name or "")[:80])
        self.items[held.session_id] = held
        return held

    def get(self, session_id: str | None) -> Held:
        held = self.items.get(session_id or DEFAULT)
        if held is None:
            raise ValueError(f"no session {session_id}: it was released or closed when idle. "
                             "Start a new one with session(action=\"create\") (it starts clean)")
        return held

    def listing(self) -> list[dict[str, Any]]:
        return [{"session_id": h.session_id, "name": h.name, "browser_open": h.open, "engine": h.engine}
                for h in self.items.values() if h.session_id != DEFAULT or h.open]

    # ── the one browser per session ─────────────────────────────────────────────────────────
    async def ensure_open(self, held: Held) -> Held:
        """Call with held.lock taken. Opens the session's browser if it is not open."""
        if held.open and held.cdp is not None and not held.cdp.reader.done():
            held.last_used = time.monotonic()
            return held
        if held.open:
            await self._close(held)            # the connection died under us: start clean
        stack = contextlib.AsyncExitStack()
        try:
            try:
                cdp, info = await stack.enter_async_context(self.cloud.browser(minutes=self.hold_minutes))
                held.engine = "browseruse"
            except CloudUnavailable as exc:
                if self.fallback is None:
                    raise
                log.warning("Browser Use could not open a browser (%s); using Browserbase", exc)
                cdp, info = await stack.enter_async_context(self.fallback.browser(minutes=self.hold_minutes))
                held.engine = "browserbase"
            held.page = await cdp.page()
        except BaseException:
            await stack.aclose()
            raise
        held.stack, held.cdp, held.live_url, held.browser_id = stack, cdp, info.get("live_url"), info.get("session_id")
        held.last_used = time.monotonic()
        self._start_reaper()
        return held

    async def release(self, session_id: str | None) -> bool:
        held = self.get(session_id)
        async with held.lock:
            was_open = held.open
            await self._close(held)
        if held.session_id != DEFAULT:
            self.items.pop(held.session_id, None)
        return was_open

    async def _close(self, held: Held) -> None:
        stack = held.stack
        held.stack = held.cdp = held.page = held.live_url = held.browser_id = held.engine = None
        held.pending = None
        if stack is not None:
            try:
                await stack.aclose()           # stops the hosted browser
            except Exception as exc:
                log.warning("closing a session browser failed (%s); its own timeout will end it", type(exc).__name__)

    def _start_reaper(self) -> None:
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.get_running_loop().create_task(self._reap(), name="session-reaper")

    async def _reap(self) -> None:
        while any(h.open for h in self.items.values()):
            await asyncio.sleep(min(30.0, self.idle_seconds / 2))
            now = time.monotonic()
            for held in list(self.items.values()):
                if held.open and now - held.last_used > self.idle_seconds and not held.lock.locked():
                    async with held.lock:
                        if now - held.last_used > self.idle_seconds:
                            await self._close(held)
                    if held.session_id != DEFAULT:
                        self.items.pop(held.session_id, None)

    async def close_all(self) -> None:
        for held in list(self.items.values()):
            await self._close(held)
