"""Browser-Use 0.13.11 spike against self-hosted Steel containers (fleet-spike-browseruse[2]).

No secrets in this file. OPENROUTER_API_KEY is read from the environment only (run.sh loads it
from browser-box/.env into this process's environment and nowhere else). Nothing here prints,
logs or writes a key or an Authorization header.

Subcommands (each prints one JSON line on stdout, then exits hard with os._exit so Browser-Use's
own teardown cannot hang the shell):

  keyusage                 OpenRouter key usage counter (USD), for a before/after spend delta.
  task  --mode baseline|flash|defaults --max-steps N [--history FILE]
                           Real GLM 5.3 Flash run on OpenRouter. Every chat/completions call is
                           captured (kind, latency, tokens, generation id); cost is read back from
                           OpenRouter's /generation endpoint per call (billed, not estimated).
  replay --history FILE [--stub-summary]
                           Agent.load_and_rerun on a saved history. The browser is first parked on
                           example.com so the final URL proves the clicks were re-executed. With
                           --stub-summary the end-of-replay summary call goes to a local stub.
  decider                  Non-generative stand-in behind the BaseChatModel protocol (0 network
                           calls to any model) + a guardrail in register_new_step_callback.
  direct                   NO Agent, NO chat model: get_browser_state_summary -> candidates from
                           selector_map -> one real /api/v1/systemone decision call -> Tools.act.
                           Then a deliberate stale-index click.
  persist --state FILE     storage_state across a Steel session release, with a negative control,
                           the multi-origin localStorage gap, and the init-script clobber test.
  conc --cdp2 URL          two browsers (two Steel containers): sessions in two threads (own loops)
                           and in one loop; then two scripted Agents (no LLM spend) both ways.

Only public test pages: books.toscrape.com, quotes.toscrape.com, example.com.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
from typing import Any

os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")  # also turns off BROWSER_USE_CLOUD_SYNC (config.py)
os.environ.setdefault("BROWSER_USE_SETUP_LOGGING", "false")

import httpx  # noqa: E402

CDP = os.environ.get("SPIKE_CDP", "ws://127.0.0.1:3302/")
STEEL_API = os.environ.get("SPIKE_STEEL_API", "http://127.0.0.1:3302")
OPENROUTER = "https://openrouter.ai/api/v1"
MODEL = os.environ.get("SPIKE_MODEL", "z-ai/glm-5.3-flash")
DECIDERS = ["typesafe/jev-1.13", "perplexity/pplx-decider-v1.1-27b"]
TASK = "On https://books.toscrape.com find the price of the first book in the Poetry category."
TRUTH = "51.77"
TASK2 = ("On https://books.toscrape.com open the Poetry category, open the first book listed there, and report "
         "its UPC and how many copies are in stock.")
TRUTH2 = ("a897fe39b1053632", "22")

CALLS: list[dict] = []      # chat/completions calls (generative)
DECISIONS: list[dict] = []  # /systemone calls (decision models)
LOGS: list[str] = []


class Capture(logging.Handler):
    PAT = re.compile(r"Element index updated|matched at|AI step|Rerun Summary|Status:|failed|Error", re.I)

    def emit(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return
        if self.PAT.search(msg):
            LOGS.append(f"{record.levelname} {record.name}: {msg[:220]}")


def capture_logs():
    h = Capture(level=logging.INFO)
    for name in ("browser_use", "Agent", "BrowserSession"):
        lg = logging.getLogger(name)
        lg.addHandler(h)
        lg.setLevel(logging.INFO)
    logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.INFO)


def classify(body: dict) -> str:
    rf = body.get("response_format") or {}
    schema = ((rf.get("json_schema") or {}).get("schema") or {})
    props = set((schema.get("properties") or {}).keys())
    if "action" in props:
        return "agent_step"
    if "verdict" in props:
        return "judge"
    if "summary" in props and "completion_status" in props:
        return "rerun_summary"
    if not rf:
        return "free_text(extract/compaction/ai_step)"
    return "structured:" + ",".join(sorted(props))[:60]


def http_client() -> httpx.AsyncClient:
    async def on_request(request: httpx.Request) -> None:
        request.extensions["t0"] = time.monotonic()

    async def on_response(response: httpx.Response) -> None:
        req = response.request
        if not req.url.path.endswith("/chat/completions"):
            return
        await response.aread()
        try:
            body = json.loads(req.content or b"{}")
        except Exception:
            body = {}
        try:
            data = response.json()
        except Exception:
            data = {}
        usage = data.get("usage") or {}
        msgs = json.dumps(body.get("messages", []))
        CALLS.append({
            "kind": classify(body),
            "status": response.status_code,
            "seconds": round(time.monotonic() - req.extensions.get("t0", time.monotonic()), 2),
            "id": data.get("id"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "cached_tokens": (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
            "reasoning_effort_sent": body.get("reasoning_effort"),
            "max_completion_tokens_sent": body.get("max_completion_tokens"),
            "request_chars": len(msgs),
            "has_image": "image_url" in msgs,
            "finish": ((data.get("choices") or [{}])[0] or {}).get("finish_reason"),
        })

    return httpx.AsyncClient(timeout=120, event_hooks={"request": [on_request], "response": [on_response]})


def make_llm():
    from browser_use import ChatOpenAI

    # Same shape as browser-box agents/browseruse/runner.py: OpenRouter through ChatOpenAI, the
    # model named in reasoning_models so reasoning_effort is actually sent.
    return ChatOpenAI(model=MODEL, reasoning_models=[MODEL], reasoning_effort="low", base_url=OPENROUTER,
                      api_key=os.environ["OPENROUTER_API_KEY"], http_client=http_client())


def by_kind(rows: list[dict]) -> dict:
    return {k: sum(1 for c in rows if c["kind"] == k) for k in {c["kind"] for c in rows}}


async def costs() -> dict:
    """Billed cost per generation from OpenRouter's /generation endpoint."""
    key = os.environ.get("OPENROUTER_API_KEY")
    total, missing = 0.0, 0
    if not key or not CALLS:
        return {"billed_usd": 0.0 if not CALLS else None, "calls_without_cost": 0}
    await asyncio.sleep(4)
    async with httpx.AsyncClient(timeout=30) as c:
        for call in CALLS:
            if not call.get("id"):
                missing += 1
                continue
            got = None
            for _ in range(8):
                r = await c.get(f"{OPENROUTER}/generation", params={"id": call["id"]},
                                headers={"Authorization": f"Bearer {key}"})
                if r.status_code == 200:
                    got = (r.json().get("data") or {})
                    break
                await asyncio.sleep(3)
            if got is None:
                missing += 1
                continue
            call["billed_usd"] = got.get("total_cost")
            call["provider"] = got.get("provider_name")
            total += float(got.get("total_cost") or 0)
    return {"billed_usd": round(total, 6), "calls_without_cost": missing}


def browser(cdp: str = CDP, **kw):
    from browser_use import Browser

    # Direct kwargs, NOT BrowserSession(browser_profile=BrowserProfile(cdp_url=...)): the wrapper
    # form silently becomes is_local=True (session.py __init__: no direct cdp_url -> is_local=True).
    return Browser(cdp_url=cdp, **kw)


async def steel_release() -> int:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{STEEL_API}/v1/sessions/release")
    await asyncio.sleep(3)
    return r.status_code


def summarize_history(history) -> dict:
    steps = []
    for n, item in enumerate(history.history, 1):
        md = item.metadata
        acts = []
        if item.model_output:
            for a in item.model_output.action:
                d = a.model_dump(exclude_unset=True, exclude_none=True)
                acts.append({k: (str(v)[:120]) for k, v in d.items()})
        steps.append({
            "step": n,
            "seconds": round(md.step_end_time - md.step_start_time, 2) if md else None,
            "url": (item.state.url if item.state else None),
            "actions": acts,
            "errors": [r.error[:160] for r in (item.result or []) if r.error],
        })
    u = history.usage
    return {
        "steps": steps,
        "n_steps": len(history.history),
        "final": history.final_result(),
        "is_done": history.is_done(),
        "success_self_report": history.is_successful(),
        "judgement": (history.judgement() if hasattr(history, "judgement") else None),
        "usage": None if not u else {"prompt": u.total_prompt_tokens, "completion": u.total_completion_tokens,
                                      "cached": u.total_prompt_cached_tokens, "total": u.total_tokens},
    }


async def cmd_keyusage(args) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{OPENROUTER}/key", headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    d = (r.json() or {}).get("data") or {}
    return {"status": r.status_code, "usage_usd": d.get("usage"), "usage_daily_usd": d.get("usage_daily")}


async def cmd_task(args) -> dict:
    from browser_use import Agent

    opts: dict[str, Any] = dict(enable_signal_handler=False)
    if args.mode in ("baseline", "flash"):
        # browser-box AGENT_OPTIONS
        opts.update(use_vision=False, use_judge=False, max_failures=3, llm_timeout=90, step_timeout=120,
                    calculate_cost=False, directly_open_url=True)
    if args.mode == "flash":
        opts["flash_mode"] = True
    b = browser(keep_alive=True)
    task = TASK2 if args.task2 else TASK
    agent = Agent(task=task, llm=make_llm(), browser=b, **opts)
    t0 = time.monotonic()
    history = await asyncio.wait_for(agent.run(max_steps=args.max_steps), timeout=args.timeout)
    wall = round(time.monotonic() - t0, 1)
    if args.history:
        agent.save_history(args.history)
    out = summarize_history(history)
    final = out["final"] or ""
    ok = all(t in final for t in TRUTH2) if args.task2 else TRUTH in final
    out.update(mode=args.mode, task=task, wall_seconds=wall, model=MODEL, correct=ok,
               settings={k: v for k, v in opts.items()})
    out["llm_calls"] = CALLS
    out["llm_calls_by_kind"] = by_kind(CALLS)
    out["llm_seconds_total"] = round(sum(c["seconds"] for c in CALLS), 2)
    out.update(await costs())
    return out


class StubSummary:
    """Local stand-in for the end-of-replay summary call (no network)."""

    model = "stub-summary"
    _verified_api_keys = True
    provider = "stub"
    name = "stub-summary"
    model_name = "stub-summary"

    def __init__(self):
        self.calls = 0

    async def ainvoke(self, messages, output_format=None, **kwargs):
        from browser_use.llm.views import ChatInvokeCompletion

        self.calls += 1
        if output_format is None:
            return ChatInvokeCompletion(completion="replay finished", usage=None)
        return ChatInvokeCompletion(completion=output_format.model_validate(
            {"summary": "replay finished (stub)", "success": True, "completion_status": "complete"}), usage=None)


async def current_url(cdp: str = CDP) -> str | None:
    s = browser(cdp, keep_alive=True)
    await s.start()
    try:
        return await s.get_current_page_url()
    finally:
        pass


async def park(url: str) -> None:
    from browser_use.browser.events import NavigateToUrlEvent

    s = browser(keep_alive=True)
    await s.start()
    ev = s.event_bus.dispatch(NavigateToUrlEvent(url=url))
    await ev
    await asyncio.sleep(1.0)


async def cmd_replay(args) -> dict:
    from browser_use import Agent

    capture_logs()
    await park("https://example.com/")
    url_before = await current_url()
    b = browser(keep_alive=True)
    llm = make_llm()
    stub = StubSummary() if args.stub_summary else None
    agent = Agent(task=TASK2 if args.task2 else TASK, llm=llm, browser=b, use_vision=False, use_judge=False,
                  enable_signal_handler=False)
    t0 = time.monotonic()
    kw = dict(max_retries=2, skip_failures=True, delay_between_actions=0.5, max_step_interval=2.0)
    if stub:
        kw["summary_llm"] = stub
    results = await asyncio.wait_for(agent.load_and_rerun(args.history, **kw), timeout=args.timeout)
    wall = round(time.monotonic() - t0, 1)
    url_after = await current_url()
    out = {
        "wall_seconds": wall,
        "url_before_replay": url_before,
        "url_after_replay": url_after,
        "reexecuted_click_to_poetry": "poetry_23" in (url_after or ""),
        "ended_on_product_page": "a-light-in-the-attic" in (url_after or ""),
        "results": [{"done": r.is_done, "success": r.success, "error": (r.error or "")[:160],
                     "content": (r.extracted_content or "")[:200]} for r in results],
        "stub_summary_calls": stub.calls if stub else None,
        "llm_calls": CALLS,
        "llm_calls_by_kind": by_kind(CALLS),
        "match_logs": LOGS[-30:],
    }
    out["final_text_contains_truth"] = any(TRUTH in (r.extracted_content or "") for r in results)
    out.update(await costs())
    return out


# ── decider behind the BaseChatModel protocol ────────────────────────────────────────────
class ScriptedDecider:
    """Stand-in for a System 1 model behind Browser-Use's BaseChatModel protocol (no network)."""

    model = "scripted-decider"
    _verified_api_keys = True

    def __init__(self, wrong_first: bool = True):
        self.calls = 0
        self.seen_inputs_chars = 0
        self.wrong_first = wrong_first

    @property
    def provider(self) -> str:
        return "scripted"

    @property
    def name(self) -> str:
        return self.model

    @property
    def model_name(self) -> str:
        return self.model

    async def ainvoke(self, messages, output_format=None, **kwargs):
        from browser_use.llm.views import ChatInvokeCompletion

        self.calls += 1
        text = "\n".join(str(getattr(m, "text", None) or getattr(m, "content", "")) for m in messages)
        self.seen_inputs_chars += len(text)
        state = str(getattr(messages[-1], "text", None) or messages[-1].content)
        if "poetry_23" not in state and "Poetry" in state and "price_color" not in text:
            label = "Travel" if self.wrong_first else "Poetry"
            m = re.search(r"\[(\d+)\]<a[^>]*>\s*" + label, state)
            action = {"click": {"index": int(m.group(1))}} if m else {"done": {"text": "no link", "success": False}}
        elif "price_color" not in text or "find_elements" not in text:
            action = {"find_elements": {"selector": "article.product_pod p.price_color", "include_text": True}}
        else:
            prices = re.findall(r"£\s?\d+\.\d\d", text)
            action = {"done": {"text": f"First Poetry book price: {prices[0] if prices else 'not found'}",
                               "success": bool(prices)}}
        parsed = output_format.model_validate({"evaluation_previous_goal": "", "memory": "", "next_goal": "",
                                               "action": [action]})
        return ChatInvokeCompletion(completion=parsed, usage=None)


async def cmd_decider(args) -> dict:
    from browser_use import Agent

    b = browser(keep_alive=True)
    decider = ScriptedDecider()
    swaps: list[str] = []

    async def guardrail(state, output, n):
        # Runs after the "model" answers and BEFORE the actions execute; the same object is executed.
        for i, a in enumerate(output.action):
            d = a.model_dump(exclude_unset=True, exclude_none=True)
            if "click" in d:
                idx = d["click"].get("index")
                node = state.dom_state.selector_map.get(idx)
                label = node.get_all_children_text() if node else ""
                if "Travel" in label:
                    poetry = next((k for k, v in state.dom_state.selector_map.items()
                                   if v.get_all_children_text().strip() == "Poetry"), None)
                    if poetry is not None:
                        output.action[i] = type(a).model_validate({"click": {"index": poetry}})
                        swaps.append(f"step {n}: click {idx} (Travel) -> click {poetry} (Poetry)")

    agent = Agent(task="Open https://books.toscrape.com and report the price of the first Poetry book.",
                  llm=decider, browser=b, use_vision=False, use_judge=False, enable_planning=False,
                  message_compaction=False, enable_signal_handler=False, register_new_step_callback=guardrail)
    t0 = time.monotonic()
    history = await asyncio.wait_for(agent.run(max_steps=6), timeout=args.timeout)
    out = summarize_history(history)
    out.update(wall_seconds=round(time.monotonic() - t0, 1), decider_calls=decider.calls,
               decider_input_chars_total=decider.seen_inputs_chars, guardrail_swaps=swaps,
               correct=TRUTH in (out["final"] or ""), http_calls_to_any_llm=len(CALLS))
    return out


# ── direct: selector_map -> real decision model -> Tools.act, no Agent ──────────────────
def describe(node) -> str | None:
    tag = (node.tag_name or "").lower()
    text = re.sub(r"\s+", " ", (node.get_all_children_text() or "")).strip()
    attrs = node.attributes or {}
    label = text or attrs.get("aria-label") or attrs.get("title") or attrs.get("placeholder") or attrs.get("value") or ""
    if not label:
        return None
    if tag == "a":
        return f'link "{label[:80]}" -> {attrs.get("href", "")[:100]}'
    if tag in ("button", "input", "select", "textarea"):
        return f'{tag} "{label[:80]}"'
    return f'{tag} "{label[:80]}"'


async def decide(state: dict, question: str, command: str, criteria: dict[str, str]) -> dict:
    key = os.environ["OPENROUTER_API_KEY"]
    last = None
    for model in DECIDERS:
        body = {"model": model, "state": state, "questions": {"target": {
            "type": "choice", "instructions": {"question": question, "command": command}, "criteria": criteria}}}
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{OPENROUTER}/systemone", json=body, headers={"Authorization": f"Bearer {key}"})
        ms = round((time.monotonic() - t0) * 1000, 1)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text[:300]}
        row = {"model": model, "status": r.status_code, "ms": ms, "n_options": len(criteria),
               "body_chars": len(json.dumps(body))}
        if r.status_code == 200:
            ans = (data.get("answers") or {}).get("target") or {}
            probs = ans.get("probabilities") or {}
            top = sorted(probs.items(), key=lambda kv: -kv[1])[:3]
            row.update(choice=ans.get("choice"), confidence=ans.get("confidence"), top3=top,
                       usage=data.get("usage"), served_model=data.get("model"), provider=data.get("provider"))
            DECISIONS.append(row)
            return row
        row["error"] = json.dumps(data)[:300]
        DECISIONS.append(row)
        last = row
    return last or {}


def candidates(selector_map: dict, cap: int = 180) -> tuple[dict[str, str], dict]:
    raw = len(selector_map)
    crit: dict[str, str] = {}
    seen: set[str] = set()
    for idx, node in selector_map.items():
        d = describe(node)
        if not d or d in seen:
            continue
        seen.add(d)
        crit[f"e{idx}"] = d
    labelled = len(crit)
    if len(crit) > cap:
        crit = dict(list(crit.items())[:cap])
    crit["none"] = "No element listed here advances the goal"
    return crit, {"selector_map_size": raw, "labelled_unique": labelled, "sent_options": len(crit), "cap": cap}


async def cmd_direct(args) -> dict:
    from browser_use import Tools

    tools = Tools()
    ActionModel = tools.registry.create_action_model()
    T0 = time.monotonic()
    trace: list[str] = []

    def mark(msg: str) -> None:
        line = f"[{time.monotonic() - T0:6.2f}] {msg}"
        trace.append(line)
        print(line, file=sys.stderr, flush=True)

    async def guard(label: str, coro, t: float = 30):
        mark("start " + label)
        try:
            r = await asyncio.wait_for(coro, t)
            mark("ok " + label)
            return r
        except BaseException as exc:
            mark(f"FAIL {label}: {type(exc).__name__}: {str(exc)[:160]}")
            return None

    b = browser(keep_alive=True)
    await guard("start", b.start())
    timeline: list[dict] = []

    async def act(d: dict, label: str):
        t0 = time.monotonic()
        res = await guard(label, tools.act(ActionModel.model_validate(d), browser_session=b, page_extraction_llm=None))
        timeline.append({"act": label, "params": d, "ms": round((time.monotonic() - t0) * 1000),
                         "error": (res.error or "")[:200] if res and res.error else (None if res else "timeout/exception"),
                         "content": ((res.extracted_content or "")[:240]) if res else None})
        return res

    await act({"navigate": {"url": "https://books.toscrape.com/"}}, "navigate (code)")
    t0 = time.monotonic()
    st = await guard("state 1", b.get_browser_state_summary(include_screenshot=False))
    state_ms = round((time.monotonic() - t0) * 1000)
    home_map = dict(st.dom_state.selector_map) if st else {}
    crit, stats = candidates(home_map)
    travel_idx = next((k for k, v in home_map.items() if (v.get_all_children_text() or "").strip() == "Travel"), None)
    goal = "Open the Poetry category of the book catalogue"
    dec = await guard("decide", decide({"command": goal, "page": {"url": st.url if st else "", "title": st.title if st else ""}},
                                       "Which element on the current page should be clicked next to advance the goal? "
                                       "Choose 'none' if no element listed here advances it.", goal, crit)) or {}
    choice = dec.get("choice")
    picked_idx = int(choice[1:]) if choice and choice.startswith("e") else None
    picked_desc = crit.get(choice) if choice else None
    if picked_idx is not None:
        await act({"click": {"index": picked_idx}}, "click (decider choice)")
    await asyncio.sleep(0.5)
    url_after_click = await guard("url after click", b.get_current_page_url())
    res = await act({"find_elements": {"selector": "article.product_pod p.price_color", "include_text": True,
                                        "max_results": 3}}, "find_elements (code)")
    prices = re.findall(r"£\s?\d+\.\d\d", (res.extracted_content or "") if res else "")
    stale = None
    probe = None
    if travel_idx is not None:
        # what does the stale backendNodeId resolve to in the NEW document?
        try:
            cdp = await b.get_or_create_cdp_session()
            r = await cdp.cdp_client.send.DOM.describeNode(params={"backendNodeId": travel_idx}, session_id=cdp.session_id)
            n = r.get("node") or {}
            probe = {"resolves": True, "nodeName": n.get("nodeName"), "attributes": n.get("attributes", [])[:6]}
            js = ("(function(){var a=[...document.querySelectorAll('a')].find(x=>x.textContent.trim()==='Travel');"
                  "if(!a)return null;var r=a.getBoundingClientRect();return [Math.round(r.x),Math.round(r.y)];})()")
            rr = await cdp.cdp_client.send.Runtime.evaluate(params={"expression": js, "returnByValue": True},
                                                            session_id=cdp.session_id)
            probe["travel_xy_on_new_page"] = (rr.get("result") or {}).get("value")
        except Exception as exc:
            probe = {"resolves": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        node = home_map.get(travel_idx)
        pos = getattr(node, "absolute_position", None)
        probe["travel_xy_on_home_page_cached"] = [round(pos.x), round(pos.y)] if pos else None
        await act({"click": {"index": travel_idx}}, "click STALE home-page index (Travel)")
        await asyncio.sleep(0.5)
        stale = {"stale_index": travel_idx, "url_after_stale_click": await guard("url after stale", b.get_current_page_url())}
    st2 = await guard("state 2", b.get_browser_state_summary(include_screenshot=False))
    stale_fresh = (travel_idx in st2.dom_state.selector_map) if (st2 and travel_idx is not None) else None
    return {
        "wall_seconds": round(time.monotonic() - T0, 1),
        "state_capture_ms": state_ms,
        "candidates": stats,
        "decision": dec,
        "picked_index": picked_idx, "picked_desc": picked_desc,
        "url_after_click": url_after_click,
        "first_price": prices[0] if prices else None,
        "correct": bool(prices) and TRUTH in prices[0],
        "stale_index_test": stale,
        "stale_index_probe": probe,
        "travel_index_in_refreshed_map": stale_fresh,
        "timeline": timeline,
        "trace": trace,
        "decision_calls": DECISIONS,
        "decision_cost_usd": round(sum(float((d.get("usage") or {}).get("cost") or 0) for d in DECISIONS), 8),
        "chat_completion_calls": len(CALLS),
    }


# ── persistence ─────────────────────────────────────────────────────────────────────────
SET_JS = """(function(tag,val){document.cookie='fleet_cookie_'+tag+'='+val+'; max-age=86400; path=/';
localStorage.setItem('fleet_ls_'+tag,val); return document.cookie+' | ls='+localStorage.getItem('fleet_ls_'+tag);})"""
GET_JS = """(function(){var o={}; for (var i=0;i<localStorage.length;i++){var k=localStorage.key(i); if(k.indexOf('fleet')===0) o[k]=localStorage.getItem(k);}
var c=document.cookie.split('; ').filter(function(x){return x.indexOf('fleet')===0;});
return JSON.stringify({cookie:c, ls:o});})()"""


async def eval_js(session, js: str) -> Any:
    cdp = await session.get_or_create_cdp_session()
    r = await cdp.cdp_client.send.Runtime.evaluate(params={"expression": js, "returnByValue": True},
                                                   session_id=cdp.session_id)
    return (r.get("result") or {}).get("value")


async def goto(session, url: str) -> None:
    from browser_use.browser.events import NavigateToUrlEvent

    ev = session.event_bus.dispatch(NavigateToUrlEvent(url=url))
    await ev
    await ev.event_result(raise_if_any=True, raise_if_none=False)
    await asyncio.sleep(1.0)


async def stop(s) -> str:
    try:
        await asyncio.wait_for(s.stop(), timeout=30)
        return "stopped"
    except BaseException as exc:
        return f"stop failed: {type(exc).__name__}"


async def read_both(s) -> dict:
    out = {}
    for url in ("https://books.toscrape.com/", "https://quotes.toscrape.com/"):
        await goto(s, url)
        out[url] = json.loads(await eval_js(s, GET_JS))
    return out


async def cmd_persist(args) -> dict:
    out: dict[str, Any] = {}
    if os.path.exists(args.state):
        os.remove(args.state)
    out["release0"] = await steel_release()
    # run 1: write on two origins, ending on books; storage_state path set -> saved on stop()
    s = browser(storage_state=args.state, keep_alive=False)
    await s.start()
    await goto(s, "https://quotes.toscrape.com/")
    out["set_quotes"] = await eval_js(s, SET_JS + "('quotes','v1')")
    await goto(s, "https://books.toscrape.com/")
    out["set_books"] = await eval_js(s, SET_JS + "('books','v1')")
    out["file_before_stop"] = os.path.exists(args.state)
    out["stop1"] = await stop(s)
    st = json.load(open(args.state)) if os.path.exists(args.state) else {}
    out["saved_cookie_names"] = sorted(c["name"] for c in st.get("cookies", []) if c["name"].startswith("fleet"))
    out["saved_origins"] = {o["origin"]: [i["name"] for i in o.get("localStorage", [])] for o in st.get("origins", [])}
    # reset the browser: Steel tears the browser down and relaunches an idle one
    out["release1"] = await steel_release()
    # negative control: no storage_state
    c = browser(keep_alive=True)
    await c.start()
    out["control_after_release"] = await read_both(c)
    out["stop_control"] = await stop(c)
    out["release2"] = await steel_release()
    # run 2: fresh browser + storage_state
    s2 = browser(storage_state=args.state, keep_alive=True)
    await s2.start()
    out["restored"] = await read_both(s2)
    # clobber: write a NEW value on books, reload, read
    await goto(s2, "https://books.toscrape.com/")
    out["set_books_v2"] = await eval_js(s2, SET_JS + "('books','v2')")
    await goto(s2, "https://books.toscrape.com/")
    out["after_reload"] = json.loads(await eval_js(s2, GET_JS))
    # same in a NEW tab (init script was added only on the focused target)
    from browser_use.browser.events import NavigateToUrlEvent
    ev = s2.event_bus.dispatch(NavigateToUrlEvent(url="https://books.toscrape.com/", new_tab=True))
    await ev
    await asyncio.sleep(1.0)
    out["new_tab_read"] = json.loads(await eval_js(s2, GET_JS))
    out["export_storage_state_origins"] = len((await s2.export_storage_state()).get("origins", []))
    return out


async def steel_create(body: dict) -> dict:
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post(f"{STEEL_API}/v1/sessions", json=body)
    d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text[:200]}
    await asyncio.sleep(2)
    return {"status": r.status_code, "id": d.get("id"), "websocketUrl": d.get("websocketUrl"), "body": body}


async def cmd_steelprofile(args) -> dict:
    """Persistence held by the browser host (Steel userDataDir/persist), Browser-Use only drives it."""
    out: dict[str, Any] = {"release0": await steel_release()}
    out["create_A_write"] = await steel_create({"userDataDir": "/tmp/fleet-profile-A"})
    s = browser(keep_alive=True)
    await s.start()
    await goto(s, "https://quotes.toscrape.com/")
    out["set_quotes"] = await eval_js(s, SET_JS + "('quotes','A')")
    await goto(s, "https://books.toscrape.com/")
    out["set_books"] = await eval_js(s, SET_JS + "('books','A')")
    out["flush_wait_s"] = args.flush_wait
    await asyncio.sleep(args.flush_wait)
    out["release1"] = await steel_release()
    out["create_control"] = await steel_create({})
    c = browser(keep_alive=True)
    await c.start()
    out["control_read"] = await read_both(c)
    out["release2"] = await steel_release()
    out["create_A_read"] = await steel_create({"userDataDir": "/tmp/fleet-profile-A"})
    s2 = browser(keep_alive=True)
    await s2.start()
    out["A_read"] = await read_both(s2)
    out["release3"] = await steel_release()
    out["create_B_read"] = await steel_create({"userDataDir": "/tmp/fleet-profile-B"})
    s3 = browser(keep_alive=True)
    await s3.start()
    out["B_read"] = await read_both(s3)
    out["release4"] = await steel_release()
    return out


# ── concurrency: two browsers ─────────────────────────────────────────────────────────────
async def one_session(tag: str, cdp: str, url: str, rounds: int) -> dict:
    t0 = time.monotonic()
    errors: list[str] = []
    s = browser(cdp, keep_alive=True)
    try:
        await s.start()
        for i in range(rounds):
            await s.navigate_to(url if i % 2 == 0 else "https://example.com/")
            st = await s.get_browser_state_summary(include_screenshot=False)
            if not st.dom_state.selector_map and i % 2 == 0:
                errors.append("empty selector map")
    except BaseException as exc:  # record, do not raise
        errors.append(f"{type(exc).__name__}: {str(exc)[:200]}")
    return {"tag": tag, "seconds": round(time.monotonic() - t0, 1), "errors": errors}


async def one_agent(tag: str, cdp: str) -> dict:
    from browser_use import Agent

    t0 = time.monotonic()
    try:
        b = browser(cdp, keep_alive=True)
        agent = Agent(task="Open https://books.toscrape.com and report the price of the first Poetry book.",
                      llm=ScriptedDecider(wrong_first=False), browser=b, use_vision=False, use_judge=False,
                      enable_planning=False, message_compaction=False, enable_signal_handler=False)
        h = await agent.run(max_steps=6)
        return {"tag": tag, "seconds": round(time.monotonic() - t0, 1), "final": h.final_result(),
                "errors": [e[:200] for e in h.errors() if e]}
    except BaseException as exc:
        return {"tag": tag, "fatal": f"{type(exc).__name__}: {str(exc)[:300]}"}


def run_no_teardown(coro):
    """asyncio.run() cancels leftover tasks and closes async generators on exit; Browser-Use's
    background tasks (event bus, CDP websocket reader) make that teardown hang. Run without it."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def run_threads(make) -> dict:
    results: dict[str, Any] = {}

    def worker(tag, coro_factory):
        try:
            results[tag] = run_no_teardown(asyncio.wait_for(coro_factory(), timeout=150))
        except BaseException as exc:
            results[tag] = {"tag": tag, "fatal": f"{type(exc).__name__}: {str(exc)[:300]}"}

    ts = [threading.Thread(target=worker, args=(tag, f)) for tag, f in make()]
    t0 = time.monotonic()
    for t in ts:
        t.start()
    for t in ts:
        t.join(180)
    return {"wall_seconds": round(time.monotonic() - t0, 1), "alive_threads": sum(t.is_alive() for t in ts),
            "results": results}


def cmd_conc(args) -> dict:
    c1, c2 = CDP, args.cdp2
    out: dict[str, Any] = {}
    out["sessions_threads_two_browsers"] = run_threads(lambda: [
        ("A", lambda: one_session("A", c1, "https://books.toscrape.com/", args.rounds)),
        ("B", lambda: one_session("B", c2, "https://quotes.toscrape.com/", args.rounds))])

    async def oneloop_sessions():
        return await asyncio.wait_for(asyncio.gather(
            one_session("A", c1, "https://books.toscrape.com/", args.rounds),
            one_session("B", c2, "https://quotes.toscrape.com/", args.rounds)), timeout=150)

    t0 = time.monotonic()
    try:
        out["sessions_oneloop_two_browsers"] = {"results": run_no_teardown(oneloop_sessions()),
                                                "wall_seconds": round(time.monotonic() - t0, 1)}
    except BaseException as exc:
        out["sessions_oneloop_two_browsers"] = {"fatal": f"{type(exc).__name__}: {str(exc)[:300]}"}

    out["agents_threads_two_browsers"] = run_threads(lambda: [
        ("A", lambda: one_agent("A", c1)), ("B", lambda: one_agent("B", c2))])

    async def oneloop_agents():
        return await asyncio.wait_for(asyncio.gather(one_agent("A", c1), one_agent("B", c2)), timeout=150)

    t0 = time.monotonic()
    try:
        out["agents_oneloop_two_browsers"] = {"results": run_no_teardown(oneloop_agents()),
                                              "wall_seconds": round(time.monotonic() - t0, 1)}
    except BaseException as exc:
        out["agents_oneloop_two_browsers"] = {"fatal": f"{type(exc).__name__}: {str(exc)[:300]}"}

    async def oneloop_agents_same_browser():
        return await asyncio.wait_for(asyncio.gather(one_agent("A", c1), one_agent("B", c1)), timeout=150)

    t0 = time.monotonic()
    try:
        out["agents_oneloop_SAME_browser"] = {"results": run_no_teardown(oneloop_agents_same_browser()),
                                              "wall_seconds": round(time.monotonic() - t0, 1)}
    except BaseException as exc:
        out["agents_oneloop_SAME_browser"] = {"fatal": f"{type(exc).__name__}: {str(exc)[:300]}"}
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    p.add_argument("--mode", default="baseline")
    p.add_argument("--max-steps", type=int, default=8)
    p.add_argument("--history")
    p.add_argument("--state")
    p.add_argument("--stub-summary", action="store_true")
    p.add_argument("--task2", action="store_true")
    p.add_argument("--flush-wait", type=float, default=2.0)
    p.add_argument("--cdp2", default="ws://127.0.0.1:3303/")
    p.add_argument("--rounds", type=int, default=4)
    p.add_argument("--timeout", type=float, default=300)
    p.add_argument("--out")
    args = p.parse_args()
    started = time.monotonic()

    def hard_timeout():  # Browser-Use can hang (e.g. after a failed CDP connect); never hang the shell
        text = json.dumps({"cmd": args.cmd, "fatal": f"hard timeout after {args.timeout + 60:.0f}s",
                           "llm_calls": CALLS, "decision_calls": DECISIONS, "logs": LOGS[-20:]}, default=str)
        if args.out:
            with open(args.out, "w") as fh:
                fh.write(text)
        print(text, flush=True)
        os._exit(3)

    wd = threading.Timer(args.timeout + 60, hard_timeout)
    wd.daemon = True
    wd.start()
    def finish(result: dict) -> None:
        result["cmd"] = args.cmd
        result["process_seconds"] = round(time.monotonic() - started, 1)
        text = json.dumps(result, default=str)
        if args.out:
            with open(args.out, "w") as fh:
                fh.write(text)
        print(text, flush=True)
        sys.stdout.flush()
        os._exit(0)

    def failed(exc: BaseException) -> dict:
        return {"fatal": f"{type(exc).__name__}: {str(exc)[:400]}", "trace": traceback.format_exc()[-1500:],
                "llm_calls": CALLS, "decision_calls": DECISIONS, "logs": LOGS[-20:]}

    if args.cmd == "conc":
        try:
            finish(cmd_conc(args))
        except BaseException as exc:
            finish(failed(exc))
    fn = {"keyusage": cmd_keyusage, "task": cmd_task, "replay": cmd_replay, "decider": cmd_decider,
          "direct": cmd_direct, "persist": cmd_persist, "steelprofile": cmd_steelprofile}[args.cmd]

    async def inside_loop() -> None:
        # Leave from INSIDE the loop (as browser-box's runner does): asyncio.run's own teardown waits
        # on Browser-Use background tasks and can hang forever.
        try:
            result = await fn(args)
        except BaseException as exc:
            result = failed(exc)
        finish(result)

    asyncio.run(inside_loop())


if __name__ == "__main__":
    main()
