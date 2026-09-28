"""Jev: step grounding inside the box. The caller plans; Jev decides which element on the page a
plain-words step means ("the pricing link"), in roughly 0.1-0.5 s, and drives Steel's own
Chromium to do it. It never generates text, so it cannot be the brain, and it is not one here.

This talks to the agent-jev container (jev-automation's server/http.ts): /health, /command,
/reply, /cancel, and /read when that build has it. The container gets no brain key and this
module never calls /ask, so no second brain rides in with it.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

# A command can be several steps, each a page load; the lane is held for all of it.
TIMEOUT = float(os.getenv("BB_JEV_TIMEOUT_SECONDS", "120"))
# The Playwright surface is the one attached to Steel; the others (Mac, Chrome bridge) are off.
SESSION = "playwright"
REFUSED_MARK = "ERR_BLOCKED_BY_CLIENT"


class JevUnavailable(RuntimeError):
    """agent-jev is not configured, not reachable, or refused. The message says which."""


def _base() -> str:
    return os.getenv("BB_JEV_URL", "").rstrip("/")


def configured() -> bool:
    return bool(_base() and os.getenv("BB_JEV_TOKEN"))


def _explain(response: httpx.Response) -> str:
    if response.status_code == 401:
        return "agent-jev refused the token: BB_JEV_TOKEN must equal the JEV_TOKEN agent-jev runs with"
    try:
        detail = response.json().get("error") or response.text[:200]
    except ValueError:
        detail = response.text[:200]
    return f"agent-jev returned {response.status_code}: {detail}"


async def _call(method: str, path: str, body: dict | None = None, *, timeout: float | None = None,
                absent_ok: bool = False) -> Any:
    if not configured():
        raise JevUnavailable("act is not configured: set BB_JEV_URL and BB_JEV_TOKEN (see .env.example)")
    try:
        async with httpx.AsyncClient(timeout=timeout or TIMEOUT) as client:
            response = await client.request(method, f"{_base()}/api{path}", json=body,
                                            headers={"Authorization": f"Bearer {os.getenv('BB_JEV_TOKEN', '')}"})
    except httpx.TimeoutException:
        raise JevUnavailable(f"agent-jev did not answer {path} within {timeout or TIMEOUT:.0f}s") from None
    except httpx.HTTPError as exc:
        raise JevUnavailable(f"agent-jev is unreachable at {_base()} ({type(exc).__name__})") from None
    if absent_ok and response.status_code == 404:
        return None
    if response.status_code >= 400:
        raise JevUnavailable(_explain(response))
    return response.json()


async def health() -> dict:
    """Cheap and unauthenticated on Jev's side; says whether decisions are Jev's or heuristics."""
    body = await _call("GET", "/health", timeout=5)
    jev = body.get("jev") or {}
    return {
        "decisions": f"TypeSafe Jev ({jev.get('model')})" if jev.get("enabled") else
                     "keyword heuristics — agent-jev has no TYPESAFE_API_KEY",
        "page": body.get("url"),
        "paused": bool(body.get("paused")),
    }


async def command(text: str) -> dict:
    return await _call("POST", "/command", {"text": text, "session": SESSION})


async def pick(element_id: str) -> dict:
    return await _call("POST", "/reply", {"pick": element_id, "session": SESSION})


async def confirm(ok: bool) -> dict:
    return await _call("POST", "/reply", {"ok": bool(ok), "session": SESSION})


async def cancel() -> None:
    try:
        await _call("POST", "/cancel", {"session": SESSION}, timeout=5)
    except JevUnavailable:
        pass


async def read(max_chars: int) -> dict | None:
    """The page's readable text, or None when this Jev build has no /read."""
    return await _call("POST", "/read", {"session": SESSION, "max": max_chars}, timeout=30, absent_ok=True)


def summarize(raw: dict) -> dict:
    """Jev's CommandResult, reshaped for a caller that has to decide what to do next."""
    steps = []
    for step in raw.get("steps") or []:
        result = step.get("result") or {}
        row = {"command": step.get("command"), "did": result.get("text"), "outcome": result.get("level")}
        decision = step.get("decision") or {}
        if decision:
            # "jev" = the model chose; "heuristic" = code did (an explicit URL, or Jev unreachable)
            row["decided_by"] = decision.get("source")
            row["decision_ms"] = decision.get("latencyMs")
        if (step.get("verify") or {}).get("text"):
            row["check"] = step["verify"]["text"]
        steps.append(row)
    page = raw.get("page") or {}
    out: dict[str, Any] = {"steps": steps, "url": page.get("url"), "title": page.get("title")}
    pending = raw.get("pending")
    if pending and pending.get("kind") == "clarify":
        out.update(
            status="needs_clarification",
            question=pending.get("question"),
            options=[{"pick": o.get("elementId"), "label": o.get("label"), "probability": round(float(o.get("probability") or 0), 2)}
                     for o in pending.get("options") or []],
            next="answer with act(pick=<an option's pick>)",
        )
    elif pending and pending.get("kind") == "confirm":
        out.update(status="needs_confirmation", action=pending.get("actionLabel"), reason=pending.get("reason"),
                   next="answer with act(confirm=true) to go ahead or act(confirm=false) to cancel")
    elif pending:
        # An approval comes only from a brain, which this box never gives Jev.
        out.update(status="needs_approval", question=pending.get("question"))
    else:
        out["status"] = "done" if raw.get("ok") else "failed"
    if raw.get("stoppedAt") is not None:
        out["stopped_at_step"] = raw["stoppedAt"]
    if any(REFUSED_MARK in (row.get("did") or "") for row in steps):
        out["refused"] = ("the browser refused a private or internal address (loopback, a private network, "
                          "cloud metadata, or a name that resolves to one); only the public web is reachable")
    return out
