# Architecture

One gateway in front of hosted browsers. This host runs no browser. The gateway is reached two
ways — MCP at `/mcp`, HTTP/JSON at `/api/v1` — both gated by the same bearer token and both
dispatching through the same function, `run_tool` (`gateway/gateway/server.py:67`, used by
`gateway/gateway/rest.py:130`). There is no privileged back door: whatever a tool does for
an MCP client, it does identically for a curl call.

```
  your agent ──MCP over HTTPS──► gateway ──► Browser Use Cloud ──► a hosted Chromium per call (CDP)
                (bearer token)      │ ├─ act ──► Jev (TypeSafe): which element? The gateway does the step
                                    │ ├─ task(browser) ──► agent-browseruse ──► a hosted Chromium of its own
                                    │ ├─ read, act, task fall back ──► Browserbase (emergency lane only)
                                    │ ├─ fetch ──► plain HTTP GET from this host
                                    │ └─ computer / task(computer) ──► Orgo (desktops, off-box)
```

(from the repo README)

## Components

**Browser Use Cloud** — the only main browser lane. A hosted Chromium is opened for each `read`,
each `act` scratch browser, each `task`, and each session's open browser, driven by the gateway
over CDP, and stopped when the call ends. How many run at once is the plan's
`concurrentSessionLimit`, read from the account (and never more than
`BB_BROWSERUSE_MAX_CONCURRENT`); that is the plan's limit, not a lock of ours. Spend is capped
box-side too (`BB_BROWSERUSE_MONTHLY_USD`), counted from Browser Use's own per-browser costs.
Neither the API key nor a CDP URL is ever logged or returned.

**Browserbase** — the emergency lane, and nothing more. It is used only when Browser Use cannot
open a browser, the site blocks it, or the caller asks for it. Every browser is fresh and logged
out, so nothing is lost on it. [choosing.md](choosing.md#browserbase-the-emergency-lane) lists what happens in each
emergency; it is the one place that table lives.

**gateway** (`gateway/gateway/`) — the one thing on this host that talks to the outside world. No
browser, no planning model. It exposes:
- `server.py` — MCP over streamable HTTP at `/mcp`, bearer-gated, plus `/health` (unauthenticated
  liveness only) and `/status` (authenticated). On start it stops browsers a previous gateway
  left running (only ones this box created, by recorded id), and on shutdown it closes every session's browser.
- `rest.py` — the same tools under `/api/v1/<tool>`, `/api/v1/status`, `/api/v1/tools`, and
  `/openapi.json` (no token — it describes what exists, not what is up).
- `tools.py` — the tool cards and their handlers (`HANDLERS`), the logic that decides which tools
  are offered at all (`offered_tools`), `safe_target` (the URL check every tool runs first) and the
  redirect walk `fetch` uses.
- `cloud.py` — the Browser Use Cloud client: opens and stops hosted browsers, enforces the spend
  and concurrency caps.
- `sessions.py` — fresh browsers kept open between calls (below).
- `stepper.py` and `decide.py` — `act`: the step logic and the client for the decision model.
- `browserbase.py` — the Browserbase client, the emergency lane.
- `cdp.py` — a small CDP client, used to read pages and to do `act`'s steps.
- `browseruse.py` — client for agent-browseruse, the agent behind `task(surface="browser")`.
- `orgo.py` — client for Orgo's cloud computers.
- `lock.py` — the lane lock, now used for Orgo computers only (below).
- `security.py` — URL scope classification, shared by every tool's pre-flight.

Both doors call the same handler map and the same `run_tool`, so a refusal, a result shape, or
a bug fix is identical whether the caller used MCP or HTTP/JSON.

**Sessions** (`sessions.py`) — a session is a handle on one fresh, logged-out hosted browser that
stays open between calls, so `act` can work a page step by step and several agents can each have their
own. The box keeps no logins: `cloud.py` refuses any API path containing "profile" before the request is
made and no browser is created with a `profileId`, because the Browser Use account also holds other tools'
logged-in profiles. The actions are `create`, `list` and `release`; a released session, or one
closed when idle, is gone and its id is refused. Each session has its own lock, so there is at most one
open browser per session and calls on one `session_id` wait for each other (`BB_SESSION_WAIT_SECONDS`),
while different sessions run side by side. An idle session's browser closes after
`BB_SESSION_IDLE_SECONDS`, and each is opened with a timeout of `BB_SESSION_MAX_MINUTES`. The `default`
session is `act`'s shared scratch browser, used when no `session_id` is given. If Browser Use cannot open a
session's browser, Browserbase does.

**agent-browseruse**, behind `task(surface="browser")` — Browser-Use (0.13.10, pinned) is an
LLM step loop: given a whole goal, its own step model (`z-ai/glm-5.3-flash` on OpenRouter by
default) decides and executes each step until the goal is done or it times out. It has no Chromium
of its own: for each task the gateway opens a fresh hosted browser (Browser Use, or Browserbase when
Browser Use cannot open one) and hands the agent its CDP address; the browser is stopped when the
task ends. Several tasks run at once, each a child process of about 100-300 MB. `BB_BROWSERUSE_PARALLEL` defaults
to 0, which means no cap of ours; the container's memory (`BROWSERUSE_MEMORY`, default 1200m) is the real
bound. `agents/browseruse/runner.py` still confines each task to the tab opened for it:
tabs that existed first are invisible to it (`visible_page_targets`, `visible_cdp_pages` are
patched to filter them out), it cannot open a CDP session on a foreign tab (`own_session_for`
raises), it cannot close one (`close_own_page_only` raises), its downloads watchdog is disabled,
and it is granted no browser permissions (`permissions=[]`). `confine()` also self-checks the
installed `browser_use` version against the version these patches are written against, and
refuses to run if it drifts. It is a compose profile (`browseruse`), off by default.

**Orgo**, behind `computer` and `task(surface="computer")` — full Linux desktops, entirely
off-box. A self-hosted VNC desktop would cost ~1.5 GB and real CPU on a small VPS, and Orgo
computers get their own named lane (`lock.py`'s `name=` parameter). Only offered when
`ORGO_API_KEY` is set.

## The call flow

1. A client calls MCP (`/mcp`) or POSTs JSON (`/api/v1/<tool>`), with `Authorization: Bearer
   <BB_TOKEN>`.
2. Both doors check the same token (`server.py:_token_matches`) and route through the same
   `HANDLERS` map via `run_tool` (`server.py:67`, `rest.py:130`).
3. `run_tool` catches the "expected" exceptions — `UnsafeUrl`, `LaneBusy`, `ValueError`,
   `CloudUnavailable`, `BrowserbaseUnavailable`, `DecisionUnavailable`, `OrgoUnavailable`,
   `BrowserUseUnavailable` — and turns them into a `{"error": ...}` result rather than a stack
   trace, because a refusal is an answer the calling model must see and adapt to, not a crash.
4. A tool that opens a URL checks it first (`safe_target`): `security.require_public_web` plus a
   DNS check, `require_public_addresses`. `fetch` also walks any redirect chain by hand, one hop
   at a time, re-checking each hop before connecting — because inspecting `response.history`
   afterwards is too late, the request already happened.
5. The gateway opens a hosted browser (Browser Use first). If it cannot, `read`, `act`'s scratch
   browser and a logged-out `task` may use Browserbase. The result says which engine ran, and why if it was the emergency lane.
6. After the page loads, `read` drops a page that landed off the public web, and `act` checks the
   page after each step and sends the tab to `about:blank` if a step led somewhere non-public.
7. The browser is stopped and the result comes
   back as JSON; a screenshot comes back as a real MCP `ImageContent` block (`server.py:render`),
   not base64 text, so a vision-capable caller can actually see it.

## The calling agent is the brain; the box executes

This is the one design correction over the system this repo replaces, which put an LLM loop
inside a tool, in a different body from the hands it was calling. Concretely:

- The gateway itself plans nothing. It classifies URLs, opens browsers, and calls the decision
  model behind `act`; that key (`TYPESAFE_API_KEY`) is the only model key it holds.
- `status`, `fetch`, `read`, `session` need no model at all.
- Even the two tools with a model behind them keep it narrowly scoped:
  - **`act`** — Jev is a decision model, not a planning one. It never generates text, so it
    cannot plan a goal, write a search query, or decide a task is done. It answers "which
    element, given this instruction" in a few hundred milliseconds. **The caller** — the agent
    calling this MCP — plans every step.
  - **`task`** — Browser-Use (surface `browser`) or Orgo's own computer-use agent (surface
    `computer`) *does* run a full LLM step loop: it plans, executes, and judges its own steps
    against the goal it was given. This is the one opt-in exception, and both `status` and the
    tool's own description say plainly that a model is doing the planning here.
- Why the split: Jev replaces the 2–10 s of LLM time a browser agent spends per step just
  finding the button, without taking over what to do next. `task` exists for a goal you'd
  rather not break into steps yourself, at the cost of losing sight of each step and paying a
  model-token bill (`README.md` "act vs task: measured" — see [benchmark.md](benchmark.md)).
