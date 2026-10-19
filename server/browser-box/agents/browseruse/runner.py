"""One Browser-Use task, in a process of its own, confined to the tab opened for it.

Reads its spec as JSON on stdin (server.py writes it). Appends one JSON line per step to
spec.progress as it goes, so a task killed at its timeout still reports what it did, and writes
the finished run to spec.result. Then exits hard: Browser-Use's own shutdown can hang
(session.stop() never returned when tried), and the parent kills this process anyway.

Confinement. Browser-Use assumes the browser is its own. On a shared Chromium it took over the
first tab it found, which was Jev's (verified), its about:blank watchdog writes into every blank
tab, its downloads watchdog switches the WHOLE browser to downloading into a temp directory, and
its permissions watchdog grants clipboard and notifications to every origin. So, against the
pinned 0.13.10 only:
  - tabs that existed before the task are invisible to it: every page listing filters them out,
  - no CDP session can be opened on one of them, so it cannot navigate, switch to or close them,
  - the downloads watchdog never touches browser-wide download behaviour,
  - no permission is granted (permissions=[]).
`runner.py --self-check` fails unless the version is the pinned one and every patched method
still exists, so an upgrade breaks at startup rather than quietly inside someone's task.
"""
from __future__ import annotations

import asyncio
import functools
import importlib.metadata
import inspect
import json
import os
import sys
import time
from typing import Any

PINNED = "0.13.10"
OPENROUTER = "https://openrouter.ai/api/v1"
FOREIGN: set[str] = set()
# upload_file is the one action that moves this container's files onto the web; save_as_pdf
# writes files nobody collects. Tab switching and closing stay: confinement covers them.
EXCLUDED_ACTIONS = ["upload_file", "save_as_pdf"]
AGENT_OPTIONS = dict(use_vision=False, use_judge=False, max_failures=3, llm_timeout=90, step_timeout=120,
                     calculate_cost=False, directly_open_url=True)
SYSTEM_NOTE = ("This browser reaches only the public web: private, internal and loopback addresses are refused "
               "inside the browser itself. If a page is refused or blocked, say so in your final answer instead of "
               "retrying it.")


def llm_options(spec: dict) -> dict:
    """browser_use sends reasoning_effort only for models on its own reasoning list, which has no
    OpenRouter models, so name ours. Without it the model reasons at full effort on every step."""
    return dict(model=spec["model"], reasoning_models=[spec["model"]],
                reasoning_effort=spec.get("reasoning_effort") or "low")


def confine() -> None:
    from browser_use.browser.session import BrowserSession
    from browser_use.browser.session_manager import SessionManager
    from browser_use.browser.watchdogs.downloads_watchdog import DownloadsWatchdog

    version = importlib.metadata.version("browser-use")
    if version != PINNED:
        raise RuntimeError(f"browser-use {version} is installed; the confinement here is written against {PINNED}")
    patched = [(SessionManager, "get_all_page_targets"), (BrowserSession, "_cdp_get_all_pages"),
               (BrowserSession, "get_or_create_cdp_session"), (BrowserSession, "get_target_id_from_tab_id"),
               (BrowserSession, "on_CloseTabEvent"), (BrowserSession, "_cdp_close_page"),
               (DownloadsWatchdog, "attach_to_target")]
    missing = [f"{owner.__name__}.{name}" for owner, name in patched if not callable(getattr(owner, name, None))]
    if missing:
        raise RuntimeError("Browser-Use changed; these no longer exist: " + ", ".join(missing))

    page_targets = SessionManager.get_all_page_targets

    @functools.wraps(page_targets)
    def visible_page_targets(self):
        return [t for t in page_targets(self) if t.target_id not in FOREIGN]

    cdp_pages = BrowserSession._cdp_get_all_pages

    @functools.wraps(cdp_pages)
    async def visible_cdp_pages(self, *args, **kwargs):
        return [t for t in await cdp_pages(self, *args, **kwargs) if t.get("targetId") not in FOREIGN]

    session_for = BrowserSession.get_or_create_cdp_session

    @functools.wraps(session_for)
    async def own_session_for(self, target_id=None, focus=True):
        if target_id in FOREIGN:
            raise ValueError("that tab belongs to another client of this browser")
        return await session_for(self, target_id, focus)

    target_for_tab = BrowserSession.get_target_id_from_tab_id

    @functools.wraps(target_for_tab)
    async def own_target_for_tab(self, tab_id):
        found = await target_for_tab(self, tab_id)
        if found in FOREIGN:
            raise ValueError(f"No TargetID found ending in tab_id=...{tab_id}")
        return found

    on_close = BrowserSession.on_CloseTabEvent

    @functools.wraps(on_close)
    async def close_own_only(self, event):
        if event.target_id in FOREIGN:
            return None
        return await on_close(self, event)

    close_page = BrowserSession._cdp_close_page

    @functools.wraps(close_page)
    async def close_own_page_only(self, target_id):
        if target_id in FOREIGN:
            raise ValueError("that tab belongs to another client of this browser")
        return await close_page(self, target_id)

    @functools.wraps(DownloadsWatchdog.attach_to_target)
    async def no_browser_wide_downloads(self, target_id):
        return None

    SessionManager.get_all_page_targets = visible_page_targets
    BrowserSession._cdp_get_all_pages = visible_cdp_pages
    BrowserSession.get_or_create_cdp_session = own_session_for
    BrowserSession.get_target_id_from_tab_id = own_target_for_tab
    BrowserSession.on_CloseTabEvent = close_own_only
    BrowserSession._cdp_close_page = close_own_page_only
    DownloadsWatchdog.attach_to_target = no_browser_wide_downloads


def profile(cdp_url: str) -> Any:
    from browser_use import BrowserProfile

    return BrowserProfile(cdp_url=cdp_url, is_local=False, keep_alive=True,
                          permissions=[], accept_downloads=False, auto_download_pdfs=False)


def self_check() -> None:
    confine()
    from browser_use import Agent, Tools

    # With either set, its storage-state watchdog saves the SHARED browser's cookies, session
    # logins included, every minute.
    made = profile("ws://127.0.0.1:1/")
    if made.user_data_dir is not None or made.storage_state is not None:
        raise RuntimeError("BrowserProfile now defaults user_data_dir or storage_state: cookies would be saved")

    accepted = inspect.signature(Agent.__init__).parameters
    unknown = [k for k in (*AGENT_OPTIONS, "register_new_step_callback", "extend_system_message") if k not in accepted]
    if unknown:
        raise RuntimeError("Agent no longer takes: " + ", ".join(unknown))
    actions = set(Tools().registry.registry.actions)
    gone = [a for a in EXCLUDED_ACTIONS if a not in actions]
    if gone:
        raise RuntimeError("these actions to exclude no longer exist, so excluding them would do nothing: " + ", ".join(gone))
    print("self-check ok", flush=True)


def _clip(value: Any, limit: int = 200) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, dict):
        return {k: _clip(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v, limit) for v in value[:10]]
    return value


def describe(action: Any) -> dict:
    data = action.model_dump(exclude_unset=True, exclude_none=True)
    if isinstance(data.get("done"), dict):  # its text is the answer, reported once at the top
        data["done"] = {k: v for k, v in data["done"].items() if k == "success"}
    return _clip(data)


def _tokens(usage: Any) -> dict | None:
    if not usage:
        return None
    return {"prompt": usage.total_prompt_tokens, "completion": usage.total_completion_tokens,
            "cached": usage.total_prompt_cached_tokens}


async def run(spec: dict) -> dict:
    FOREIGN.update(spec["foreign_tabs"])
    confine()
    from browser_use import Agent, BrowserSession, ChatOpenAI, Tools

    llm = ChatOpenAI(**llm_options(spec), base_url=OPENROUTER, api_key=os.environ["OPENROUTER_API_KEY"])
    session = BrowserSession(browser_profile=profile(spec["cdp_url"]))
    await session.start()
    # It focuses the first tab it can see, and the only one it can see is the one opened for it.
    if session.agent_focus_target_id != spec["own_tab"]:
        await session.get_or_create_cdp_session(spec["own_tab"], focus=True)

    holder: dict[str, Any] = {}

    async def on_step(state: Any, output: Any, number: int) -> None:
        usage = await holder["agent"].token_cost_service.get_usage_summary()
        row = {"step": number, "url": getattr(state, "url", None),
               "actions": [describe(a) for a in (getattr(output, "action", None) or [])],
               "next_goal": _clip(getattr(output, "next_goal", "") or ""), "tokens": _tokens(usage)}
        with open(spec["progress"], "a") as fh:
            fh.write(json.dumps(row) + "\n")

    agent = Agent(task=spec["goal"], llm=llm, browser_session=session,
                  tools=Tools(exclude_actions=EXCLUDED_ACTIONS), register_new_step_callback=on_step,
                  extend_system_message=SYSTEM_NOTE, **AGENT_OPTIONS)
    holder["agent"] = agent
    history = await agent.run(max_steps=spec["max_steps"])

    steps = []
    for number, item in enumerate(history.history, 1):
        out = item.model_output
        results = item.result or []
        row = {"step": number, "url": getattr(item.state, "url", None) if item.state else None,
               "actions": [describe(a) for a in (out.action if out else [])],
               "next_goal": _clip(getattr(out, "next_goal", "") or "") if out else ""}
        done = [_clip(r.extracted_content) for r in results if r.extracted_content and not r.is_done]
        failed = [_clip(r.error) for r in results if r.error]
        if done:
            row["result"] = done
        if failed:
            row["error"] = failed
        steps.append(row)
    success = history.is_successful()
    status = "done" if success else ("failed" if history.is_done() else "incomplete")
    urls = [u for u in history.urls() if u]
    return {
        "status": status, "success": success, "answer": history.final_result(),
        "steps": steps, "urls": list(dict.fromkeys(urls)), "final_url": urls[-1] if urls else None,
        "tokens": _tokens(history.usage), "errors": [_clip(e) for e in history.errors() if e][-3:],
    }


def main() -> None:
    if sys.argv[1:] == ["--self-check"]:
        try:
            self_check()
        except Exception as exc:
            print(f"self-check failed: {type(exc).__name__}: {exc}", flush=True)
            os._exit(1)
        os._exit(0)
    asyncio.run(finish(json.loads(sys.stdin.read())))


async def finish(spec: dict) -> None:
    """Write the result and leave from inside the loop: asyncio.run's own teardown waits on
    Browser-Use's background tasks, which is where its shutdown hangs."""
    started = time.monotonic()
    try:
        result = await run(spec)
    except BaseException as exc:  # a result, not a traceback: the parent reports it
        result = {"status": "error", "errors": [f"{type(exc).__name__}: {exc}"[:400]]}
    result["agent_seconds"] = round(time.monotonic() - started, 1)
    with open(spec["result"], "w") as fh:
        json.dump(result, fh)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
