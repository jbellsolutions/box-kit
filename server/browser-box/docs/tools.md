# Tools

Seven tools, plus `GET /api/v1/tools` to list what this box currently offers. `fetch` and
`status` are always listed. The rest are listed only when what they need is configured
(`gateway/gateway/tools.py:OPTIONAL`):

| tool | listed when |
|---|---|
| `read` | `BROWSER_USE_API_KEY` or `BROWSERBASE_API_KEY` is set |
| `session` | `BROWSER_USE_API_KEY` is set |
| `act` | `BROWSER_USE_API_KEY` and `TYPESAFE_API_KEY` are both set |
| `computer` | `ORGO_API_KEY` is set |
| `task` | at least one surface is configured: `browser` needs `BROWSER_USE_API_KEY` plus agent-browseruse (`BB_BROWSERUSE_URL`, `BB_BROWSERUSE_TOKEN`); `computer` needs Orgo |

If a tool is listed, it works; if it can't work right now (an outage at the provider, say),
`status` says so in one line with the reason. Which tool to pick, and what each emergency does, is
in [choosing.md](choosing.md).

Arguments below are taken from `docs/openapi.json` / `gateway/gateway/tools.py`.

## fetch

Plain HTTP GET, no browser. Fastest and free. Use first for anything server-rendered — news
sites, docs, APIs, RSS. Do not use when the page needs JavaScript, is behind a login, or blocks
bots.

- **Arguments**: `url` (string, required) — a public `http(s)` URL.
- **Result**: `text`, `text_chars`, `status_code`, `final_url`.
- **Refusals**: the URL (or where a redirect in its chain lands) is not `public_web` —
  loopback, private, link-local, or unresolvable.

## read

Open a URL in a hosted browser; return its rendered text, links, and optionally a screenshot. Use
when `fetch` returned nothing useful because the page needs JavaScript. Do not use when `fetch`
already answered, or the task needs clicking/typing rather than reading. Each read gets a browser
of its own (Browser Use Cloud), so reads run side by side with no queue on this host.

- **Arguments**:
  - `url` (string, required)
  - `screenshot` (boolean, default `false`) — a full-page JPEG, taken from the same page load the
    text came from. Not available on Browserbase.
  - `delay_ms` (integer, 0–15000) — wait this long after load for late content.
  - `engine` (enum `auto` | `browseruse` | `browserbase`, default `auto`) — `auto` is Browser Use,
    with Browserbase as the emergency lane when it is configured. `browseruse` never falls back.
    `browserbase` goes straight there. See
    [choosing.md](choosing.md#browserbase-the-emergency-lane).
  - `session_id` (string) — read in that session's browser (a tab of its own; `act`'s tab is left
    where it was). The session is fresh and logged out, like every browser here. Hosted engine only
    (`engine` `auto` or `browseruse`).
  - `region` (enum `us-west-2` | `us-east-1` | `eu-central-1` | `ap-southeast-1`) — Browserbase only;
    implies `engine="browserbase"`.
- **Result**: `engine` (`browseruse` | `browserbase`) and, on Browser Use, `browser_seconds`. Then
  `text`, `text_chars`, `title`, `final_url`, `links` (up to 50), `status_code` (null on
  Browserbase), and when asked for and available: `screenshot_media_type`, `screenshot_bytes`,
  `screenshot_base64` (rendered as a real MCP image block, not text, by the server). On
  Browserbase a requested screenshot is not taken and `screenshot_note` says so.
- **On a fallback** the result also carries `fallback_reason` (`engine_down` | `blocked` |
  `no_browser_use` | `region` | `requested`), `why`, `region` and `browserbase_seconds`; for
  `engine_down` also `engine_error`, Browser Use's own error. If a page looked blocked and
  Browserbase failed too, the Browser Use result comes back with `fallback_error`.
- **Refusals**: the same URL-scope refusal as `fetch`; a page that ends off the public web;
  Browser Use not configured, over its monthly cap (`BB_BROWSERUSE_MONTHLY_USD`), out of credit or
  at the plan's browser limit and no Browserbase to fall back to (with Browserbase, the error names
  both failures); a `session_id` whose session is busy.

## session

A browser of your own that stays open between calls, so `act` can work a page step by step and
several agents can each drive their own at once. Every session is a fresh, logged-out browser, and
it is forgotten when it closes. The box keeps no logins and never creates, opens, reads or deletes a
Browser Use profile (`cloud.py` refuses any API path containing "profile"); logged-in work belongs
to a tool built for it. Don't create a session for a one-off public read: `read` opens and closes its
own browser, and `act` without a `session_id` uses one shared scratch browser.

- **Arguments**:
  - `action` (enum `create` | `list` | `release`, required)
  - `session_id` (string) — `release`: the session to close; without it, `act`'s scratch browser
  - `name` (string, up to 80) — `create` only: a label for your own bookkeeping
- **Result**:
  - `create` → `session_id`, `name`, `live_url`, `engine`, `note`. Pass `session_id` to `act` and
    `read`. `live_url` is a view of that browser and lets whoever holds it drive it: keep it to
    yourself.
  - `list` → `sessions`: array of `{session_id, name, browser_open, engine}`.
  - `release` → `released`, `session_id`, `was_open`. Closes the browser; the session is gone.
- **Refusals**: the session is busy (another call is using its browser; waits up to
  `BB_SESSION_WAIT_SECONDS`, default 30); an unknown session id, which includes one that was
  released or closed when idle (create a new one); Browser Use not configured, over a cap or
  unavailable and no Browserbase to open the browser on. An idle session's browser closes itself
  after `BB_SESSION_IDLE_SECONDS` (default 300), and the session with it.

## act

Drive the browser step by step in plain words you plan (`"open https://…"`, `"click the
Pricing link"`, `"type 'x' into the search box and press enter"`, `"scroll down"`, `"go
back"`). Jev — a decision model that never writes text — picks which element on the page each
step means (~0.3 s; page loads dominate the real time), and the gateway does the step over CDP. Up
to 4 steps joined by "then"/"and" run in order. Prefer `act` over `task` whenever you can say the
steps: measured 10–60x faster and as-or-more accurate on all but one job (see
[benchmark.md](benchmark.md)). Only listed when `BROWSER_USE_API_KEY` and `TYPESAFE_API_KEY` are set.

- **Arguments** (exactly one of `command`, `pick`, `confirm`):
  - `command` (string) — one step, or up to 4 joined by then/and.
  - `pick` (string) — answers a `needs_clarification`, with one option's `pick` value.
  - `confirm` (boolean) — answers a `needs_confirmation`.
  - `read_page` (boolean, default `false`) — also return the page's readable text afterwards.
  - `session_id` (string) — work in that session's browser (see `session`). Without it `act` uses
    one shared scratch browser, forgotten when it closes after a few idle minutes. Every browser
    is fresh and logged out. The tab stays where you left it between calls.
- **Result**: `status` (`done` | `failed` | `needs_clarification` | `needs_confirmation`),
  `steps` (what ran and how each went, including each step's `did` and, when applicable,
  `decided_by`/`decision_ms`), `url`, `title`, `session_id`, `engine`, `live_url`, and
  `text`/`text_chars` when `read_page=true`. `engine` is `browserbase` when the browser fell back
  to the emergency lane.
- **Refusals**: `needs_clarification` (Jev is unsure which element — answer with
  `act(pick=…)`); `needs_confirmation` (the step looks hard to undo: buy, delete, send, post —
  answer with `act(confirm=true|false)`; risk is judged from your words and again from the element
  Jev picked); a step that led off the public web is reported `refused` and the tab goes to
  `about:blank`; a question that expired (two minutes) must be re-asked with a new command; the
  session is busy; Browser Use or the decision model unavailable.

## computer

Drive an Orgo cloud computer: a full Linux desktop with a browser and a shell, running **off**
this box. The caller is the eyes — screenshot, decide, act, screenshot again. Coordinates are
pixels in the most recent screenshot. Do not use for a page that `fetch`/`read` can answer —
this is a whole billed computer. Only listed when `ORGO_API_KEY` is set.

- **Arguments**:
  - `action` (enum `screenshot` | `click` | `type` | `key` | `scroll` | `bash` | `start` |
    `stop`, required)
  - `x`, `y` (integer) — required for `click`/`scroll`
  - `button` (enum `left` | `right` | `middle`, default `left`)
  - `double` (boolean, default `false`)
  - `text` (string) — for `type`
  - `key` (string) — for `key`: a key or a `+`-joined combination, e.g. `"Return"`, `"ctrl+c"`
  - `direction` (enum `up` | `down` | `left` | `right`, default `down`) — for `scroll`
  - `amount` (integer, 1–50, default 3) — for `scroll`
  - `command` (string) — for `bash`
  - `screenshot_after` (boolean, default `false`) — return a screenshot after the action in the
    same call
  - `computer_id` (string) — omit to use the pinned or running computer
- **Result**: `action`, `computer_id`, `computer`, `ok`, plus action-specific fields (`output`
  for `bash`; `screenshot_base64`/`screenshot_media_type`/`screenshot_bytes`/`width`/`height`
  when a screenshot is returned); `note` on `start`/`stop`.
- **Refusals**: `LaneBusy` on that computer's own lane (one driver per desktop; a computer never
  blocks the browsers); Orgo errors surface as `OrgoUnavailable`.
- **Billing note**: a computer bills until stopped — there is no auto-stop. Call
  `action="stop"` when finished.

## task

Hand a whole goal to an agent and wait for its answer: `surface="browser"` runs it via Browser-Use
on a hosted browser the gateway opens for that task; `surface="computer"` runs it on an Orgo desktop
via Orgo's own computer-use agent. Use when you'd rather not plan the steps yourself. Do not use when one
`fetch`/`read` answers it, or when you can drive the steps with `act`/`computer` — that is
faster, cheaper, and you see every step. Only surfaces this box has configured appear in the
`surface` enum; if only one is configured, `surface` defaults to it.

- **Arguments**:
  - `goal` (string, required to start a task) — what to achieve and what to report back.
  - `cancel` (boolean) — browser surface only: stop the running task instead of starting one.
  - `surface` (enum, narrowed to configured surfaces)
  - `max_steps` (integer, 1–50, default 25) — browser surface only: the most model steps it may take.
  - `timeout_seconds` (integer, 30–1800) — hitting it stops the run. Default 300 on the browser
    (max 900), 600 on a computer.
  - `computer_id` (string) — computer surface only.
- **Result, `surface="browser"`**: `surface`, `engine` (`browseruse` | `browserbase`), `status`
  (`done` | `failed` | `incomplete` | `timed_out` | `cancelled` | `stopped`), `answer`, `steps`,
  `urls`, `final_url`, `tokens`, `estimated_cost_usd`. Its hosted browser is stopped when it ends,
  so to look at the last page again, `read` the `final_url`. Several tasks run at once. An MCP
  client's cancel notification cannot reach a stateless POST, so a task runs to its timeout unless
  `task(cancel=true)` stops it (that stops every running browser task); a stopped task still
  reports what it did. Tasks take no `session_id`: each runs in a fresh, logged-out browser of its
  own, with no cap of ours on how many run at once (`BB_BROWSERUSE_PARALLEL` defaults to 0; the
  agent container's memory, `BROWSERUSE_MEMORY`, is the bound, at about 100-300 MB per running
  task). If Browser Use cannot open a browser, the task runs on Browserbase and the result carries
  `engine: "browserbase"` and `fallback_reason`.
- **Result, `surface="computer"`**: `surface`, `computer_id`, `computer`, plus Orgo's result
  fields. Orgo ignores `max_steps` (fixed 250-step loop); `timeout_seconds` is the real bound
  and closes the stream when hit.
- **Refusals**: `surface` not configured on this box; Browser Use not configured, over a cap or
  unavailable (with no Browserbase fallback for that task); `LaneBusy` on a computer surface.

## status

What is running, what is healthy, and what the last calls cost. Call this when a tool fails,
before assuming a capability is missing — it reports a down component as down, with the reason,
rather than raising.

- **Arguments**: none.
- **Result**: `components` (one entry per part of the box — browser-use cloud, browserbase, the
  decision model, the browser-use agent, orgo — each with `up` and a `detail`; one that is not
  configured says so and what to set), `tools_working_now`, `tools_unavailable` (with `reason`,
  and `surface` for a partially-down `task`), `recent_calls` (last 10), and
  `model_spend_recent_usd` when any recent call reported cost.

## act vs task: measured

Five jobs, each run 3 times through `act` and through `task(surface="browser")` (Browser-Use
with `z-ai/glm-5.3-flash`), in one browser on the retired Steel engine (2026-09-23; raw rows in
[`bench/results-2026-09-23.json`](../bench/results-2026-09-23.json)). See
[benchmark.md](benchmark.md) for method and full discussion.

| job | via | success | median s | caller turns | agent steps | model cost (median) | Steel peak |
|---|---|---|---|---|---|---|---|
| search a site, open the top result | act | 0/3 | 3.8 | 3 | 3 | caller's | 1219 MiB |
| search a site, open the top result | task | 2/3 | 126.8 | 1 | 4 | $0.0059 | 1355 MiB |
| fill a form, stop before submit | act | 3/3 | 4.7 | 3 | 7 | caller's | 1104 MiB |
| fill a form, stop before submit | task | 3/3 | 118.6 | 1 | 5 | $0.0052 | 1155 MiB |
| paginate and collect | act | 3/3 | 2.2 | 3 | 3 | caller's | 1154 MiB |
| paginate and collect | task | 3/3 | 37.0 | 1 | 4 | $0.0042 | 1206 MiB |
| state across pages (a cookie, standing in for a login) | act | 3/3 | 0.5 | 2 | 2 | caller's | 984 MiB |
| state across pages | task | 1/3 | 31.1 | 1 | 2 | $0.0026 | 1111 MiB |
| JS-heavy SPA (TodoMVC React) | act | 3/3 | 3.0 | 3 | 4 | caller's | 1164 MiB |
| JS-heavy SPA | task | 0/3 | 300 (timeout) | 1 | 2 | $0.0064 | 1129 MiB |

**Which to use:** `act` whenever you can say the steps — 10–60x faster and won or tied every
job but one. `task` is for a goal you cannot break into steps, or when the caller should not
spend its own turns. Read its answer with care.

## Two doors, one set of tools

MCP (`/mcp`, streamable HTTP) and HTTP/JSON both call the same handlers with the same token —
no privileged back door that could drift from what agents see.

### MCP

```bash
claude mcp add --transport http browser-box "$BROWSER_BOX_URL/mcp" \
  --header "Authorization: Bearer $BROWSER_BOX_TOKEN"
```

### HTTP/JSON

```
POST /api/v1/<tool>     the tool's arguments as JSON body → its result as JSON
GET  /api/v1/status     status, as a GET
GET  /api/v1/tools      the tools this box offers right now, with their input schemas
GET  /openapi.json      this API, described — no token required (says what exists, not what is up)
```

Status codes, exactly as implemented in `gateway/gateway/rest.py`:

| code | when |
|---|---|
| 200 | the tool ran; its result is the body |
| 422 | the result carries `"error"` — a refusal, or a part of the box that's down — same JSON body |
| 404 | unknown tool name, or a tool this box does not currently offer |
| 400 | the request body is not a JSON object |
| 401 | missing or wrong bearer token |

Examples:

```bash
curl -fsS "$BROWSER_BOX_URL/api/v1/fetch" \
  -H "Authorization: Bearer $BROWSER_BOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

curl -fsS "$BROWSER_BOX_URL/api/v1/status" \
  -H "Authorization: Bearer $BROWSER_BOX_TOKEN"

curl -fsS "$BROWSER_BOX_URL/api/v1/tools" \
  -H "Authorization: Bearer $BROWSER_BOX_TOKEN"

curl -fsS "$BROWSER_BOX_URL/openapi.json"
```
