"""Probe OpenRouter behaviour for z-ai/glm-5.3-flash that matters to Stagehand/Browser-Use:
  1. can reasoning be turned off?           (reasoning.enabled=false, reasoning_effort='none')
  2. what happens when json_schema is sent but the request is pinned to a provider whose
     endpoint does not list structured_outputs / response_format (no require_parameters)?
  3. does require_parameters=true refuse such a pinned provider?
Uses the small captured Stagehand act request (the-internet.herokuapp.com/inputs, ~0.9k tokens).
Usage: python routing_probe.py <data_dir> <out_jsonl>
"""
import json
import os
import sys
import time
from pathlib import Path

import httpx

DATA, OUT = Path(sys.argv[1]), Path(sys.argv[2])
KEY = os.environ.get("OPENROUTER_API_KEY") or next(
    l.split("=", 1)[1].strip().strip('"\'') for l in open(os.environ.get("ENV_FILE", ".env")) if l.startswith("OPENROUTER_API_KEY="))
cap = json.loads((DATA / "captures" / "09_inputs_act_Act.json").read_text())
c = cap["messages"][0]["content"]
MSGS = [{"role": "system", "content": cap["system_prompt"]}, {"role": "user", "content": c["text"] if isinstance(c, dict) else c}]
RF = {"type": "json_schema", "json_schema": {"name": cap["name"], "strict": True, "schema": cap["schema"]}}

PROBES = [
    ("reasoning_enabled_false", {"reasoning": {"enabled": False}, "response_format": RF}),
    ("reasoning_effort_none", {"reasoning": {"effort": "none"}, "response_format": RF}),
    ("no_reasoning_param_default", {"response_format": RF, "provider": {"require_parameters": True}}),
    ("pin_ZAI_no_require", {"reasoning": {"effort": "low"}, "response_format": RF, "provider": {"order": ["z-ai"], "allow_fallbacks": False}}),
    ("pin_ZAI_require", {"reasoning": {"effort": "low"}, "response_format": RF, "provider": {"order": ["z-ai"], "allow_fallbacks": False, "require_parameters": True}}),
    ("pin_Relace_no_require", {"reasoning": {"effort": "low"}, "response_format": RF, "provider": {"order": ["relace"], "allow_fallbacks": False}}),
    ("pin_Novita_no_require", {"reasoning": {"effort": "low"}, "response_format": RF, "provider": {"order": ["novita"], "allow_fallbacks": False}}),
    ("json_object_only", {"reasoning": {"effort": "low"}, "response_format": {"type": "json_object"}, "provider": {"require_parameters": True}}),
]

with OUT.open("a") as fh:
    for name, extra in PROBES:
        body = {"model": "z-ai/glm-5.3-flash", "messages": MSGS, "max_tokens": 6000, "usage": {"include": True}, **extra}
        t0 = time.time()
        r = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=body, timeout=180,
                       headers={"Authorization": f"Bearer {KEY}"})
        d = r.json()
        ch = (d.get("choices") or [{}])[0]
        u = d.get("usage") or {}
        rec = {"probe": name, "status": r.status_code, "latency_s": round(time.time() - t0, 2), "provider": d.get("provider"),
               "error": d.get("error"), "finish_reason": ch.get("finish_reason"),
               "completion_tokens": u.get("completion_tokens"),
               "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"), "cost": u.get("cost"),
               "content": ((ch.get("message") or {}).get("content") or "")[:500],
               "has_reasoning_text": bool((ch.get("message") or {}).get("reasoning"))}
        fh.write(json.dumps(rec) + "\n")
        print(json.dumps(rec)[:500])
