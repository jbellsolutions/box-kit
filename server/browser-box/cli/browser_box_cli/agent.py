"""`bb ask` — a client-side brain.

The box has no LLM in it, on purpose. This module is a client: it runs the loop HERE,
calling the same four MCP tools an agent would. If it disappeared, the box would be
unchanged. That is the difference between this and the harness that failed twice.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .client import call, tool_list

MODEL = os.getenv("BB_MODEL", "z-ai/glm-5.3-flash")
BASE = os.getenv("BB_LLM_BASE", "https://openrouter.ai/api/v1")
MAX_STEPS = int(os.getenv("BB_MAX_STEPS", "12"))

SYSTEM = """You drive a self-hosted browser through four tools. You decide; the box executes.

Rules that save time and money:
- Try `fetch` FIRST. It is free, instant, and works on most server-rendered pages.
- Use `read` only when fetch came back empty or unrendered. It holds the single browser lane.
- Ask for a screenshot only when the picture is the evidence; it costs a second page load.
- If a tool refuses, read the reason and adapt. Do not retry the identical call.
- When you have the answer, say it plainly with the URL you got it from. Do not narrate tool calls.
"""


class LlmUnavailable(RuntimeError):
    pass


def _key() -> str:
    key = os.getenv("OPENROUTER_API_KEY") or os.getenv("BB_LLM_KEY")
    if not key:
        raise LlmUnavailable(
            "bb ask needs a model. Set OPENROUTER_API_KEY (or BB_LLM_KEY), or use the direct "
            "commands — bb fetch / bb read / bb status — which need no model at all."
        )
    return key


def _for_openai(tool: Any) -> dict:
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": tool.inputSchema},
    }


def _trim(result: dict) -> dict:
    """A base64 screenshot would swamp the context; the model only needs to know it exists."""
    if "screenshot_base64" in result:
        result = {**result, "screenshot_base64": f"<{result.get('screenshot_bytes', 0)} bytes, saved separately>"}
    return result


async def ask(goal: str, history: list[dict] | None = None, *, on_step=None) -> tuple[str, list[dict]]:
    """Run the goal to an answer. Returns (answer, messages) so a REPL can keep the thread."""
    key = _key()
    tools = [_for_openai(tool) for tool in await tool_list()]
    messages = list(history or [{"role": "system", "content": SYSTEM}])
    messages.append({"role": "user", "content": goal})

    async with httpx.AsyncClient(timeout=180) as http:
        for _step in range(MAX_STEPS):
            response = await http.post(
                f"{BASE}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": messages, "tools": tools, "tool_choice": "auto"},
            )
            if response.status_code >= 400:
                raise LlmUnavailable(f"{MODEL} returned {response.status_code}: {response.text[:300]}")
            choice = response.json()["choices"][0]["message"]
            messages.append(choice)
            calls = choice.get("tool_calls") or []
            if not calls:
                return (choice.get("content") or "").strip(), messages
            for entry in calls:
                name = entry["function"]["name"]
                try:
                    arguments = json.loads(entry["function"]["arguments"] or "{}")
                except ValueError:
                    arguments = {}
                if on_step:
                    on_step(name, arguments)
                result = _trim(await call(name, arguments))
                messages.append(
                    {"role": "tool", "tool_call_id": entry["id"], "name": name,
                     "content": json.dumps(result, ensure_ascii=False)[:20000]}
                )
    return f"Stopped after {MAX_STEPS} steps without a final answer.", messages
