"""B5: the same five jobs through act (the caller plans every step) and through task (Browser-Use
plans them), against the running box, through the real MCP endpoint.

    .venv/bin/python scripts/bench.py [runs per cell, default 3] > bench/results.json

What is measured, per run: success against ground truth fetched independently, wall time of
the tool calls, caller turns (act: one per act call; task: one), agent steps, model cost as
reported, Jev's decisions, and Steel's peak memory while the run was going.

Two things to know before reading the numbers:
- act's wall time does NOT include the caller's own thinking between steps, and its cost does
  not include the caller's tokens: in real use every caller turn is also a model call on the
  caller's side. task's numbers include all of its planning. Caller turns is the column that
  shows the difference.
- This Jev build has no page-read endpoint (Justin's uncommitted work adds one), so after act
  the harness reads act's tab itself over CDP as a stand-in for act(read_page=true). Without
  it a caller would have to re-load the URL with read, which loses in-tab state (a filled form,
  an SPA's todos).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]
TOKEN = next(line.split("=", 1)[1].strip() for line in (ROOT / ".env").open() if line.startswith("BB_TOKEN="))
MCP = os.getenv("BB_MCP", "http://127.0.0.1:8080/mcp")
CDP = os.getenv("BB_STEEL_CDP", "ws://127.0.0.1:3000/")
STEEL_CONTAINER = os.getenv("BB_STEEL_CONTAINER", "browser-box-steel-1")

WIKI_SEARCH = "https://en.wikipedia.org/w/index.php?search=&title=Special%3ASearch&profile=advanced&fulltext=1&ns0=1"
QUERY = "lovelace analytical engine"
TODO = "https://todomvc.com/examples/react/dist/"


# ── the browser, directly (ground truth, cleanup, and the stand-in for act's page read) ──
async def cdp(method: str, params: dict | None = None, session: str | None = None, ws=None):
    async def go(sock):
        await sock.send(json.dumps({"id": 1, "method": method, "params": params or {}, **({"sessionId": session} if session else {})}))
        while True:
            reply = json.loads(await asyncio.wait_for(sock.recv(), 20))
            if reply.get("id") == 1:
                return reply.get("result") or {}
    if ws is not None:
        return await go(ws)
    async with connect(CDP, max_size=None) as sock:
        return await go(sock)


async def pages() -> dict[str, str]:
    listed = await cdp("Target.getTargets")
    return {t["targetId"]: t["url"] for t in listed["targetInfos"] if t["type"] == "page"}


async def evaluate(target: str, expression: str):
    async with connect(CDP, max_size=None) as ws:
        async def call(method, params=None, session=None, mid=[0]):
            mid[0] += 1
            await ws.send(json.dumps({"id": mid[0], "method": method, "params": params or {}, **({"sessionId": session} if session else {})}))
            while True:
                reply = json.loads(await asyncio.wait_for(ws.recv(), 20))
                if reply.get("id") == mid[0]:
                    return reply.get("result") or {}
        session = (await call("Target.attachToTarget", {"targetId": target, "flatten": True}))["sessionId"]
        got = await call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, session)
        await call("Target.detachFromTarget", {"sessionId": session})
        return (got.get("result") or {}).get("value")


async def clear_todos() -> None:
    """TodoMVC keeps its list in localStorage, shared by every tab: start each run empty."""
    made = await cdp("Target.createTarget", {"url": TODO})
    await asyncio.sleep(3)
    await evaluate(made["targetId"], "localStorage.clear(); 1")
    await cdp("Target.closeTarget", {"targetId": made["targetId"]})


class SteelPeak:
    def __init__(self) -> None:
        self.peak = 0.0
        self._on = False

    def _sample(self) -> None:
        while self._on:
            out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", STEEL_CONTAINER],
                                 capture_output=True, text=True).stdout
            m = re.match(r"([\d.]+)(MiB|GiB)", out.strip())
            if m:
                self.peak = max(self.peak, float(m[1]) * (1024 if m[2] == "GiB" else 1))

    def __enter__(self):
        self._on, self.peak = True, 0.0
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._on = False
        self._thread.join()


# ── the caller ─────────────────────────────────────────────────────────────────
class Caller:
    def __init__(self, session: ClientSession) -> None:
        self.s = session

    async def tool(self, name: str, args: dict) -> tuple[dict, float]:
        t0 = time.monotonic()
        res = await self.s.call_tool(name, args, read_timeout_seconds=timedelta(seconds=400))
        return json.loads(res.content[0].text), time.monotonic() - t0

    async def act(self, command: str, run: dict) -> dict:
        """One caller turn per call. A clarification is answered with the likeliest option,
        which is what a caller would do, and costs a turn of its own."""
        out, dt = await self.tool("act", {"command": command})
        run["seconds"] += dt
        run["caller_turns"] += 1
        run["jev_decisions"] += sum(1 for s in out.get("steps") or [] if s.get("decided_by") == "jev")
        while out.get("status") == "needs_clarification":
            best = max(out["options"], key=lambda o: o["probability"])
            run["clarifications"] += 1
            out, dt = await self.tool("act", {"pick": best["pick"]})
            run["seconds"] += dt
            run["caller_turns"] += 1
        if out.get("status") == "needs_confirmation":
            await self.tool("act", {"confirm": False})
            run["caller_turns"] += 1
        run["log"].append({"command": command, "status": out.get("status"), "url": out.get("url"),
                           "did": [s.get("did") for s in out.get("steps") or []],
                           "checks": [s.get("check") for s in out.get("steps") or []]})
        if out.get("status") != "done":
            raise RuntimeError(f"act {command!r} -> {out.get('status')}: {json.dumps(out)[:300]}")
        return out


# ── the five jobs ──────────────────────────────────────────────────────────────
async def truth_search() -> str:
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "browser-box-bench/1.0"}) as client:
        r = await client.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": QUERY, "srlimit": 1, "format": "json"})
    return r.json()["query"]["search"][0]["title"]


async def truth_authors() -> list[str]:
    authors = []
    async with httpx.AsyncClient(timeout=20) as client:
        for page in (1, 2, 3):
            html = (await client.get(f"https://quotes.toscrape.com/page/{page}/")).text
            authors.append(re.search(r'<small class="author"[^>]*>([^<]+)</small>', html)[1].strip())
    return authors


FORM_VALUES = "JSON.stringify(Object.fromEntries([...document.querySelectorAll('input')].map(e => [e.name + (e.type === 'radio' || e.type === 'checkbox' ? ':' + e.value : ''), (e.type === 'radio' || e.type === 'checkbox') ? e.checked : e.value])))"


async def act_search(c: Caller, run: dict, tab: str, truth) -> bool:
    await c.act(f"open {WIKI_SEARCH}", run)
    await c.act(f"type '{QUERY}' into the search box and press enter", run)
    # "click the first search result" picked Wikipedia's red "create this page" suggestion above
    # the results in the dry run; a caller that can see the page names the list it means.
    out = await c.act("click the first article title in the list of search results", run)
    return truth in (out.get("title") or "")


async def act_form(c: Caller, run: dict, tab: str, truth) -> bool:
    await c.act("open https://httpbin.org/forms/post", run)
    await c.act("type 'Test User' into the customer name field then type '555-0100' into the telephone field "
                "then type 'test@example.com' into the e-mail address field", run)
    out = await c.act("click the Medium pizza size then click the Bacon topping then click the Extra Cheese topping", run)
    values = json.loads(await evaluate(tab, FORM_VALUES) or "{}")
    return (out.get("url", "").endswith("/forms/post") and values.get("custname") == "Test User"
            and values.get("custtel") == "555-0100" and values.get("custemail") == "test@example.com"
            and values.get("size:medium") is True and values.get("topping:bacon") is True
            and values.get("topping:cheese") is True and values.get("topping:onion") is False)


async def act_paginate(c: Caller, run: dict, tab: str, truth) -> bool:
    got = []
    for i, command in enumerate(("open https://quotes.toscrape.com/", "click the Next link", "click the Next link")):
        await c.act(command, run)
        got.append(await evaluate(tab, "document.querySelector('.author')?.innerText || ''"))
    run["answer"] = got
    return got == truth


async def act_state(c: Caller, run: dict, tab: str, truth) -> bool:
    await c.act(f"open https://httpbin.org/cookies/set?bench={truth}", run)
    await c.act("open https://httpbin.org/cookies", run)
    text = await evaluate(tab, "document.body.innerText")
    return truth in (text or "")


async def act_spa(c: Caller, run: dict, tab: str, truth) -> bool:
    await c.act(f"open {TODO}", run)
    await c.act("type 'buy milk' into the new todo input and press enter then type 'walk dog' into the new todo input and press enter", run)
    await c.act("click the checkbox next to buy milk", run)
    state = await evaluate(tab, "JSON.stringify({count: document.querySelector('.todo-count')?.innerText, "
                                "done: [...document.querySelectorAll('.todo-list li.completed label')].map(l => l.innerText), "
                                "all: [...document.querySelectorAll('.todo-list li label')].map(l => l.innerText)})")
    state = json.loads(state or "{}")
    run["answer"] = state
    return state.get("done") == ["buy milk"] and sorted(state.get("all") or []) == ["buy milk", "walk dog"] \
        and (state.get("count") or "").startswith("1 item left")


GOALS = {
    "search": f"Go to {WIKI_SEARCH} , search the site for '{QUERY}', open the top search result, and report that article's exact title.",
    "form": ("Open https://httpbin.org/forms/post and fill in the form: customer name 'Test User', telephone '555-0100', "
             "e-mail 'test@example.com', pizza size Medium, toppings Bacon and Extra Cheese. Do NOT submit the form. "
             "Then report the value now in each of those fields."),
    "paginate": "Open https://quotes.toscrape.com/ and, moving with the Next button, report the author of the first quote on pages 1, 2 and 3, in order.",
    "state": "Open https://httpbin.org/cookies/set?bench={token} , then open https://httpbin.org/cookies and report the value of the 'bench' cookie.",
    "spa": f"Open {TODO} , add two todos 'buy milk' and 'walk dog', mark 'buy milk' as completed, then report the exact text of the items-left counter.",
}


def task_ok(job: str, out: dict, truth) -> bool:
    answer = (out.get("answer") or "").lower()
    if out.get("status") != "done":
        return False
    if job == "search":
        return truth.lower() in answer
    if job == "form":
        # submitting posts to https://httpbin.org/post; the form itself lives at /forms/post
        submitted = any(u.rstrip("/") == "https://httpbin.org/post" for u in out.get("urls") or [])
        return all(v in answer for v in ("test user", "555-0100", "test@example.com", "medium", "bacon", "cheese")) and not submitted
    if job == "paginate":
        positions = [answer.find(a.lower()) for a in truth]
        return all(p >= 0 for p in positions) and positions == sorted(positions)
    if job == "state":
        return truth.lower() in answer
    if job == "spa":
        return "1 item left" in answer
    return False


ACT = {"search": act_search, "form": act_form, "paginate": act_paginate, "state": act_state, "spa": act_spa}
NAMES = {"search": "search a site, open the top result", "form": "fill a form, stop before submit",
         "paginate": "paginate and collect", "state": "state across pages (cookie; stand-in for a login)",
         "spa": "JS-heavy SPA (TodoMVC React)"}


async def anchor_act_tab(c: Caller) -> str:
    """Find act's tab and close every other tab, so reads and memory start clean."""
    mark = uuid.uuid4().hex[:8]
    run = {"seconds": 0.0, "caller_turns": 0, "jev_decisions": 0, "clarifications": 0, "log": []}
    await c.act(f"open https://example.com/?bench-anchor={mark}", run)
    tabs = await pages()
    mine = next(t for t, url in tabs.items() if mark in url)
    for t in tabs:
        if t != mine:
            await cdp("Target.closeTarget", {"targetId": t})
    return mine


async def one(c: Caller, job: str, mode: str, tab: str, truth) -> dict:
    run = {"job": job, "mode": mode, "seconds": 0.0, "caller_turns": 0, "jev_decisions": 0, "clarifications": 0, "log": []}
    if job == "spa":
        await clear_todos()
    with SteelPeak() as mem:
        try:
            if mode == "act":
                run["ok"] = await ACT[job](c, run, tab, truth)
            else:
                goal = GOALS[job].format(token=truth) if job == "state" else GOALS[job]
                out, dt = await c.tool("task", {"surface": "browser", "goal": goal, "max_steps": 15, "timeout_seconds": 300})
                run.update(seconds=dt, caller_turns=1, steps=out.get("steps_taken"), cost_usd=out.get("estimated_cost_usd"),
                           status=out.get("status"), answer=(out.get("answer") or "")[:300], ok=task_ok(job, out, truth))
                run.update(urls=out.get("urls"), final_url=out.get("final_url"), agent_errors=out.get("errors"),
                           last_steps=(out.get("steps") or [])[-4:])
                if "error" in out:
                    run["error"] = out["error"]
        except Exception as exc:
            run.update(ok=False, error=str(exc)[:300])
    run["seconds"] = round(run["seconds"], 1)
    run["steel_peak_mib"] = round(mem.peak)
    if mode == "act":
        run["steps"] = sum(len(entry["did"]) for entry in run["log"])
    print(f"{job:9} {mode:4} ok={run['ok']!s:5} {run['seconds']:6.1f}s turns={run['caller_turns']} steps={run.get('steps')} "
          f"cost={run.get('cost_usd')} steel={run['steel_peak_mib']}MiB {run.get('error', '')[:80]}", file=sys.stderr)
    return run


def summarize(rows: list[dict]) -> str:
    lines = ["| job | via | success | median s | caller turns | agent steps | model cost (median) | Jev decisions | Steel peak |",
             "|---|---|---|---|---|---|---|---|---|"]
    for job in ACT:
        for mode in ("act", "task"):
            cell = [r for r in rows if r["job"] == job and r["mode"] == mode]
            if not cell:
                continue
            med = lambda k: statistics.median([r[k] for r in cell if r.get(k) is not None]) if any(r.get(k) is not None for r in cell) else None
            cost = med("cost_usd")
            lines.append(f"| {NAMES[job]} | {mode} | {sum(r['ok'] for r in cell)}/{len(cell)} | {med('seconds'):.1f} | "
                         f"{med('caller_turns'):.0f} | {med('steps') if med('steps') is not None else '—'} | "
                         f"{f'${cost:.4f}' if cost is not None else '— (caller pays)'} | "
                         f"{med('jev_decisions') if mode == 'act' else '—'} | {max(r['steel_peak_mib'] for r in cell)} MiB |")
    return "\n".join(lines)


async def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    truths = {"search": await truth_search(), "paginate": await truth_authors(), "form": None, "spa": None}
    print(f"ground truth: {truths}", file=sys.stderr)
    rows = []
    # a task may run 300 s plus the gateway's margin: the stream must outwait it
    async with streamablehttp_client(MCP, headers={"Authorization": f"Bearer {TOKEN}"}, sse_read_timeout=900) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            c = Caller(session)
            tab = await anchor_act_tab(c)
            for i in range(runs):
                for job in ACT:
                    for mode in (("act", "task") if i % 2 == 0 else ("task", "act")):
                        truth = f"b{uuid.uuid4().hex[:10]}" if job == "state" else truths[job]
                        rows.append(await one(c, job, mode, tab, truth))
    jev_ref = next((line.split("=", 1)[1].strip() for line in (ROOT / ".env").open() if line.startswith("JEV_REF=")), None)
    print(json.dumps({"when": time.strftime("%Y-%m-%d %H:%M"), "runs_per_cell": runs, "jev_ref": jev_ref, "truths": truths,
                      "rows": rows, "table": summarize(rows)}, indent=1))
    print("\n" + summarize(rows), file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
