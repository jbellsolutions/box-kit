"""Cross-process single-flight lock for browser work.

One Chromium, one job at a time. This has to be a filesystem lock rather than an
asyncio primitive because the contenders live in different processes and different
containers: the gateway, and each agent job.

Super Browser recorded the failure this prevents. `scripts/talk_super_browser.py`
carries the note that concurrent Browser-Use runs produced "attached to a different
loop", "Root CDP client not initialized", a dead CDP websocket and a 30s
BrowserStartEvent stall, and the flat comment: local Chromium isn't concurrency-safe
(proven 2026-08-14).
"""
from __future__ import annotations

import asyncio
import errno
import fcntl
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

LOCK_PATH = Path(os.getenv("BB_LANE_LOCK", "/tmp/browser-box/lane.lock"))
WAIT_SECONDS = float(os.getenv("BB_LANE_WAIT_SECONDS", "120"))
POLL_SECONDS = 0.25


class LaneBusy(RuntimeError):
    """Another browser job holds the lane and did not finish within the wait budget."""


def _path(name: str | None) -> Path:
    """The browser lane is LOCK_PATH itself; any other named lane sits beside it.

    Separate lanes are separate resources: an Orgo computer is its own desktop, so driving
    it must not block the browser, but two jobs on the SAME computer would fight over its
    mouse exactly the way two jobs on one Chromium fight over CDP.
    """
    if not name:
        return LOCK_PATH
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)[:120]
    return LOCK_PATH.parent / f"{safe}.lock"


@asynccontextmanager
async def lane(wait_seconds: float | None = None, *, label: str = "job", name: str | None = None):
    """Hold a lane (the browser by default), or raise LaneBusy after the wait budget."""
    budget = WAIT_SECONDS if wait_seconds is None else wait_seconds
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + budget
    try:
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    held = _holder(handle)
                    what = f"computer {name}" if name else "browser"
                    raise LaneBusy(
                        f"another job has held the {what} lane for longer than {budget:.0f}s"
                        + (f" ({held})" if held else "")
                        + (". It is a browser task: task(cancel=true) stops it" if (held or "").startswith("task ") and not name else "")
                        + (". This host runs one browser at a time; retry, or use fetch for a page that does not need one."
                           if not name else ". One job drives a computer at a time; retry when it finishes.")
                    ) from None
                await asyncio.sleep(POLL_SECONDS)
        os.ftruncate(handle, 0)
        os.write(handle, f"{label} pid={os.getpid()} since={time.time():.0f}\n".encode())
        os.fsync(handle)
        yield
    finally:
        try:
            fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            os.close(handle)


def _holder(handle: int) -> str:
    try:
        os.lseek(handle, 0, os.SEEK_SET)
        return os.read(handle, 200).decode("utf-8", "replace").strip()
    except OSError:
        return ""
