"""Orgo cloud computers: full desktops OFF this box, so they cost no RAM here and never
contend for the browser lane.

Every path and body below was read from Orgo's own API docs (docs.orgo.ai, 2026-09-23), not
recalled. Two facts from them shaped this module:

- The computer-use endpoint accepts EXACTLY five model ids and 400s on anything else. Super
  Browser's adapter sent "claude-sonnet-4-6" (hyphen; Orgo spells it "claude-sonnet-4.6"),
  which is the likeliest reason its Orgo live test failed on 2026-09-20. The id is validated
  here before any request is made.
- A computer "runs continuously until you stop it". There is no auto-stop, whatever the old
  adapter's auto_stop_minutes suggested. So creating one is opt-in, and stop is a tool action.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

BASE = os.getenv("ORGO_API_BASE", "https://www.orgo.ai/api").rstrip("/")
MODELS = ("claude-sonnet-5", "claude-opus-5", "claude-opus-4.8", "claude-sonnet-4.6", "claude-opus-4.6")
TIMEOUT = float(os.getenv("ORGO_TIMEOUT_SECONDS", "60"))
WORKSPACE_NAME = os.getenv("ORGO_WORKSPACE", "browser-box")
COMPUTER_NAME = os.getenv("ORGO_COMPUTER_NAME", "browser-box")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# Orgo's documented statuses. `stop` freezes, so a stopped computer reads `frozen`.
STARTABLE = ("frozen", "stopped", "suspended")


# Discovery costs two API calls. Caller-driven computer use is many small steps, so the
# answer is remembered briefly rather than rediscovered on every click.
_RESOLVED: dict[str, Any] = {}
RESOLVE_TTL = float(os.getenv("ORGO_RESOLVE_TTL_SECONDS", "300"))


class OrgoUnavailable(RuntimeError):
    """Orgo is not configured, not reachable, or refused. The message says which."""


def key() -> str:
    return os.getenv("ORGO_API_KEY", "")


def configured() -> bool:
    return bool(key())


def model() -> str:
    chosen = os.getenv("ORGO_MODEL", "claude-sonnet-5")
    if chosen not in MODELS:
        raise OrgoUnavailable(
            f"ORGO_MODEL={chosen!r} is not one Orgo accepts; it would return 400 invalid_model. "
            f"Use one of: {', '.join(MODELS)} (note the dot in 4.6)."
        )
    return chosen


def computer_id_or_raise(value: str) -> str:
    """The id lands in a URL path, so it must not be able to walk that path."""
    if not isinstance(value, str) or not _ID.match(value):
        raise ValueError("computer_id must be letters, digits, '-' or '_' (an Orgo computer id)")
    return value


def screen_id_or_raise(value: str | None) -> str | None:
    """A supplied screen is always explicit; Orgo must reject unknown ids."""
    if value is None:
        return None
    if not isinstance(value, str) or not _ID.match(value):
        raise ValueError("screen_id must be an Orgo screen id")
    return value


def _screen_params(screen_id: str | None, **other: Any) -> dict:
    screen = screen_id_or_raise(screen_id)
    return {**other, **({"screen": screen} if screen else {})}


def _headers() -> dict[str, str]:
    if not configured():
        raise OrgoUnavailable("ORGO_API_KEY is not set. Keys begin with sk_live_; create one at orgo.ai/start.")
    return {"Authorization": f"Bearer {key()}", "Content-Type": "application/json"}


def _explain(response: httpx.Response) -> str:
    try:
        body = response.json()
        detail = body.get("error") or body.get("message") or body
    except ValueError:
        detail = response.text[:200]
    return f"orgo returned {response.status_code}: {str(detail)[:240]}"


async def _call(method: str, path: str, *, body: dict | None = None, params: dict | None = None,
                timeout: float | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=timeout or TIMEOUT) as client:
            response = await client.request(method, f"{BASE}{path}", json=body, params=params, headers=_headers())
    except httpx.HTTPError as exc:
        raise OrgoUnavailable(f"orgo is unreachable ({type(exc).__name__}: {exc})") from None
    if response.status_code >= 400:
        raise OrgoUnavailable(_explain(response))
    return response.json() if response.content else {}


def _collection(payload: Any, keys: tuple[str, ...]) -> list[dict]:
    """Orgo's live API has returned workspaces under "projects" and computers under "desktops"."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for candidate in (*keys, "data", "items"):
            value = payload.get(candidate)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


async def resolve(computer_id: str | None = None) -> tuple[str, str]:
    """Which computer to drive: explicit, then ORGO_COMPUTER_ID, then reuse, then start.

    Creating one is a new standing cost, so it only happens with BB_ORGO_AUTOCREATE=1.
    """
    if computer_id:
        return computer_id_or_raise(computer_id), "given"
    pinned = os.getenv("ORGO_COMPUTER_ID")
    if pinned:
        return computer_id_or_raise(pinned), "pinned via ORGO_COMPUTER_ID"
    if _RESOLVED and time.monotonic() - _RESOLVED["at"] < RESOLVE_TTL:
        return _RESOLVED["id"], _RESOLVED["how"]
    cid, how = await _discover()
    _RESOLVED.update(id=cid, how=how, at=time.monotonic())
    return cid, how


def forget() -> None:
    """Drop the remembered computer, e.g. after stopping it."""
    _RESOLVED.clear()


async def _discover() -> tuple[str, str]:
    workspaces = _collection(await _call("GET", "/workspaces"), ("workspaces", "projects"))
    workspace = next((w for w in workspaces if w.get("name") == WORKSPACE_NAME), workspaces[0] if workspaces else None)
    computers: list[dict] = []
    if workspace is not None:
        detail = await _call("GET", f"/workspaces/{computer_id_or_raise(str(workspace['id']))}")
        computers = _collection(detail, ("computers", "desktops"))
    running = [c for c in computers if c.get("status") == "running"]
    chosen = next((c for c in running if c.get("name") == COMPUTER_NAME), running[0] if running else None)
    if chosen is not None:
        return computer_id_or_raise(str(chosen["id"])), f"reused running computer {chosen.get('name', chosen['id'])}"
    asleep = [c for c in computers if c.get("status") in STARTABLE]
    if asleep:
        target = next((c for c in asleep if c.get("name") == COMPUTER_NAME), asleep[0])
        target_id = computer_id_or_raise(str(target["id"]))
        await _call("POST", f"/computers/{target_id}/start", body={})
        return target_id, f"started {target.get('name', target_id)} (it bills until stopped: computer action=stop)"
    if os.getenv("BB_ORGO_AUTOCREATE") != "1" or workspace is None:
        raise OrgoUnavailable(
            "no running or startable Orgo computer. Set ORGO_COMPUTER_ID to one you own, or set "
            "BB_ORGO_AUTOCREATE=1 to let this box create one — it then runs and bills until stopped."
        )
    created = await _call("POST", "/computers", body={"workspace_id": workspace["id"], "name": COMPUTER_NAME})
    return computer_id_or_raise(str(created["id"])), f"created {COMPUTER_NAME} (it bills until stopped: computer action=stop)"


async def health() -> dict:
    """A cheap authenticated read. Proves the key works without touching a computer."""
    workspaces = _collection(await _call("GET", "/workspaces", timeout=15), ("workspaces", "projects"))
    return {"workspaces": len(workspaces), "model": model()}


# ── actions ────────────────────────────────────────────────────────────────────────────

async def screenshot(cid: str, *, scale: float | None = None, screen_id: str | None = None,
                     context: bool = False) -> dict:
    params: dict[str, Any] = _screen_params(screen_id, response_format="base64", format="jpeg", quality=80)
    if scale:
        params["scale"] = scale
    if context:
        params["context"] = 1
    shot = await _call("GET", f"/computers/{computer_id_or_raise(cid)}/screenshot", params=params)
    return {"image": shot.get("image"), "mime_type": shot.get("mime_type") or "image/jpeg",
            "width": shot.get("width"), "height": shot.get("height"),
            **({"context": shot.get("context")} if context else {})}


async def click(cid: str, x: int, y: int, *, button: str = "left", double: bool = False,
                screen_id: str | None = None, context: bool = False) -> dict:
    return await _call("POST", f"/computers/{computer_id_or_raise(cid)}/click",
                       body={"x": int(x), "y": int(y), "button": button, "double": bool(double)},
                       params=_screen_params(screen_id, **({"context": 1} if context else {})))


async def type_text(cid: str, text: str, *, screen_id: str | None = None, context: bool = False) -> dict:
    return await _call("POST", f"/computers/{computer_id_or_raise(cid)}/type", body={"text": text},
                       params=_screen_params(screen_id, **({"context": 1} if context else {})))


async def press(cid: str, combo: str, *, screen_id: str | None = None, context: bool = False) -> dict:
    return await _call("POST", f"/computers/{computer_id_or_raise(cid)}/key", body={"key": combo},
                       params=_screen_params(screen_id, **({"context": 1} if context else {})))


async def scroll(cid: str, x: int, y: int, *, direction: str = "down", amount: int = 3,
                 screen_id: str | None = None, context: bool = False) -> dict:
    # x and y are required by Orgo: without them the pointer warps to the top-left corner.
    return await _call("POST", f"/computers/{computer_id_or_raise(cid)}/scroll",
                       body={"x": int(x), "y": int(y), "direction": direction, "amount": int(amount)},
                       params=_screen_params(screen_id, **({"context": 1} if context else {})))


async def bash(cid: str, command: str, *, timeout: int = 200) -> dict:
    return await _call("POST", f"/computers/{computer_id_or_raise(cid)}/bash",
                       body={"command": command, "timeout": int(timeout)}, timeout=float(timeout) + 15)


async def start(cid: str) -> dict:
    return await _call("POST", f"/computers/{computer_id_or_raise(cid)}/start", body={})


async def stop(cid: str) -> dict:
    result = await _call("POST", f"/computers/{computer_id_or_raise(cid)}/stop", body={})
    forget()
    return result


# ── Orgo's own computer-use agent ──────────────────────────────────────────────────────

async def agent(cid: str, goal: str, *, timeout_seconds: float = 600) -> dict:
    """Hand a whole goal to Orgo's hosted computer-use agent and wait for its answer.

    Streamed on purpose. Orgo ignores max_steps (the loop runs to a fixed 250), and a buffered
    request that times out on our side may keep running and billing on theirs. Closing a
    stream is the documented way to abort, so the deadline here actually stops the run.
    """
    body = {"computer_id": computer_id_or_raise(cid), "model": model(), "stream": True,
            "messages": [{"role": "user", "content": goal}]}
    parts: list[str] = []
    chunks = 0
    thread_id = None
    deadline = time.monotonic() + timeout_seconds
    timed_out = False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=timeout_seconds)) as client:
            async with client.stream("POST", f"{BASE}/v1/chat/completions", json=body, headers=_headers()) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise OrgoUnavailable(_explain(response))
                async for line in response.aiter_lines():
                    if time.monotonic() > deadline:
                        timed_out = True
                        break
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except ValueError:
                        continue
                    chunks += 1
                    thread_id = thread_id or (event.get("orgo") or {}).get("thread_id")
                    for choice in event.get("choices") or []:
                        piece = (choice.get("delta") or {}).get("content")
                        if isinstance(piece, str):
                            parts.append(piece)
    except httpx.HTTPError as exc:
        raise OrgoUnavailable(f"orgo agent stream failed ({type(exc).__name__}: {exc})") from None
    answer = "".join(parts).strip()
    return {
        "status": "timeout" if timed_out else "done",
        "answer": answer or None,
        "events": chunks,
        "thread_id": thread_id,
        **({"note": f"stopped after {timeout_seconds:.0f}s; the stream was closed, which aborts the run"} if timed_out else {}),
    }
