"""One OpenAI-style tool-calling agent step (the shape Stagehand's operator agent and any
Hermes-native tool loop use; Browser-Use 0.13 itself uses json_schema, not tools).
Context = the real Browser-Use browser_state message captured on books.toscrape.com.
Correct = exactly one call to click with index 347 (the Poetry link).

Usage: python tools_step.py <data_dir> <out_jsonl> <runs> <model[@effort|@off]>,...
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

DATA, OUT, RUNS = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
SPECS = sys.argv[4].split(",")
KEY = os.environ.get("OPENROUTER_API_KEY") or next(
    l.split("=", 1)[1].strip().strip('"\'') for l in open(os.environ.get("ENV_FILE", ".env")) if l.startswith("OPENROUTER_API_KEY="))
bu = json.loads((DATA / "bu_request_01.json").read_text())
user = bu["messages"][1]["content"]
user = user if isinstance(user, str) else "\n".join(p.get("text", "") for p in user)
SYSTEM = ("You are a browser agent. Each turn you receive the browser state with interactive elements "
          "listed as [index]<tag>. Call exactly one tool to make progress on the user request.")
TOOLS = [
    {"type": "function", "function": {"name": "click", "description": "Click an interactive element by its index.",
     "parameters": {"type": "object", "properties": {"index": {"type": "integer"}}, "required": ["index"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "type_text", "description": "Type text into an input by index.",
     "parameters": {"type": "object", "properties": {"index": {"type": "integer"}, "text": {"type": "string"}}, "required": ["index", "text"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "navigate", "description": "Open a URL in the current tab.",
     "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "done", "description": "Finish and report the answer.",
     "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False}}},
]


def run(spec: str, i: int) -> dict:
    model, _, mode = spec.partition("@")
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            "tools": TOOLS, "tool_choice": os.environ.get("TOOL_CHOICE", "required"), "max_tokens": 4000,
            "provider": {"require_parameters": True}, "usage": {"include": True}}
    if mode == "off":
        body["reasoning"] = {"enabled": False}
    elif mode:
        body["reasoning"] = {"effort": mode}
    t0 = time.time()
    r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body, timeout=180,
                   headers={"Authorization": f"Bearer {KEY}"})
    d = r.json()
    rec = {"spec": spec, "tool_choice": body["tool_choice"], "run": i, "status": r.status_code, "latency_s": round(time.time() - t0, 2), "provider": d.get("provider")}
    if r.status_code != 200 or "choices" not in d:
        rec.update(error=str(d.get("error"))[:400], correct=False)
        return rec
    ch = d["choices"][0]
    calls = (ch.get("message") or {}).get("tool_calls") or []
    u = d.get("usage") or {}
    parsed = []
    for c in calls:
        try:
            parsed.append((c["function"]["name"], json.loads(c["function"]["arguments"] or "{}")))
        except Exception:
            parsed.append((c["function"]["name"], "UNPARSABLE:" + str(c["function"].get("arguments"))[:100]))
    rec.update(finish_reason=ch.get("finish_reason"), n_calls=len(calls), calls=parsed, cost=u.get("cost"),
               completion_tokens=u.get("completion_tokens"),
               correct=len(parsed) == 1 and parsed[0][0] == "click" and isinstance(parsed[0][1], dict) and parsed[0][1].get("index") == 347)
    return rec


jobs = [(s, i) for s in SPECS for i in range(RUNS)]
with ThreadPoolExecutor(max_workers=6) as pool, OUT.open("a") as fh:
    for rec in pool.map(lambda j: run(*j), jobs):
        fh.write(json.dumps(rec) + "\n")
        print(json.dumps(rec)[:300])
