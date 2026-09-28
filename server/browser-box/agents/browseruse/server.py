"""agent-browseruse: hands one whole goal at a time to Browser-Use, in a tab of its own.

This process never imports browser_use. Each task runs in a child process (runner.py) that is
killed outright when the task times out or is cancelled, so a wedged agent cannot wedge this
server. The parent, not the child, opens the task's tab and closes the task's tabs afterwards:
a killed child cannot clean up, and inside a finished Browser-Use process new CDP connections
stopped completing their handshake (verified), so cleanup there is not dependable either.

Other clients of the same Chromium (Jev's act tab) are never touched. The tabs that exist when
a task starts are handed to the child as foreign, and the child hides them from Browser-Use
entirely; without that, Browser-Use took over the first tab it found, which was Jev's.

Endpoints, all behind the bearer token except health:
  GET  /api/health   liveness, model, whether a task is running, the child's self-check
  POST /api/task     {goal, max_steps, timeout_seconds} -> the run, steps, answer, tokens, cost
  POST /api/cancel   stop the running task: kill the child, close its tabs, then answer
"""
from __future__ import annotations

import asyncio
import contextlib
import hmac
import ipaddress
import json
import logging
import math
import os
import shutil
import signal
import socket
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from websockets.asyncio.client import connect

log = logging.getLogger("agent-browseruse")

TOKEN = os.getenv("BU_TOKEN", "")
CDP_URL = os.getenv("CDP_URL", "ws://steel:3000/")
MODEL = os.getenv("BU_MODEL", "z-ai/glm-5.3-flash")
OPENROUTER = "https://openrouter.ai/api/v1"
MAX_STEPS = int(os.getenv("BU_MAX_STEPS", "50"))
MAX_SECONDS = int(os.getenv("BU_MAX_SECONDS", "900"))
RUNNER = Path(__file__).with_name("runner.py")
KEEP_STEPS = 40


# ── CDP, as a plain client: list, open and close tabs ─────────────────────────────
async def dialable(cdp_url: str) -> str:
    """Chromium's DevTools refuses a Host header that is neither an IP nor localhost, and Steel
    passes ours through, so a compose name like ws://steel:3000/ is dialled by IP."""
    parts = urlsplit(cdp_url)
    host = parts.hostname or ""
    try:
        ipaddress.ip_address(host)
        return cdp_url
    except ValueError:
        if host == "localhost":
            return cdp_url
    infos = await asyncio.to_thread(socket.getaddrinfo, host, parts.port, socket.AF_INET, socket.SOCK_STREAM)
    netloc = f"{infos[0][4][0]}:{parts.port}" if parts.port else infos[0][4][0]
    return parts._replace(netloc=netloc).geturl()


async def cdp(*calls: tuple[str, dict]) -> list[dict]:
    """Run browser-level CDP calls in order on one short-lived connection."""
    out = []
    async with connect(await dialable(CDP_URL), max_size=None, open_timeout=10) as ws:
        for mid, (method, params) in enumerate(calls, 1):
            await ws.send(json.dumps({"id": mid, "method": method, "params": params}))
            while True:
                reply = json.loads(await asyncio.wait_for(ws.recv(), 15))
                if reply.get("id") == mid:
                    if "error" in reply:
                        raise RuntimeError(f"{method}: {reply['error'].get('message')}")
                    out.append(reply.get("result") or {})
                    break
    return out


async def pages() -> dict[str, dict]:
    [listed] = await cdp(("Target.getTargets", {}))
    return {t["targetId"]: {"url": t.get("url", ""), "opener": t.get("openerId")}
            for t in listed["targetInfos"] if t.get("type") == "page"}


async def open_tab() -> str:
    [made] = await cdp(("Target.createTarget", {"url": "about:blank"}))
    return made["targetId"]


async def close_task_tabs(foreign: dict[str, dict]) -> int:
    """Close every tab the task opened. A tab that was there before it, or a popup one of those
    opened meanwhile, is someone else's and stays. Never close the last tab: keep a blank one."""
    now = await pages()
    ours = [t for t, info in now.items() if t not in foreign and info["opener"] not in foreign]
    if not ours:
        return 0
    calls: list[tuple[str, dict]] = []
    if len(ours) == len(now):
        calls.append(("Target.createTarget", {"url": "about:blank"}))
    calls += [("Target.closeTarget", {"targetId": t}) for t in ours]
    await cdp(*calls)
    return len(ours)


# ── cost: OpenRouter's list price, looked up once ───────────────────────────────────
_PRICES: dict[str, tuple[float, float]] = {}


async def price(model: str) -> tuple[float, float] | None:
    if model not in _PRICES:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                listed = (await client.get(f"{OPENROUTER}/models")).json()["data"]
            for row in listed:
                p = row.get("pricing") or {}
                _PRICES[row["id"]] = (float(p.get("prompt") or 0), float(p.get("completion") or 0))
        except Exception as exc:
            log.warning("could not read OpenRouter prices: %s", exc)
    return _PRICES.get(model)


async def costed(tokens: dict | None) -> dict[str, Any]:
    if not tokens:
        return {"estimated_cost_usd": None}
    rates = await price(MODEL)
    if rates is None:
        return {"estimated_cost_usd": None, "cost_basis": f"no OpenRouter list price found for {MODEL}"}
    usd = tokens.get("prompt", 0) * rates[0] + tokens.get("completion", 0) * rates[1]
    return {"estimated_cost_usd": round(usd, 6),
            "cost_basis": f"OpenRouter list price for {MODEL}; prompt-cache discounts not applied, so an upper bound"}


# ── the task ──────────────────────────────────────────────────────────────────────
class Run:
    def __init__(self) -> None:
        self.proc: asyncio.subprocess.Process | None = None
        self.cancelled = asyncio.Event()
        self.finished = asyncio.Event()


LOCK = asyncio.Lock()
CURRENT: Run | None = None
SELF_CHECK: str = "not run"


def child_env(workdir: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "PYTHONPATH", "SSL_CERT_FILE")}
    env.update({
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
        "HOME": workdir, "TMPDIR": workdir, "XDG_CONFIG_HOME": workdir,
        "ANONYMIZED_TELEMETRY": "false", "BROWSER_USE_CLOUD_SYNC": "false",
        "BROWSER_USE_LOGGING_LEVEL": "warning", "PYTHONUNBUFFERED": "1",
    })
    return env


def _kill(proc: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _progress(path: Path) -> list[dict]:
    rows = []
    try:
        for line in path.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return rows


async def run_task(run: Run, goal: str, max_steps: int, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    workdir = tempfile.mkdtemp(prefix="bu-task-")
    progress, result_path, errlog = (Path(workdir) / n for n in ("progress.jsonl", "result.json", "stderr.log"))
    foreign = await pages()
    own = await open_tab()
    spec = {"goal": goal, "max_steps": max_steps, "cdp_url": await dialable(CDP_URL), "model": MODEL,
            "own_tab": own, "foreign_tabs": list(foreign), "progress": str(progress), "result": str(result_path)}
    outcome = "finished"
    try:
        with errlog.open("wb") as err:
            run.proc = await asyncio.create_subprocess_exec(
                sys.executable, str(RUNNER), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
                stderr=err, env=child_env(workdir), cwd=workdir, start_new_session=True)
            run.proc.stdin.write(json.dumps(spec).encode())
            await run.proc.stdin.drain()
            run.proc.stdin.close()
            waiter = asyncio.create_task(run.proc.wait())
            stopper = asyncio.create_task(run.cancelled.wait())
            done, _ = await asyncio.wait({waiter, stopper}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            if waiter not in done:
                outcome = "cancelled" if stopper in done else "timed_out"
                _kill(run.proc)
                await run.proc.wait()
            stopper.cancel()
    finally:
        # However this ends, even with this handler cancelled, the agent dies before its tabs are
        # closed: a live one would open a fresh blank tab the moment it saw none of its own.
        if run.proc and run.proc.returncode is None:
            _kill(run.proc)
            await run.proc.wait()
        try:
            closed = await close_task_tabs(foreign)
        except Exception as exc:
            closed = None
            log.warning("could not close the task's tabs: %s", exc)
    result = _read_json(result_path) or {}
    steps = result.get("steps") or _progress(progress)
    body: dict[str, Any] = {
        "status": result.get("status") if outcome == "finished" and result else outcome,
        "answer": result.get("answer"),
        "agent_says_success": result.get("success"),
        "steps_taken": len(steps),
        "steps": steps[-KEEP_STEPS:],
        "urls": result.get("urls") or list(dict.fromkeys(s.get("url") for s in steps if s.get("url"))),
        "final_url": result.get("final_url") or next((s.get("url") for s in reversed(steps) if s.get("url")), None),
        "tokens": result.get("tokens") or (steps[-1].get("tokens") if steps else None),
        "errors": result.get("errors") or [],
        "model": MODEL,
        "seconds": round(time.monotonic() - started, 1),
        "tabs_closed": closed,
    }
    if len(steps) > KEEP_STEPS:
        body["steps_note"] = f"showing the last {KEEP_STEPS} of {len(steps)} steps"
    if outcome == "finished" and not result:
        tail = errlog.read_text(errors="replace")[-600:] if errlog.exists() else ""
        body.update(status="error", errors=[f"the agent process exited ({run.proc.returncode}) without a result: {tail}"])
    body.update(await costed(body["tokens"]))
    shutil.rmtree(workdir, ignore_errors=True)
    return body


# ── HTTP ──────────────────────────────────────────────────────────────────────────
def authorized(request: Request) -> bool:
    given = request.headers.get("authorization", "")
    return bool(TOKEN) and hmac.compare_digest(given.encode(), f"Bearer {TOKEN}".encode())


def finite(value):
    """Browser-Use's step data can hold inf (a scroll "to the end"): JSON has no such number, and
    one in a result turned a finished task into a 500."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    if isinstance(value, list):
        return [finite(v) for v in value]
    return value


async def health(_request: Request) -> JSONResponse:
    try:
        await cdp(("Browser.getVersion", {}))
        browser = "reachable"
    except Exception as exc:
        browser = f"unreachable: {type(exc).__name__}: {exc}"[:200]
    return JSONResponse({
        "ok": SELF_CHECK == "ok" and browser == "reachable" and bool(os.getenv("OPENROUTER_API_KEY")),
        "busy": LOCK.locked(), "model": MODEL, "llm_key": bool(os.getenv("OPENROUTER_API_KEY")),
        "self_check": SELF_CHECK, "browser": browser,
    })


async def task(request: Request) -> JSONResponse:
    global CURRENT
    if not authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not os.getenv("OPENROUTER_API_KEY"):
        return JSONResponse({"error": "agent-browseruse has no OPENROUTER_API_KEY"}, status_code=503)
    if SELF_CHECK != "ok":
        return JSONResponse({"error": f"the Browser-Use self-check failed: {SELF_CHECK}"}, status_code=503)
    try:
        body = await request.json()
        goal = str(body["goal"]).strip()
        max_steps = max(1, min(int(body.get("max_steps", 25)), MAX_STEPS))
        timeout = max(30, min(int(body.get("timeout_seconds", 300)), MAX_SECONDS))
    except (ValueError, KeyError, TypeError):
        return JSONResponse({"error": "send {goal, max_steps?, timeout_seconds?}"}, status_code=400)
    if not goal:
        return JSONResponse({"error": "goal is empty"}, status_code=400)
    if LOCK.locked():
        return JSONResponse({"error": "a task is already running"}, status_code=409)
    async with LOCK:
        CURRENT = run = Run()
        try:
            out = await run_task(run, goal, max_steps, timeout)
        except Exception as exc:
            log.exception("task failed")
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:300]}, status_code=502)
        finally:
            run.finished.set()
            CURRENT = None
    return JSONResponse(finite(out))


async def cancel(request: Request) -> JSONResponse:
    if not authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    run = CURRENT
    if run is None:
        return JSONResponse({"cancelled": False, "detail": "no task running"})
    run.cancelled.set()
    try:
        # Answer only once the child is dead and its tabs are closed: the caller releases the
        # browser lane on this reply, and nothing of the task may outlive that.
        await asyncio.wait_for(run.finished.wait(), 20)
    except TimeoutError:
        return JSONResponse({"cancelled": False, "detail": "the task did not stop within 20 s"}, status_code=504)
    return JSONResponse({"cancelled": True})


async def self_check() -> None:
    """Run the child's own check once: a pinned Browser-Use whose patched methods moved must
    fail here, at startup, and not quietly inside someone's task."""
    global SELF_CHECK
    workdir = tempfile.mkdtemp(prefix="bu-check-")
    proc = await asyncio.create_subprocess_exec(sys.executable, str(RUNNER), "--self-check", env=child_env(workdir),
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await asyncio.wait_for(proc.communicate(), 120)
    text = out.decode(errors="replace").strip()
    SELF_CHECK = "ok" if proc.returncode == 0 and text.endswith("self-check ok") else (text.splitlines() or ["no output"])[-1][:300]
    shutil.rmtree(workdir, ignore_errors=True)
    log.info("self-check: %s", SELF_CHECK)


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    await self_check()
    yield


def app() -> Starlette:
    return Starlette(
        routes=[Route("/api/health", health), Route("/api/task", task, methods=["POST"]),
                Route("/api/cancel", cancel, methods=["POST"])],
        lifespan=lifespan,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    host = os.getenv("HOST", "0.0.0.0")
    if not TOKEN and host not in ("127.0.0.1", "localhost"):
        sys.exit("BU_TOKEN is empty: refusing to listen off loopback without a token")
    uvicorn.run(app(), host=host, port=int(os.getenv("PORT", "3120")), log_level="warning")
