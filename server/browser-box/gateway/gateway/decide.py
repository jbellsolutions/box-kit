"""Typed decisions from a System 1 model: Jev (TypeSafe) by default, any server that speaks its API otherwise.

A decision model picks among options it is given and answers yes/no questions with a probability. It
never writes text, so it never plans and never decides what to type: code does that. Measured
2026-10-12 on 30 element questions over real pages (bench/decisionbench.py): Jev 30/30, ~176 ms;
Cloudflare's Clef, which takes the same request body, 28/30, ~518 ms.

Settings: ``TYPESAFE_API_KEY`` (required), ``BB_DECISION_URL`` (default TypeSafe's ``/v1/systemone``),
``BB_DECISION_MODEL`` (default ``jev-latest``).
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

URL = "https://api.typesafe.ai/v1/systemone"


class DecisionUnavailable(RuntimeError):
    """No key, or the decision model did not answer. Never holds the key."""


def configured() -> bool:
    return bool(os.getenv("TYPESAFE_API_KEY", "").strip())


def choice(instructions: str, options: dict[str, str]) -> dict[str, Any]:
    return {"type": "choice", "instructions": instructions, "criteria": options}


def noul(instructions: str, yes: str, no: str) -> dict[str, Any]:
    return {"type": "noul", "instructions": instructions, "criteria": {"true": yes, "false": no}}


async def ask(state: dict, questions: dict[str, dict], *, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """One request, every question at once. Returns {answers, model, ms, input_tokens}."""
    key = os.getenv("TYPESAFE_API_KEY", "").strip()
    if not key:
        raise DecisionUnavailable("act needs a decision model: set TYPESAFE_API_KEY")
    url = os.getenv("BB_DECISION_URL", "").strip() or URL
    body = {"model": os.getenv("BB_DECISION_MODEL", "").strip() or "jev-latest", "state": state, "questions": questions}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
            response = await client.post(url, json=body, headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError as exc:
        raise DecisionUnavailable(f"the decision model is unreachable ({type(exc).__name__})") from None
    if response.status_code >= 400:
        raise DecisionUnavailable(f"the decision model returned {response.status_code}")
    data = response.json()
    data = data.get("result", data)          # Cloudflare wraps the same answer in {"result": ...}
    return {"answers": data.get("answers") or {}, "model": data.get("model"),
            "ms": round((time.perf_counter() - started) * 1000), "input_tokens": (data.get("usage") or {}).get("input_tokens")}


def picked(answers: dict, name: str) -> tuple[str | None, float, dict[str, float]]:
    a = answers.get(name) or {}
    probs = {k: float(v) for k, v in (a.get("probabilities") or {}).items()}
    return a.get("choice"), float(a.get("confidence") or probs.get(a.get("choice"), 0.0)), probs


def probability(answers: dict, name: str) -> float:
    a = answers.get(name) or {}
    for key in ("noul", "probability"):          # Jev answers {"noul": p}; keep the other spelling working
        if isinstance(a.get(key), (int, float)):
            return float(a[key])
    if "probability" in a:
        return float(a["probability"])
    probs = a.get("probabilities") or {}
    if "true" in probs:
        return float(probs["true"])
    return 1.0 if a.get("choice") in ("true", True) else 0.0
