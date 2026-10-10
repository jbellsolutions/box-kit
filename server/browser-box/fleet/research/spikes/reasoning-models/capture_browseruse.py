"""Capture the exact HTTP bodies Browser-Use 0.13.11 sends to its step model, configured the
way browser-box's agents/browseruse/runner.py does it (ChatOpenAI against OpenRouter,
reasoning_models=[model], reasoning_effort=low, use_vision=False, use_judge=False).

An httpx event hook on the ChatOpenAI http_client writes every request body and the
matching response (provider, usage, finish_reason, content) to <out>/bu_calls.jsonl.
This is the default-routing path (no provider.require_parameters), i.e. what the box does today.

Public test page only (books.toscrape.com). Key read into the process env, never printed.

Usage: python capture_browseruse.py <out_dir> [model] [max_steps] [mode] [task]
  mode "box" (default): ChatOpenAI(base_url=OpenRouter, reasoning_models=[model], reasoning_effort=low),
        exactly what browser-box's runner sends.
  mode "or-off": browser_use ChatOpenRouter with extra_body {reasoning:{enabled:false}, max_tokens:4096,
        provider:{require_parameters:true}} for models whose reasoning can be switched off.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

ENV_FILE = os.environ.get("ENV_FILE", ".env")
CHROME = os.environ["CHROME_BIN"]  # path to a Chrome for Testing binary
OUT = Path(sys.argv[1])
MODEL = sys.argv[2] if len(sys.argv) > 2 else "z-ai/glm-5.3-flash"
MAX_STEPS = int(sys.argv[3]) if len(sys.argv) > 3 else 4
MODE = sys.argv[4] if len(sys.argv) > 4 else "box"
TASK = sys.argv[5] if len(sys.argv) > 5 else ("Go to https://books.toscrape.com/ , open the Poetry category, and report the title "
                                              "and price of the first book listed there.")
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("BROWSER_USE_CLOUD_SYNC", "false")
for line in open(ENV_FILE):
    if line.startswith("OPENROUTER_API_KEY=") and not os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")

SEQ = {"n": 0, "t": {}}


async def on_request(request: httpx.Request) -> None:
    if request.url.path.endswith("/chat/completions"):
        SEQ["n"] += 1
        request.extensions["seq"] = SEQ["n"]
        SEQ["t"][SEQ["n"]] = time.time()
        (OUT / f"bu_request_{SEQ['n']:02d}.json").write_bytes(request.content)


async def on_response(response: httpx.Response) -> None:
    seq = response.request.extensions.get("seq")
    if seq is None:
        return
    await response.aread()
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text[:2000]}
    choice = (data.get("choices") or [{}])[0]
    usage = data.get("usage") or {}
    row = {"seq": seq, "status": response.status_code, "latency_s": round(time.time() - SEQ["t"][seq], 2),
           "provider": data.get("provider"), "model": data.get("model"),
           "finish_reason": choice.get("finish_reason"), "prompt_tokens": usage.get("prompt_tokens"),
           "completion_tokens": usage.get("completion_tokens"),
           "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
           "cost": usage.get("cost"), "content": ((choice.get("message") or {}).get("content") or "")[:4000],
           "error": data.get("error")}
    with open(OUT / "bu_calls.jsonl", "a") as fh:
        fh.write(json.dumps(row) + "\n")


async def main() -> None:
    from browser_use import Agent, BrowserProfile, BrowserSession, ChatOpenAI, Tools
    from browser_use.llm.openrouter.chat import ChatOpenRouter

    client = httpx.AsyncClient(timeout=120, event_hooks={"request": [on_request], "response": [on_response]})
    if MODE == "box":
        llm = ChatOpenAI(model=MODEL, reasoning_models=[MODEL], reasoning_effort="low",
                         base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"],
                         http_client=client)
    else:
        llm = ChatOpenRouter(model=MODEL, api_key=os.environ["OPENROUTER_API_KEY"], http_client=client,
                             extra_body={"reasoning": {"enabled": False}, "max_tokens": 4096,
                                         "provider": {"require_parameters": True}, "usage": {"include": True}})
    session = BrowserSession(browser_profile=BrowserProfile(executable_path=CHROME, headless=True,
                                                            user_data_dir=str(OUT / "profile")))
    agent = Agent(task=TASK,
                  llm=llm, browser_session=session, tools=Tools(exclude_actions=["upload_file", "save_as_pdf"]),
                  use_vision=False, use_judge=False, max_failures=3, llm_timeout=90, step_timeout=120,
                  calculate_cost=False, directly_open_url=True)
    t0 = time.time()
    history = await agent.run(max_steps=MAX_STEPS)
    summary = {"model": MODEL, "mode": MODE, "task": TASK, "wall_s": round(time.time() - t0, 1), "steps": len(history.history),
               "final": history.final_result(), "done": history.is_done(), "errors": [e for e in history.errors() if e]}
    (OUT / "bu_summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, default=str)[:2000])
    await session.kill()
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
