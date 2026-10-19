# browser-box

One door to hosted browsers.

A gateway on your own VPS, behind a single MCP endpoint, that hands your agent a hosted browser
when it needs one. Your agent (Claude, or anything else that speaks MCP) is the brain. This box is
the hands. **The host runs no browser:** the browsers are Browser Use Cloud's, one per call, many
at once. Two models can run here, both opt-in: Jev, behind `act`, picks page elements and cannot
write a word; Browser-Use, behind `task(surface="browser")`, is an LLM step loop for when you would
rather hand over a whole goal than plan its steps. Neither decides what you are trying to do.

```
  your agent ──MCP over HTTPS──► gateway ──► Browser Use Cloud ──► a hosted Chromium per call (CDP)
                (bearer token)      │ ├─ act ──► Jev (TypeSafe): which element? The gateway does the step
                                    │ ├─ task(browser) ──► agent-browseruse ──► a hosted Chromium of its own
                                    │ ├─ read, act, task fall back ──► Browserbase (emergency lane only)
                                    │ ├─ fetch ──► plain HTTP GET from this host
                                    │ └─ computer / task(computer) ──► Orgo (desktops, off-box)
```

**Run your own:** a 1 vCPU / 2 GB VPS is enough, since no browser runs on the host. See
[docs/operations.md](docs/operations.md).

| Read next | |
|---|---|
| [CHARTER.md](CHARTER.md) | the rules every agent here follows |
| [AGENTS.md](AGENTS.md) | using the box, and changing this repo |
| [docs/choosing.md](docs/choosing.md) | which tool, and what each emergency does |
| [docs/tools.md](docs/tools.md) | every tool, its arguments and answers; the MCP and HTTP/JSON doors |
| [docs/architecture.md](docs/architecture.md) | how a call flows through the box |
| [docs/operations.md](docs/operations.md) | deploy, update, rotate, troubleshoot |
| [docs/security.md](docs/security.md) | the threat model and what is not covered |
| [docs/integrations.md](docs/integrations.md) | Claude Code, the plugin, Hermes, the two command lines |
| [docs/benchmark.md](docs/benchmark.md) | act vs task, measured |

## Why this exists

The system this replaces had 29 MCP tools, 22 of which could not reach a browser, and a
capability report that said `unverified` and `[]` for providers that were working in the
same minute. It had an LLM loop inside the tool, in a different body from the hands. That
is the failure this repo is shaped to avoid:

- **If a tool is listed, it works.** If it can't work right now, `status` says so in one line, with the reason.
- **No brain in the box by default.** The agent calling the MCP decides. The box executes and
  reports. The one step-planning model here, Browser-Use behind `task`, is opt-in and says so.
- **Few tools.** Each new capability adds one tool, or one surface of one, and only after it is proven end to end.

## Where the browsers come from

This box used to run a browser itself (Steel, a self-hosted Chromium) and was built around that
browser's limit of one session per server. That was Steel's limit,
not requirements, so Steel was replaced rather than obeyed.

| | What it is | Role here |
|---|---|---|
| **Browser Use Cloud** | Hosted Chromium at $0.02 per browser-hour, billed by the minute; many browsers at once, up to the plan's `concurrentSessionLimit` | **The only main lane.** `read`, `session`, `act` and `task` all run on its browsers |
| **Browserbase** | Hosted Chromium, billed in plan hours | **Emergency lane only.** `read`, `act` (any session) and `task` fall back to it when Browser Use cannot open a browser. See [what happens in each emergency](docs/choosing.md#browserbase-the-emergency-lane) |
| **Browser-Use** (the library) | An LLM agent that drives a browser. Needs a browser | `task(surface="browser")`, in the `agent-browseruse` container, driving a hosted browser the gateway opens for each task |
| **Orgo** | Full cloud desktops | `computer` and `task(surface="computer")`, off-box |

Browser Use Cloud (a service that supplies browsers) and Browser-Use (a library that plans steps
inside one) share a name and are different things.

## Start with no subscription

Nothing here needs a monthly plan. The smallest working box is one key:

| Key | What it costs to start | What it turns on |
|---|---|---|
| `BROWSER_USE_API_KEY` (cloud.browser-use.com) | **Pay as you go, no subscription.** $1 of free credit on sign-up with Google, GitHub or Microsoft, no card; then $0.02 per browser-hour, top-ups from $5, credits never expire; 10 browsers at once before any payment | `read`, `session`, `fetch`, `status` |
| `BROWSERBASE_API_KEY` (optional) | **The $0 Free plan** is enough for the emergency lane: 1 browser-hour a month, 3 at once, 15-minute sessions, no CAPTCHA solving or proxies on that plan | Browserbase behind `read`, `act` and `task` when Browser Use cannot open a browser. Set `BB_BROWSERBASE_MONTHLY_HOURS=1` and `BB_BROWSERBASE_MAX_CONCURRENT=3` to match |
| `TYPESAFE_API_KEY` (optional) | Pay per use, about $0.042 per million input tokens; TypeSafe has been invite-first | `act` (with the Browser Use key) |
| `OPENROUTER_API_KEY` (optional) | Pay as you go | `task(surface="browser")`, with the agent-browseruse container |
| `ORGO_API_KEY` (optional) | Orgo's own pricing | `computer`, `task(surface="computer")` |

Prices are the providers' published ones as of 2026-10-19; check their pages before relying on
them. Plus the host: any small VPS, since no browser runs on it (this box is a $12 droplet).

## The tools

| Tool | Does | Backed by | Costs |
|---|---|---|---|
| `fetch` | plain HTTP GET from this host, no browser | gateway | free |
| `read` | open a URL, return text + links + screenshot | Browser Use Cloud; Browserbase as the emergency lane | ~$0.0003 a read |
| `session` | a fresh, logged-out browser that stays open between calls: create / list / release | Browser Use Cloud | browser time while its browser is open |
| `act` | drive the browser in plain-words steps: open, click, type, scroll; asks when unsure, confirms anything risky | Jev + Browser Use Cloud | TypeSafe decisions + browser time |
| `computer` | drive an Orgo cloud desktop: screenshot, click, type, key, scroll, bash, start, stop | Orgo (off-box) | Orgo, per hour |
| `task` | hand a whole goal to an agent: Browser-Use on a hosted browser, or Orgo's computer-use agent on a desktop | Browser-Use + Browser Use Cloud; Orgo (off-box) | model tokens, reported per task, plus browser time; Orgo + model |
| `status` | what is up, what is healthy, what recent calls cost | gateway | free |

A tool is listed only when what it needs is configured:

- `read` needs `BROWSER_USE_API_KEY` or `BROWSERBASE_API_KEY`.
- `session` needs `BROWSER_USE_API_KEY`.
- `act` needs `BROWSER_USE_API_KEY` and `TYPESAFE_API_KEY`, both.
- `computer` needs `ORGO_API_KEY`.
- `task` needs at least one surface. `browser` needs `BROWSER_USE_API_KEY` plus agent-browseruse
  (`BB_BROWSERUSE_URL` + `BB_BROWSERUSE_TOKEN`); `computer` needs Orgo. Its card and its `surface`
  choices list only the surfaces this box has.

A box without Orgo has no computers, and advertising them would be the lie this repo exists to
stop. Screenshots (from `read` and `computer`) come back as real MCP image blocks, so a
vision-capable caller can actually see them rather than receiving base64 as text.

### act vs task: measured, and which to use

Five jobs, each run 3 times through `act` (the caller plans the steps, Jev grounds each one) and
through `task(surface="browser")` (Browser-Use with `z-ai/glm-5.3-flash` plans them). **These were
measured on the retired Steel engine**, in one local browser on a Mac (2026-09-23; Jev `edcbbae`;
raw rows in [`bench/results-2026-09-23.json`](bench/results-2026-09-23.json)). Success is checked
against ground truth fetched separately (the Wikipedia search API, the quotes pages, the live form
and to-do DOM), never against the agent's own claim. They have not been rerun on hosted browsers.

| job | via | success | median s | caller turns | agent steps | model cost (median) | Steel peak |
|---|---|---|---|---|---|---|---|
| search a site, open the top result | act | 0/3 | 3.8 | 3 | 3 | caller's | 1219 MiB |
| search a site, open the top result | task | 2/3 | 126.8 | 1 | 4 | $0.0059 | 1355 MiB |
| fill a form, stop before submit | act | **3/3** | 4.7 | 3 | 7 | caller's | 1104 MiB |
| fill a form, stop before submit | task | 3/3 | 118.6 | 1 | 5 | $0.0052 | 1155 MiB |
| paginate and collect | act | **3/3** | 2.2 | 3 | 3 | caller's | 1154 MiB |
| paginate and collect | task | 3/3 | 37.0 | 1 | 4 | $0.0042 | 1206 MiB |
| state across pages (a cookie, standing in for a login) | act | **3/3** | 0.5 | 2 | 2 | caller's | 984 MiB |
| state across pages | task | 1/3 | 31.1 | 1 | 2 | $0.0026 | 1111 MiB |
| JS-heavy SPA (TodoMVC React) | act | **3/3** | 3.0 | 3 | 4 | caller's | 1164 MiB |
| JS-heavy SPA | task | 0/3 | 300 (timeout) | 1 | 2 | $0.0064 | 1129 MiB |

**Which to use:** `act` whenever you can say the steps. It was 10–60× faster and won or tied
every job but one. `task` is for a goal you cannot break into steps, or when the caller should
not spend its own turns. Read its answer with care.

How to read it:
- **`act`'s seconds leave out the caller's own thinking.** Each caller turn is also a model call
  on the caller's side (2–4 turns per job here), which this harness does not make. Add a few
  seconds per turn for a real agent. It is still far ahead.
- **Search, `act` 0/3: a real Jev grounding miss.** Asked to click "the first article title in
  the list of search results", Jev picked Wikipedia's red *create this page* link above the
  results, three times. The step reports the link as `(page does not exist)`, so a caller that
  reads the step would notice and correct it in one more turn. The harness scores it as a miss.
- **`task`'s misses are the step model.** GLM 5.3 Flash garbled the URL it had to open
  (`http bin .org/co okies`), answered from an invented host, cut its own JSON off at the
  4,096-token limit, and on the SPA tried to reach into a shadow root that does not exist,
  running out of steps or time. A stronger `BB_BROWSERUSE_MODEL` may do better. That was not
  measured here.
- **The first dry run found four Jev defects, fixed before these rounds** (jev-automation
  `feat/steel-cdp`):
  - A tick-box click or a second identical list row counted as "no change", which stopped the
    sequence as stuck.
  - Quoted text was typed lowercase ("test user").
  - Unlabelled row checkboxes were one deduplicated element.
  - Custom-drawn (opacity 0) checkboxes were not listed at all.
- The "Steel peak" column is that browser's memory during the run. It stays because the rows are
  the record; no browser runs on this host now.

### Jev, and why it is inside

Jev (TypeSafe) is a decision model: given the page's interactive elements and a step like
"click the pricing link", it returns *which element*, with a probability, in a few hundred
milliseconds. It never generates text, so it cannot plan, write a search query or decide a
goal is done — **your agent still does all of that**. What Jev replaces is the 2–10 s of LLM
time a browser agent spends per step just finding the button.

- **The gateway does the step.** There is no Jev container. The gateway lists the page's
  interactive elements over CDP, sends them to TypeSafe's decision API in one request per step,
  and clicks or types the element Jev picked (`gateway/gateway/stepper.py`, `decide.py`). It needs
  `TYPESAFE_API_KEY`; `BB_DECISION_URL` and `BB_DECISION_MODEL` point it at another server that
  speaks the same API.
- **It asks rather than guesses.** A low-confidence step comes back as
  `needs_clarification` with options; answer with `act(pick=…)`. Anything that looks hard to
  undo (buy, delete, send, post) comes back as `needs_confirmation`; nothing risky runs
  unconfirmed. Risk is judged twice, once from your words and once from the element Jev picked.
- **No second brain.** The decision model never writes text; code decides what is typed.
- **Measured 2026-10-12** on 30 element questions over real pages: Jev 30/30 at ~176 ms;
  Cloudflare's Clef, which takes the same request body, 28/30 at ~518 ms. Page loads, not the
  decision, dominate a step's time.
- **Where it works.** `act` works in the browser of the `session_id` you give it, so it can take a
  page step by step and each agent can have its own. Without one it uses one shared scratch browser,
  forgotten when it closes. Every browser is fresh and logged out; this box keeps no logins
  ([choosing.md](docs/choosing.md)).

### Browser-Use, and how it gets a browser

`task(surface="browser")` hands a whole goal to Browser-Use (0.13.10, pinned), an LLM step loop.
The gateway opens a hosted browser for the task and passes its CDP address to `agent-browseruse`,
which drives it. The step model is `z-ai/glm-5.3-flash` on OpenRouter (`BB_BROWSERUSE_MODEL`),
text only (`use_vision` off). Browser-Use's end-of-run "judge" model call is off too: it costs a
call per task and judges what the answer already reports.

- **A browser per task, several tasks at once.** Each task runs in a child process of its own,
  killed outright at `timeout_seconds` or on cancel, against a hosted browser that is stopped when
  the task ends. Tasks run side by side up to the plan's browser ceiling. `BB_BROWSERUSE_PARALLEL` defaults to 0, which means no cap of
  ours; the agent container's memory (`BROWSERUSE_MEMORY`, default 1200m) is the real bound, at about
  100-300 MB per running task. A `task` takes no `session_id`: it always opens a browser of its own.
- **No browser in the container.** `agent-browseruse` idled at 38 MiB and peaked at 327 MiB during
  a task (measured, one task at a time).
- **Its tab confinement remains.** `agents/browseruse/runner.py` still keeps each task to the tab
  opened for it: tabs that existed first are invisible to it, it cannot open a CDP session on or
  close one, and its downloads watchdog and browser-wide permission grant are disabled. These
  patches are written against 0.13.10 only: a self-check at startup fails, and status reports it,
  if the version or any patched method changes.
- **It keeps running if you stop waiting.** The endpoint is stateless, so an MCP client's
  cancel notification can never reach the call it cancels (each POST is its own server
  instance). A task therefore runs to its `timeout_seconds` unless someone calls
  `task(cancel=true)`. That stops every running browser task and its hosted browser, and each
  stopped task still reports its steps and cost. Browsers left running by a gateway crash are
  stopped when the gateway next starts.
- **When Browser Use cannot open a browser,** the task runs on Browserbase and says so
  (`engine: "browserbase"`, `fallback_reason`).
- **What it costs, measured** (before the move to hosted browsers; the model cost does not depend
  on the browser, the seconds may):
  - example.com, report the heading: 2 steps, 9.7 s, $0.0011.
  - Hacker News top story and its points: 2 steps, 13.3 s, $0.0021.
  - Hacker News top story's comment count, from its comments page: 3 steps, 31.4 s, $0.0056.
  - Hacker News first top-level comment: 3 steps, 24.8 s, $0.0053.

  Cost is the model's tokens at OpenRouter's list price, as an upper bound because
  prompt-cache discounts are not applied. It comes back per task, and `status` adds up the
  recent ones. Browser time is billed by Browser Use on top.
- **Telemetry is off** (`ANONYMIZED_TELEMETRY=false`, cloud sync off). The only outside
  service it calls is OpenRouter.

Enable it (a compose profile, off by default):

```bash
# in .env — see .env.example for each line
COMPOSE_PROFILES=browseruse
BROWSER_USE_API_KEY=...
BB_BROWSERUSE_URL=http://agent-browseruse:3120
BB_BROWSERUSE_TOKEN=$(openssl rand -hex 24)
OPENROUTER_API_KEY=...
make up
```

### Orgo, and why it is off-box

A self-hosted X/VNC desktop would need ~1.5 GB and real CPU on a small VPS. Orgo gives full
desktops elsewhere, so they cost this box nothing. Three things from Orgo's own API docs shape
the integration:

- **Its computer-use endpoint accepts exactly five model ids** and returns `400 invalid_model`
  for anything else — including `claude-sonnet-4-6` with a hyphen (Orgo spells it `4.6`). That
  hyphenated id is what Super Browser sent, and is the likeliest reason its Orgo test failed.
  `ORGO_MODEL` is validated before any request.
- **A computer runs until it is stopped.** There is no auto-stop. So `computer` has a `stop`
  action, and creating a computer requires `BB_ORGO_AUTOCREATE=1`.
- **Orgo ignores `max_steps`** (fixed 250-step loop). `task` streams, so its timeout closes the
  stream and genuinely aborts the run rather than leaving it billing after we stop listening.

There is no provider catalog, no readiness walkthrough, no plan/verify/resume, and no doctor
variants. That surface is what made the last one unusable.

## Concurrency

Browsers do not share a lane. Every `read`, every `act` scratch browser and every `task` gets a
hosted browser of its own, and they run side by side up to the plan's `concurrentSessionLimit`
(read from the account, never more than `BB_BROWSERUSE_MAX_CONCURRENT`; that is the plan's limit,
not a lock of ours). The one rule that remains per browser: **a session runs one browser at a
time**, because two callers driving one page at once would trample each other. Calls on one
`session_id` wait for each other up to `BB_SESSION_WAIT_SECONDS` (default 30) and then answer
"busy"; different sessions run in parallel.

The cross-process `flock` in `gateway/gateway/lock.py` now guards only Orgo computers: one driver
per desktop. A second caller waits up to `BB_LANE_WAIT_SECONDS` and is then told that computer is
busy.

## Security

The box sits next to your other services (the gateway, Caddy, anything else on the host), so a page
must never be able to reach them. This was real: on 2026-09-22, when the browser ran on this host,
a public URL that 302-redirected to `http://127.0.0.1:3000/v1/sessions` made the browser read its
own session list and hand it back as page content. The redirect exploit is in the test suite still.

**What changed.** The browsers now run on Browser Use's and Browserbase's networks, not on this
host. A page loaded in one cannot reach this host's loopback, its compose network or its cloud
metadata address. It reaches this host only the way any internet client does, through its public
ports, where the MCP endpoint is bearer-gated.
So the host-egress `iptables` rules and the in-browser request guard, which existed to stop a
browser on this host from being steered into the host's other services, are gone, and nothing
replaces them because that route no longer exists. SSRF against this host is closed by where the
browsers live, not by a rule we maintain.

What the code still does:

- **Every URL is validated and classified before any browser opens or connection is made**
  (`safe_target`). Only a public scheme and host pass, and every address the host name resolves to
  must be public too.
- **Obfuscated loopback is handled.** Browsers accept `0x7f000001`, `2130706433`, `0177.0.0.1`
  and `127.1`; Python's `ip_address` rejects all four, so a naive check falls through to
  "public" and happily fetches localhost. See `gateway/gateway/security.py`.
- **Every hostname is resolved and every address it answers with is checked.** A public name
  that A-records to `10.0.0.5` is refused. One public record does not launder a second one
  pointing at the metadata service.
- **`fetch` walks the redirect chain by hand, one hop at a time, and clears each hop before
  connecting.** `fetch` is the one tool that makes an HTTP request from this host, so it is the
  one where a redirect into an internal address would be a real exposure. Inspecting
  `response.history` afterwards is too late: the request to the internal address already happened.
- **A page that lands off the public web is dropped.** `read` (on either provider) drops one, and `act`
  checks the page after each step: if it landed somewhere non-public, the tab goes to
  `about:blank` and the step is reported as refused.
- Cloud metadata (`169.254.169.254`) is link-local and blocked.
- Nothing is published beyond `127.0.0.1`. Caddy terminates TLS and is the only public surface.
- The gateway refuses to start without `BB_TOKEN`. An open browser endpoint is not a degraded
  mode; it is a breach.
- `/health` is unauthenticated liveness only and never reports what is configured or up.

### What this does NOT cover

1. **DNS rebinding.** A name that resolves public at check time can resolve private a second
   later. For `fetch` this is real: the gateway resolves the name to check it, and the HTTP client
   resolves it again to connect. For the hosted browsers a rebound answer points into the
   provider's network, not this host.
2. **The hosted browsers' own DNS and connecting.** The gateway checks the URL it hands over and,
   in `read` and `act`, where the page landed; it does not see requests a page makes after
   that. Those happen on the provider's machines.
3. **This box keeps no logins and never touches a Browser Use profile.** `cloud.py` refuses any API
   path containing "profile" before making the request, and no browser is created with a
   `profileId`: the Browser Use account also holds other tools' logged-in profiles, and
   touching one would be a serious incident. `live_url` lets whoever holds it drive that session's
   browser, so keep it to yourself. Crash cleanup stops only browsers this box created, by the ids
   it recorded (`BB_OWNED_BROWSERS`); it never searches the account.
4. **Browser-Use reads untrusted pages and acts on them.** A page can instruct it, and it may
   follow the instructions: go elsewhere on the public web, type what the page asks, click what
   the page wants clicked. The hosted browser keeps it off this host. `upload_file` is excluded,
   so it cannot post this container's files. Its process holds one secret, the OpenRouter
   key, and no tool of its reads the environment. A task takes no `session_id` and runs in a fresh,
   logged-out browser, so a page that steers it has no login to act as.
5. **Bot walls are not reliably bypassed.** CAPTCHA solving is on by default (`BB_SOLVE_CAPTCHAS=1`)
   on both providers, but Browser Use's residential proxy is off (it is billed per GB), so a
   challenge the provider cannot solve still comes back as a failed or blocked read.

## Run it

```bash
cp .env.example .env
make token          # paste the value into BB_TOKEN in .env
chmod 600 .env      # then set BROWSER_USE_API_KEY, and the keys for what you want offered
make up
make status
```

Then prove it end to end:

```bash
make smoke
```

`make smoke` lists the tools, calls `status`, reads a real page with a screenshot through the MCP
endpoint, and asserts that obfuscated loopback and a public redirect into loopback are refused.
When `act` is offered it opens a page and checks that a redirect into loopback is refused; when
`task(surface="browser")` is offered it runs a one-page goal. If it passes, the box works.

Measured on the read path (2026-10-12): Hacker News with a screenshot in 3.6 s; three different
pages at once in 3.2 s. The gateway container is capped at 256 MB and `agent-browseruse` at 1200 MB (`BROWSERUSE_MEMORY`).
There is no Chromium to size a host for.

`make smoke` finishes by driving the endpoint with a real MCP client — `initialize`,
`notifications/initialized`, session headers, SSE negotiation — because raw JSON-RPC over
curl skips all of that, and "it should work statelessly" is exactly the kind of assumption
that produced the last system. Both `/mcp` and `/mcp/` are checked, and so is the refusal of
a client with the wrong token.

## Five ways to talk to it

All five hit the same gateway, the same tools, the same token. There is no privileged
back door that can drift from what agents see.

- **MCP** at `/mcp`, for agents (below).
- **HTTP/JSON** at `/api/v1/<tool>`: one POST per tool, the arguments as the JSON body, a refusal
  as HTTP 422 with the same `{"error": ...}` body; `GET /api/v1/status`, `GET /api/v1/tools`, and
  the OpenAPI document at `/openapi.json` (no token). `make openapi` regenerates
  `docs/openapi.json` from the tool cards, and a test fails if the committed copy drifts.
  Details: [docs/tools.md](docs/tools.md).
- **`bb`**, the Python command line, which can also chat through a model on your machine (below).
- **`browser-box-pp-cli`**, a Go command line generated from the OpenAPI document with Printing
  Press, in [pp-cli/](pp-cli/). Every call it makes is written to a local ledger, so it adds what
  the box does not keep: `history` (the box remembers only its last 10 calls), `cache` and `find`
  over every page it read, `queue read` for batches of reads, `alias` for session ids, and `drift`
  for what changed on the box since you last looked. The ledger sees only calls made through this
  CLI or its own MCP server. It also serves the same commands as an MCP server of its own.
- **The plugin**, for Claude Code (below).

### 1. MCP — for Claude Code, Claude Desktop, or any agent

```bash
claude mcp add --transport http browser-box https://your-box/mcp \
  --header "Authorization: Bearer $BROWSER_BOX_TOKEN"
```

Or drop this in a project's `.mcp.json` (the repo ships one, defaulting to a local box).
Both expansion forms below are **verified live against Claude Code** — the `${VAR:-default}`
URL resolves when the variable is unset, and `BROWSER_BOX_TOKEN` expands in the header
despite being a credential-shaped name. Note that `claude mcp list` prints the raw text
rather than the expanded value, so a literal `${...}` in that output is not a fault:

```json
{
  "mcpServers": {
    "browser-box": {
      "type": "http",
      "url": "${BROWSER_BOX_URL:-http://127.0.0.1:8080/mcp}",
      "headers": { "Authorization": "Bearer ${BROWSER_BOX_TOKEN}" }
    }
  }
}
```

### 2. The `bb` CLI — for your terminal

```bash
pipx install ./cli                       # from a clone
bb login --url https://your-box --token <BB_TOKEN>
```

While the repo is **private**, the `git+https://…` install form needs a credential — clone
first, or make the repo public (one command, below). Once it is public:

```bash
pipx install 'git+https://github.com/jbellsolutions/browser-box#subdirectory=cli'
```

```bash
bb status                                          # what is up, and why not
bb fetch -t https://example.com                    # plain HTTP, free, instant
bb read -t -s -o shot.jpg https://news.ycombinator.com  # hosted browser + screenshot to a file
bb session create                                  # a fresh browser of your own, for act
bb act "open news.ycombinator.com then click new"   # steps you planned, grounded by Jev
bb task "report the top HN story's comment count"  # hand a whole goal to Browser-Use
bb task --cancel                                   # stop a running task
bb tools                                           # what this box offers
```

And to actually **chat** with it:

```bash
export OPENROUTER_API_KEY=sk-or-...
bb ask "what are the top 3 stories on Hacker News right now"
bb chat
```

> `ask` and `chat` are the only part of this repo **not** proven against a live model — their
> loop is tested against a stub, so the suite spends nothing. One real call settles it.

`ask` and `chat` run the model **in the CLI, on your machine** — the box still has no brain
in it. If you deleted the CLI tomorrow the box would be unchanged. That is the whole
difference between this and the harness that failed twice. Everything else (`fetch`, `read`,
`session`, `status`) needs no model and no key at all.

### 3. The plugin — for your agents

The repo is its own plugin marketplace, so it installs in one step:

```
/plugin marketplace add jbellsolutions/browser-box
/plugin install browser-box@browser-box
```

`claude plugin validate .` passes on this repo, and `make plugin` re-runs it. A private
marketplace works as long as your `git` is authenticated to the repo; to remove that
condition entirely:

```bash
gh repo edit jbellsolutions/browser-box --visibility public --accept-visibility-change-consequences
```

That attaches the MCP server, a `browser-box` skill that teaches `fetch`-before-`read` and
what the refusals mean, and two commands: `/browse <url or question>` and `/box-status`.
Set `BROWSER_BOX_URL` and `BROWSER_BOX_TOKEN` in your environment first.

### Host setup

Ubuntu 24.04, Docker Engine, UFW allowing only 22, 80 (the certificate challenge) and 443,
`python3-venv` (for `make venv` and `make smoke`), Caddy on the host (not in compose, so a stack
restart never drops TLS). There is no egress rule to apply: no browser runs on the host.

**DigitalOcean expires root's password** on a droplet created without a DO-registered SSH key,
and an expired password blocks every non-interactive login, even with a valid key ("Password
change required but no TTY available"). Create it with `chpasswd: {expire: false}` in its
cloud-init, and give it a key-only sudo user.

```bash
sudo apt-get install -y caddy   # or the official repo: caddyserver.com/docs/install

# Substitute the domain at install time. `BB_DOMAIN=x cp ...` does NOT work: cp does no
# substitution, and Caddy reads {$BB_DOMAIN} from the caddy SERVICE's environment, not
# from the shell that copied the file. An unset value yields an empty site address.
sudo sed "s|{\$BB_DOMAIN}|box.example.com|" Caddyfile | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy
```

**Sizing.** A 1 vCPU / 2 GB droplet with 2 GB swap ($12/mo). The compose caps total about
1.5 GB (gateway 256 MB, agent-browseruse 1200 MB); measured there, 10 reads at once took 4 s and 4
tasks at once 73 s, with agent-browseruse peaking at 444 MiB.

## Develop

```bash
make venv     # once
make test     # 238 tests, no Docker, no browser and no API key needed
```

The tests cover the SSRF checks — all four obfuscated-loopback forms, inward DNS answers, the
redirect-into-loopback exploit — plus the Orgo lane, the tool result shapes, the emergency
fallbacks, and the fact that the gateway refuses to start unauthenticated and refuses to answer
without a token. The CLI's `ask` loop is tested against a stub model, so the suite needs no key and
spends nothing, and the plugin manifests are checked against the real tool list so a command cannot
allow-list a tool that does not exist.

## Layout

```
compose.yml          gateway (+ agent-browseruse, profile browseruse), loopback-only, memory and CPU
                     capped. No browser runs on this host
Caddyfile            TLS and the only public surface (install on the host)
gateway/
  gateway/
    server.py        MCP over streamable HTTP, bearer-gated
    rest.py          the HTTP/JSON door and the OpenAPI document, built from the same tool cards
    tools.py         the tools and their cards; safe_target and fetch's redirect walk
    cloud.py         Browser Use Cloud: a hosted browser per call, spend and concurrency caps
    sessions.py      fresh browsers kept open between calls, one open browser per session
    stepper.py       act: lists the page's elements, asks Jev, does the step over CDP
    decide.py        client for the decision model (TypeSafe's Jev by default)
    browserbase.py   Browserbase, the emergency lane
    cdp.py           a small CDP client
    orgo.py          Orgo cloud computers — every path and body from Orgo's own docs
    browseruse.py    client for agent-browseruse, the agent behind task(surface="browser")
    lock.py          the lane lock, now used for Orgo computers only
    security.py      URL scope classification — port this, never rewrite it
agents/browseruse/   Browser-Use in a container: server.py (no browser_use import; runs, times out, kills,
                     cleans up tabs) and runner.py (one task, confined to its own tab)
cli/                 the `bb` command line (its own package, pipx-installable)
pp-cli/              browser-box-pp-cli: the Go command line + MCP server generated from docs/openapi.json
docs/                choosing, architecture, tools, operations, security, integrations, benchmark; openapi.json
CHARTER.md AGENTS.md the rules for agents, and how to use and change this repo
.claude-plugin/      plugin + marketplace manifests
skills/ commands/    what the plugin teaches an agent
scripts/smoke.sh     the end-to-end proof
tests/               238 tests; scope_vectors.json holds the shared URL-scope vectors
```
