"""agent-browseruse: hands a whole goal to Browser-Use, in a tab of its own.

A task names the browser it runs in. With ``cdp_url`` it gets a browser of its own (a hosted
Browser Use Cloud browser the gateway opened for it), and up to ``BU_PARALLEL`` such tasks run
side by side, each in its own child process. Without it the task runs in the box's shared
Chromium (``CDP_URL``), one at a time: concurrent Browser-Use runs on one Chromium were measured
to break each other.

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
  POST /api/task     {goal, max_steps, timeout_seconds, cdp_url?, task_id?} -> the run, steps, answer, tokens, cost
  POST /api/cancel   {task_id?} stop that task, or every task: kill the child, close its tabs, then answer
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
CDP_URL = os.getenv("CDP_URL", "")  # empty: no shared browser; each task brings its own
# 0 (the default) = no cap of ours: as many tasks as Browser Use hands out browsers for. Set it only
# as a memory guard on a small host; each task is a child process of ~100-300 MB.
PARALLEL = int(os.getenv("BU_PARALLEL", "0")) or 10_000
MODEL = os.getenv("BU_MODEL", "z-ai/glm-5.3-flash")
# GLM 5.3 Flash reasons on every call and OpenRouter refuses to turn that off; left at its default
# effort a step took ~40 s and up to 6k tokens. "low" brings it back to a few seconds.
REASONING_EFFORT = os.getenv("BU_REASONING_EFFORT", "low")
OPENROUTER = "https://openrouter.ai/api/v1"
MAX_STEPS = int(os.getenv("BU_MAX_STEPS", "50"))
MAX_SECONDS = int(os.getenv("BU_MAX_SECONDS", "900"))
RUNNER = Path(__file__).with_name("runner.py")
KEEP_STEPS = 40


# ── CDP, as a plain client: list, open and close tabs ─────────────────────────────
async def dialable(cdp_url: str) -> str:
    """Chromium's DevTools refuses a Host header that is neither an IP nor localhost, and Steel
    passes ours through, so a compose name like ws://steel:3000/ is dialled by IP. A wss:// address
    (a hosted browser) is dialled as given: TLS needs its name."""
    parts = urlsplit(cdp_url)
    if parts.scheme == "wss":
        return cdp_url
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


async def cdp(*calls: tuple[str, dict], url: str | None = None) -> list[dict]:
    """Run browser-level CDP calls in order on one short-lived connection."""
    out = []
    async with connect(await dialable(url or CDP_URL), max_size=None, open_timeout=30) as ws:
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


async def pages(url: str | None = None) -> dict[str, dict]:
    [listed] = await cdp(("Target.getTargets", {}), url=url)
    return {t["targetId"]: {"url": t.get("url", ""), "opener": t.get("openerId")}
            for t in listed["targetInfos"] if t.get("type") == "page"}


async def open_tab(url: str | None = None) -> str:
    [made] = await cdp(("Target.createTarget", {"url": "about:blank"}), url=url)
    return made["targetId"]


async def close_task_tabs(foreign: dict[str, dict], url: str | None = None) -> int:
    """Close every tab the task opened. A tab that was there before it, or a popup one of those
    opened meanwhile, is someone else's and stays. Never close the last tab: keep a blank one."""
    now = await pages(url)
    ours = [t for t, info in now.items() if t not in foreign and info["opener"] not in foreign]
    if not ours:
        return 0
    calls: list[tuple[str, dict]] = []
    if len(ours) == len(now):
        calls.append(("Target.createTarget", {"url": "about:blank"}))
    calls += [("Target.closeTarget", {"targetId": t}) for t in ours]
    await cdp(*calls, url=url)
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
    def __init__(self, shared: bool = True) -> None:
        self.shared = shared  # in the box's own Chromium, not a browser of its own
        self.proc: asyncio.subprocess.Process | None = None
        self.cancelled = asyncio.Event()
        self.finished = asyncio.Event()


RUNS: dict[str, Run] = {}
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


async def run_task(run: Run, goal: str, max_steps: int, timeout: int, cdp_url: str | None = None) -> dict[str, Any]:
    started = time.monotonic()
    workdir = tempfile.mkdtemp(prefix="bu-task-")
    progress, result_path, errlog = (Path(workdir) / n for n in ("progress.jsonl", "result.json", "stderr.log"))
    browser = cdp_url or CDP_URL
    foreign = await pages(browser)
    own = await open_tab(browser)
    spec = {"goal": goal, "max_steps": max_steps, "cdp_url": await dialable(browser), "model": MODEL,
            "reasoning_effort": REASONING_EFFORT, "own_tab": own, "foreign_tabs": list(foreign), "progress": str(progress), "result": str(result_path)}
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
            closed = await close_task_tabs(foreign, browser)
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
    if CDP_URL:
        try:
            await cdp(("Browser.getVersion", {}))
            browser = "reachable"
        except Exception as exc:
            browser = f"unreachable: {type(exc).__name__}: {exc}"[:200]
    else:
        browser = "none shared: each task brings its own"
    return JSONResponse({
        "ok": SELF_CHECK == "ok" and not browser.startswith("unreachable") and bool(os.getenv("OPENROUTER_API_KEY")),
        "busy": len(RUNS) >= PARALLEL, "running": len(RUNS), "parallel": PARALLEL, "model": MODEL,
        "llm_key": bool(os.getenv("OPENROUTER_API_KEY")), "self_check": SELF_CHECK, "browser": browser,
    })


async def task(request: Request) -> JSONResponse:
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
        cdp_url = str(body.get("cdp_url") or "") or None
        task_id = str(body.get("task_id") or "") or os.urandom(6).hex()
    except (ValueError, KeyError, TypeError):
        return JSONResponse({"error": "send {goal, max_steps?, timeout_seconds?, cdp_url?, task_id?}"}, status_code=400)
    if not goal:
        return JSONResponse({"error": "goal is empty"}, status_code=400)
    if cdp_url and urlsplit(cdp_url).scheme not in ("ws", "wss"):
        return JSONResponse({"error": "cdp_url must be a ws:// or wss:// DevTools address"}, status_code=400)
    if not cdp_url and not CDP_URL:
        return JSONResponse({"error": "no shared browser here: send the cdp_url of a browser for this task"}, status_code=400)
    # Checked and taken with no await between: two requests cannot both get the last slot.
    if task_id in RUNS:
        return JSONResponse({"error": f"task {task_id} is already running"}, status_code=409)
    if len(RUNS) >= PARALLEL:
        return JSONResponse({"error": f"{PARALLEL} tasks are already running (BU_PARALLEL)"}, status_code=409)
    if not cdp_url and any(r.shared for r in RUNS.values()):
        return JSONResponse({"error": "a task is already running in the shared browser"}, status_code=409)
    RUNS[task_id] = run = Run(shared=not cdp_url)
    try:
        out = await run_task(run, goal, max_steps, timeout, cdp_url)
    except Exception as exc:
        log.exception("task failed")
        return JSONResponse({"error": f"{type(exc).__name__}: {str(exc).split('?')[0]}"[:300]}, status_code=502)
    finally:
        run.finished.set()
        RUNS.pop(task_id, None)
    return JSONResponse(finite({**out, "task_id": task_id}))


async def cancel(request: Request) -> JSONResponse:
    if not authorized(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        wanted = str((await request.json()).get("task_id") or "")
    except (ValueError, AttributeError):
        wanted = ""
    runs = [r for tid, r in RUNS.items() if not wanted or tid == wanted]
    if not runs:
        return JSONResponse({"cancelled": False, "detail": "no task running"})
    for run in runs:
        run.cancelled.set()
    try:
        # Answer only once the children are dead and their tabs closed: the caller releases the
        # browser on this reply, and nothing of a task may outlive that.
        await asyncio.wait_for(asyncio.gather(*(r.finished.wait() for r in runs)), 20)
    except TimeoutError:
        return JSONResponse({"cancelled": False, "detail": "the task did not stop within 20 s"}, status_code=504)
    return JSONResponse({"cancelled": True, "count": len(runs)})


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
