"""Browser-Use: hand a whole goal to an agent that works it in the one browser.

This is the one place in the box with a step-planning model in it, and it is here on purpose:
task(surface="browser") is for a caller that would rather not plan the steps. Each step is one
call to the model on OpenRouter; the answer comes back with every step, the pages visited, the
tokens spent and what they cost at list price.

It talks to the agent-browseruse container (agents/browseruse/server.py): /health, /task and
/cancel. The container runs each task in a child process confined to a tab of its own, and
answers /cancel only once that process is dead and its tabs are closed, which is what lets the
caller here release the browser lane safely.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

# The container bounds the task; this only has to outlast it and the tab cleanup after it.
MARGIN = 45.0


class BrowserUseUnavailable(RuntimeError):
    """agent-browseruse is not configured, not reachable, or refused. The message says which."""


def _base() -> str:
    return os.getenv("BB_BROWSERUSE_URL", "").rstrip("/")


def configured() -> bool:
    return bool(_base() and os.getenv("BB_BROWSERUSE_TOKEN"))


def _explain(response: httpx.Response) -> str:
    if response.status_code == 401:
        return "agent-browseruse refused the token: BB_BROWSERUSE_TOKEN must equal the BU_TOKEN it runs with"
    try:
        detail = response.json().get("error") or response.text[:200]
    except ValueError:
        detail = response.text[:200]
    return f"agent-browseruse returned {response.status_code}: {detail}"


async def _call(method: str, path: str, body: dict | None = None, *, timeout: float) -> Any:
    if not configured():
        raise BrowserUseUnavailable("task on the browser is not configured: set BB_BROWSERUSE_URL and BB_BROWSERUSE_TOKEN")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, f"{_base()}/api{path}", json=body,
                                            headers={"Authorization": f"Bearer {os.getenv('BB_BROWSERUSE_TOKEN', '')}"})
    except httpx.TimeoutException:
        raise BrowserUseUnavailable(f"agent-browseruse did not answer {path} within {timeout:.0f}s") from None
    except httpx.HTTPError as exc:
        raise BrowserUseUnavailable(f"agent-browseruse is unreachable at {_base()} ({type(exc).__name__})") from None
    if response.status_code >= 400:
        raise BrowserUseUnavailable(_explain(response))
    return response.json()


async def health() -> dict:
    body = await _call("GET", "/health", timeout=10)
    detail = {"model": body.get("model"), "busy": body.get("busy"), "browser": body.get("browser")}
    if not body.get("llm_key"):
        detail["problem"] = "agent-browseruse has no OPENROUTER_API_KEY"
    elif body.get("self_check") != "ok":
        detail["problem"] = f"its Browser-Use self-check failed: {body.get('self_check')}"
    elif body.get("browser") != "reachable":
        detail["problem"] = f"it cannot reach the browser: {body.get('browser')}"
    return {"up": not detail.get("problem"), **detail}


async def run(goal: str, max_steps: int, timeout_seconds: int) -> dict:
    return await _call("POST", "/task", {"goal": goal, "max_steps": max_steps, "timeout_seconds": timeout_seconds},
                       timeout=timeout_seconds + MARGIN)


async def cancel() -> dict | None:
    """Stop whatever is running there. Returns once the agent is dead and its tabs are closed."""
    try:
        return await _call("POST", "/cancel", timeout=30)
    except BrowserUseUnavailable:
        return None
