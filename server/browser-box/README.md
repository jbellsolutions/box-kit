# browser-box

One browser, one door.

A self-hosted browser on your own VPS, behind a single MCP endpoint. Your agent — Claude,
or anything else that speaks MCP — is the brain. This box is the hands. Two models can run
here, both opt-in: Jev, behind `act`, picks page elements and cannot write a word; Browser-Use,
behind `task(surface="browser")`, is an LLM step loop for when you would rather hand over a
whole goal than plan its steps. Neither decides what you are trying to do.

```
  your agent ──MCP over HTTPS──► gateway ──REST──────────────────────► Steel ──► the only Chromium
                (bearer token)      │ └─ guard ──CDP (every request)──────┤
                                    ├─ act ──► agent-jev ──CDP───────────┤  (Jev: which element?)
                                    ├─ task(browser) ──► agent-browseruse ┘  (an LLM plans each step)
                                    └─ computer / task(computer) ──► Orgo (desktops, off-box)
```

## Why this exists

The system this replaces had 29 MCP tools, 22 of which could not reach a browser, and a
capability report that said `unverified` and `[]` for providers that were working in the
same minute. It had an LLM loop inside the tool, in a different body from the hands. That
is the failure this repo is shaped to avoid:

- **If a tool is listed, it works.** If it can't work right now, `status` says so in one line, with the reason.
- **No brain in the box by default.** The agent calling the MCP decides. The box executes and
  reports. The one step-planning model here, Browser-Use behind `task`, is opt-in and says so.
- **Few tools.** Each new capability adds one tool, or one surface of one, and only after it is proven end to end.

## Steel vs Browser-Use vs Browserless vs Browserbase

They are not four of the same thing. They are **two layers**, and only one of them is a browser.

| | What it actually is | Self-host? | License | Here |
|---|---|---|---|---|
| **Steel** | Browser **infrastructure** — sessions, CDP, profiles, cookies, proxy, live view | Yes, Docker | Apache-2.0 | **This is the browser.** |
| **Browserless** | Browser infrastructure — CDP + REST | Yes, Docker | **SSPL-1.0** or commercial | Skipped. Same job as Steel; SSPL §13 triggers when you offer the functionality to third parties as a service. |
| **Browser-Use** | An **LLM agent** that drives a browser. Needs a browser | Yes, pip | MIT | `task(surface="browser")`, on Steel's Chromium |
| **Browserbase** | SaaS browser infrastructure | **No self-hostable server exists** | — | Cloud only. Their open source is Stagehand. |
| **Stagehand** | Browserbase's **agent/SDK** (`act`/`extract`/`observe`), runs against a local browser | Yes, npm/pip | MIT | Deferred: its `act` overlaps Jev's. It gets a slot only if the act-vs-task benchmark shows a need. This is what "self-hosted Browserbase" means |

**Running four Chromiums buys nothing.** Browser-Use and Stagehand are two steering wheels;
they both need one engine. One browser plus two agent front-ends gives the same capability
at a quarter of the RAM — and lets you A/B the two agents against the *same* browser, which
is the only fair comparison you can make.

Hyperbrowser and Browserbase stay cloud, called by API when a job needs their fleet or their
stealth. There is nothing to self-host there.

## The tools

| Tool | Does | Backed by | Costs |
|---|---|---|---|
| `fetch` | plain HTTP GET, no browser | gateway | free |
| `read` | open a URL, return text + links + screenshot | Steel | free (own hardware) |
| `session` | create / list / release a persistent logged-in session | Steel | free |
| `act` | drive the browser in plain-words steps: open, click, type, scroll; asks when unsure, confirms anything risky | Jev → Steel | TypeSafe decisions |
| `computer` | drive an Orgo cloud desktop: screenshot, click, type, key, scroll, bash, start, stop | Orgo (off-box) | Orgo, per hour |
| `task` | hand a whole goal to an agent: Browser-Use in this box's browser, or Orgo's computer-use agent on a desktop | Browser-Use → Steel; Orgo (off-box) | model tokens, reported per task; Orgo + model |
| `status` | what is up, what is healthy, what recent calls cost | gateway | free |

`act` is listed **only when Jev is configured** (`BB_JEV_URL` + `BB_JEV_TOKEN`), `computer`
**only when `ORGO_API_KEY` is set**, and `task` only when at least one of its surfaces is:
`browser` needs agent-browseruse (`BB_BROWSERUSE_URL` + `BB_BROWSERUSE_TOKEN`), `computer`
needs Orgo. Its card and its `surface` choices list only the surfaces this box has. A box
without Orgo has no computers, and advertising them would be the lie this repo exists to stop. Screenshots — from
`read` and `computer` — come back as real MCP image blocks, so a vision-capable caller can
actually see them rather than receiving base64 as text.

### act vs task: measured, and which to use

Five jobs, each run 3 times through `act` (the caller plans the steps, Jev grounds each one) and
through `task(surface="browser")` (Browser-Use with `z-ai/glm-5.3-flash` plans them), in the same
Steel browser on a Mac (2026-09-23; Jev `edcbbae`; raw rows in
[`bench/results-2026-09-23.json`](bench/results-2026-09-23.json); rerun with
`.venv/bin/python scripts/bench.py 3`). Success is checked against ground truth fetched
separately (the Wikipedia search API, the quotes pages, the live form and to-do DOM), never
against the agent's own claim.

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
- Steel peaked at 1.36 GiB during a task. The cap is now 1.5 GiB.

### Jev, and why it is inside

Jev (TypeSafe) is a decision model: given the page's interactive elements and a step like
"click the pricing link", it returns *which element*, with a probability, in a few hundred
milliseconds. It never generates text, so it cannot plan, write a search query or decide a
goal is done — **your agent still does all of that**. What Jev replaces is the 2–10 s of LLM
time a browser agent spends per step just finding the button.

- **One browser.** `agent-jev` has no Chromium. It attaches to Steel's over CDP and works in
  its own tab, so a `read` in between does not disturb it. Measured: 134 MiB for the container,
  and `ps` finds Chromium only inside `steel`.
- **It asks rather than guesses.** A low-confidence step comes back as
  `needs_clarification` with options; answer with `act(pick=…)`. Anything that looks hard to
  undo (buy, delete, send, post) comes back as `needs_confirmation`; nothing risky runs
  unconfirmed.
- **No second brain.** The container gets no model key, and the gateway never calls Jev's
  `/ask`. It decides elements, nothing more.
- **Creating or releasing a `session` restarts Steel's Chromium.** Jev reattaches on its
  next step, but its tab starts again at `about:blank`.
- **Measured through `act` on real pages** (Hacker News, python.org, Wikipedia, example.com):
  Jev's decision itself took 209–424 ms (median ~300 ms, n=20; one 8.8 s outlier). A whole
  click step, gateway to page settled, took 1.2–2.5 s, and up to ~11 s when the page itself
  was slow. Page load and settling dominate, not the decision. `act` reports each step's
  `decided_by` and `decision_ms` so this stays checkable. The benchmark against Browser-Use is B5.

Enable it (it is a compose profile, off by default):

```bash
# in .env — see .env.example for each line
COMPOSE_PROFILES=jev
BB_JEV_URL=http://agent-jev:3111
BB_JEV_TOKEN=$(openssl rand -hex 24)
TYPESAFE_API_KEY=...          # without it Jev falls back to keyword heuristics, and status says so
JEV_DIR=../jev-automation     # a checkout of jev-automation
JEV_REF=<commit>              # the exact commit `make jev-image` builds, via git archive
make up                       # builds agent-jev first, then the stack
```

`make jev-image` builds from the commit in git, never from that checkout's working files, so
uncommitted work there cannot leak into the box.

### Browser-Use, and how it shares the one browser

`task(surface="browser")` hands a whole goal to Browser-Use (0.13.10, pinned), an LLM step loop
that drives Steel's Chromium over CDP. The step model is `z-ai/glm-5.3-flash` on OpenRouter
(`BB_BROWSERUSE_MODEL`), text only (`use_vision` off). Browser-Use's end-of-run "judge" model
call is off too: it costs a call per task and judges what the answer already reports.

- **One browser.** `agent-browseruse` has no Chromium. Each task runs in a child process of its
  own, killed outright at `timeout_seconds` or on cancel. The container idles at 38 MiB and
  peaked at 327 MiB during a task (measured).
- **It stays in its own tab.** Browser-Use assumes the browser is its own. On connect it took
  over the first tab it found, which was `act`'s (verified: `act`'s next step landed on Hacker
  News). Now every tab that exists when a task starts is invisible to it, and it cannot open a
  CDP session on one, so it cannot navigate, switch to or close them. Its downloads watchdog,
  which would switch the whole browser to downloading into a temp directory, is disabled.
  So is its browser-wide permission grant. The container closes the task's tabs when it ends,
  never someone else's and never the last one. These patches are written against 0.13.10
  only: a self-check at startup fails, and status reports it, if the version or any patched
  method changes. `make smoke` runs `act`, then a task, then `act` again, and fails if the
  task moved `act`'s tab.
- **It holds the browser lane for the whole task** and needs the in-browser guard. If the
  guard detaches mid-task, the task is stopped (status `stopped`) rather than left browsing
  unguarded.
- **It keeps running if you stop waiting.** The endpoint is stateless, so an MCP client's
  cancel notification can never reach the call it cancels (each POST is its own server
  instance). A task therefore runs to its `timeout_seconds`, holding the browser, unless
  someone calls `task(cancel=true)`. That answers once the agent is dead and its tabs are
  closed, and the stopped task still reports its steps and cost. A `read` or `act` that finds
  the lane held by a task says so. A gateway that restarts stops any task left running by the
  one before it, since that task's lane died with the old process.
- **What it costs, measured**:
  - example.com, report the heading: 2 steps, 9.7 s, $0.0011.
  - Hacker News top story and its points: 2 steps, 13.3 s, $0.0021.
  - Hacker News top story's comment count, from its comments page: 3 steps, 31.4 s, $0.0056.
  - Hacker News first top-level comment: 3 steps, 24.8 s, $0.0053.
  Cost is the model's tokens at OpenRouter's list price, as an upper bound because
  prompt-cache discounts are not applied. It comes back per task, and `status` adds up the
  recent ones. Compared against `act` in the benchmark (B5).
- **Telemetry is off** (`ANONYMIZED_TELEMETRY=false`, cloud sync off). The only outside
  service it calls is OpenRouter.

Enable it (a compose profile, off by default):

```bash
# in .env — see .env.example for each line
COMPOSE_PROFILES=jev,browseruse
BB_BROWSERUSE_URL=http://agent-browseruse:3120
BB_BROWSERUSE_TOKEN=$(openssl rand -hex 24)
OPENROUTER_API_KEY=...
make up
```

### Orgo, and why it is off-box

A self-hosted X/VNC desktop would need ~1.5 GB and real CPU on a box whose browser already
sits near 900 MB. Orgo gives full desktops elsewhere, so they cost this box nothing and never
contend for the browser lane. Three things from Orgo's own API docs shape the integration:

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

## One job at a time

The gateway holds a cross-process `flock` and every browser call takes it. This is not
caution for its own sake — it is a bug already paid for. Concurrent Browser-Use runs on a
single local Chromium produced *"attached to a different loop"*, *"Root CDP client not
initialized"*, a dead CDP websocket and a 30s browser-start stall. A second caller waits
up to `BB_LANE_WAIT_SECONDS` and is then told the lane is busy, in words the model can act
on. It is never queued silently forever. `task(surface="browser")` holds the lane for its whole
run, since its agent is driving the browser the entire time.

## Security

The box sits next to your other services, so a page must never be able to reach them.
**This is not theoretical here.** On 2026-09-22, before the guard below existed, a public
URL that 302-redirected to `http://127.0.0.1:3000/v1/sessions` made the browser read
Steel's *own* session list and hand it back as page content. That exploit is in the test
suite now.

What the code does:

- **Every URL is validated and classified before any connection is made.** Only `public_web` passes.
- **Obfuscated loopback is handled.** Browsers accept `0x7f000001`, `2130706433`, `0177.0.0.1`
  and `127.1`; Python's `ip_address` rejects all four, so a naive check falls through to
  "public" and happily fetches localhost. See `gateway/gateway/security.py`.
- **Every hostname is resolved and every address it answers with is checked.** A public name
  that A-records to `10.0.0.5` is refused. One public record does not launder a second one
  pointing at the metadata service.
- **The redirect chain is walked by hand, one hop at a time, and cleared before each
  connection.** Inspecting `response.history` afterwards is too late — the request to the
  internal address already happened.
- **The browser is handed the cleared final URL, not the one that was asked for.** Steel's
  `metadata.urlSource` echoes the request, so the browser's own landing address is not
  observable from the gateway. Pre-flighting the chain is the only control there is at this layer.
- Cloud metadata (`169.254.169.254`) is link-local and blocked.
- **Inside the browser, every request is checked where it actually happens.** A click, a browser
  agent's own navigation, a redirect inside Steel's screenshot load, a popup and an iframe are
  all invisible to the gateway's pre-flight. So the gateway also runs a **guard**
  (`gateway/gateway/guard.py`): one CDP client that switches request interception on for the
  **whole browser at once** (`Fetch.enable` on the browser target). Every request in every tab,
  frame and dedicated worker, redirect hops included, is paused and checked with the same
  classifier as everything else here, from the moment the guard connects. Service and shared
  workers run as targets of their own, which the browser-wide interceptor does not see, so the
  guard also auto-attaches to those two kinds, holds each before its first line runs, and
  intercepts it on its own session.
  - Two designs were tried first and leaked. Playwright's `route()` let redirect hops straight
    through. Per-tab interception (attach to each new tab, then intercept it) missed a tab
    created with its URL already given: `Target.createTarget` starts that request before any
    client can intercept the tab, and a redirect rides the request already in flight. A public
    URL that 302s to `127.0.0.1:3000` loaded Steel's session list past it every time (5/5,
    verified 2026-09-23). Any CDP client in the box can create such a tab, Browser-Use included.
  - `make guard-check` runs 18 attacks against the live browser with nothing but this guard
    between them and Steel's API. It refused all 18: the redirect exploit, a metadata redirect,
    direct and obfuscated loopback, a compose service name, a page `fetch()`, a worker's
    fetch, a popup that redirects inward, the exploit after a 1.5 MB request, and after a
    browser relaunch. With no guard at all, the 7 navigation cases get through: Chromium's own
    Local Network Access check covers subresources and WebSockets, **not navigation**.
  - `make smoke` aims Steel's own `/v1/screenshot` straight at the redirect, bypassing the
    gateway entirely; the guard refuses it inside the browser.
  - Its cost is small next to the noise but not zero: warm loads of two news front pages
    (120–195 requests) took 2.6 s and 2.5–3.6 s with it on, 3.7 s and 1.7–2.4 s with it off.
    The first load of a new host also waits for the guard's own DNS check (cached for 60 s).
  - Jev's executor keeps its own per-page guard on top (a TypeScript port of the same
    classifier, run against the same 33 vectors in `tests/scope_vectors.json`), so `act` has
    two independent layers.
- **The guard fails open, so the tools fail closed.** When its connection drops, Chrome
  releases everything it was holding (verified). So `act` waits for it and refuses without it,
  `read` withholds its screenshot, `session` holds the browser lane after a relaunch until the
  guard is back on the new browser, and `status` reports the guard as its own component.
- Steel's recorder extension posts session events from its service worker to Steel's own API.
  The guard refuses those like any other request inward (this box does not run Steel's replay
  viewer) and counts posts to that endpoint apart in `status`, so they cannot bury real refusals.
- Nothing is published beyond `127.0.0.1`. Caddy terminates TLS and is the only public surface.
- **CDP especially stays on loopback** — an exposed CDP port is a remote shell into the browser.
- The gateway refuses to start without `BB_TOKEN`. An open browser endpoint is not a degraded
  mode; it is a breach.
- `/health` is unauthenticated liveness only and never reports what is configured or up.

### What this does NOT cover, and what to do about it

Be clear-eyed: the gateway can only vet what it sees. Once Steel has a URL, **Chromium does
its own DNS and its own connecting**, and the gateway has no say.

1. **DNS rebinding.** A name that resolves public at check time can resolve private a second
   later. The pre-flight cannot close this.
2. **A server that answers our pre-flight differently from the browser.** `read` sends a HEAD
   with the same user agent, but a target that redirects only for real Chromium defeats it.
   If the pre-flight fails outright, `read` proceeds with the URL as written (already
   validated) rather than failing every site that refuses non-browser clients.
3. **Steel reaching its own loopback.** No network policy can stop a container talking to
   itself, which is why Steel holds nothing worth stealing and why the token in front matters.
4. **`read(screenshot=true)` is a second navigation the pre-flight never sees.** Before the
   guard existed, it photographed Steel's own API through a redirect. The guard now refuses
   that inside the browser, and `read` withholds the screenshot whenever the guard is not
   attached.
5. **Service workers** have their own network path. The guard intercepts them on their own
   sessions (it refuses Steel's recorder worker's posts this way), but a page-registered service
   worker's fetch into a private address has not been tested. Chromium's Local Network Access
   applies too; the egress rule is the backstop.
6. **The guard is one process.** A crash or a Steel restart leaves a window before it
   reattaches. The tools refuse to navigate in that window, and a browser task is stopped when
   the guard goes, but anything already loading at that moment is unguarded until it is back.
7. **Browser-Use reads untrusted pages and acts on them.** A page can instruct it, and it may
   follow the instructions: go elsewhere on the public web, type what the page asks, click what
   the page wants clicked. The guard keeps it off private addresses. `upload_file` is excluded,
   so it cannot post this container's files. Its process holds one secret, the OpenRouter
   key, and no tool of its reads the environment. It cannot reach `act`'s tab. But its tab
   shares the browser's cookies, so **after a `session` login, a task can act as that login**.
   Hand it goals on logged-in sites only when you would let a web page steer that account.

Not a security gap, but a limit to know: under Steel, only the first dedicated Web Worker of a
CDP connection gets network; later workers' fetches hang, with or without any guard (verified
with a bare Playwright client). A page that does its data loading in workers may never finish
loading, whichever tool drives it.

**The real control is network-level, and it belongs on the host.** Deny the browser
everything private except the gateway:

```bash
STEEL_NET=$(docker network inspect browser-box_box -f '{{(index .IPAM.Config 0).Subnet}}')
for range in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 127.0.0.0/8; do
  sudo iptables -I DOCKER-USER -s "$STEEL_NET" -d "$range" -j DROP
done
# ORDER MATTERS: -I prepends, so this ACCEPT must go in LAST to sit ABOVE the DROPs.
# Reorder these two blocks and the stack silently loses steel <-> gateway.
sudo iptables -I DOCKER-USER 1 -s "$STEEL_NET" -d "$STEEL_NET" -j ACCEPT
sudo iptables -L DOCKER-USER -n --line-numbers | head    # ACCEPT must be line 1
# DOCKER-USER only sees traffic passing THROUGH the host. A container connecting to the host
# itself (its bridge, VPC or public address) goes through INPUT: without this line the browser
# reached the droplet's sshd (verified on the droplet, 2026-09-23). NEW only, so replies on
# connections the host opened (published ports) still flow.
sudo iptables -I INPUT 1 -s "$STEEL_NET" -m conntrack --ctstate NEW -j DROP
sudo apt-get install -y iptables-persistent && sudo netfilter-persistent save   # or the rules die on reboot
```

Run that on the droplet before pointing anything at it. Then check it from inside the browser's
container: DigitalOcean's metadata address, the VPC and the host must all time out., and keep the guards in the gateway
as well. Neither layer is sufficient alone.

## Run it

```bash
cp .env.example .env
make token          # paste the value into BB_TOKEN in .env
chmod 600 .env
make up
make status
```

Then prove it end to end:

```bash
make smoke
```

`make smoke` lists the tools, calls `status`, reads a real page through the MCP endpoint,
and asserts that obfuscated loopback is refused. If it passes, the box works.

With Jev enabled, also run the attack from inside the box network:

```bash
make shield-check   # 18 cases, both guards on; relaunches Chromium twice, so not while work is running
make guard-check    # the same 18 with Jev's guard off: the gateway's guard must refuse them alone
```

It drives Jev's executor against the running Steel: every private route a page or click can
take (redirects, metadata, obfuscated loopback, compose names, fetch, workers, WebSockets,
popups, reattach after a relaunch) must be refused, and ordinary browsing must still work.
Some of those are stopped by Chromium's own Local Network Access check rather than by our
code, the WebSocket to Steel's CDP port among them. So this must pass against the **exact
pinned Steel image** on the droplet: a Steel update that ships a Chromium without that check
fails here, not in production.

Measured on a first run (2026-09-22, Apple Silicon, **linux/arm64** image — the amd64 droplet
will be slower, and its Chromium will not be smaller):

| | |
|---|---|
| `read https://news.ycombinator.com` | 2s wall, 6,712 chars of markdown, 50 links |
| screenshot on the same call | 371 KB JPEG, one extra page load |
| `fetch https://example.com` | sub-second, no browser touched |
| steel container | 686 MB resident after a few pages, 895 MB after a dozen, against a 1.2 GB cap |
| gateway container | 45 MB resident against a 256 MB cap |
| agent-jev container | 134 MiB resident against a 384 MB cap, no browser of its own |
| agent-browseruse container | 38 MiB idle, 327 MiB peak during a task, against a 640 MB cap |
| steel during a task | 1.08 GiB of its 1.17 GiB cap: Hacker News with 646 comments open, `act`'s tab open beside it. The benchmark's form task peaked at 1.17 GiB, so the cap is now 1.5 GiB |

Steel's own Chromium is what eats the memory, and it is the number to watch: it **climbs
with use** — 686 MB after a handful of pages, 895 MB after a dozen — which is exactly how a
2 GB box with no swap ends up OOM-killing a Chromium rather than failing loudly. `make
restart-browser` resets it, and the cap in `compose.yml` is what turns a leak into a
restart instead of a dead host.

`make smoke` finishes by driving the endpoint with a real MCP client — `initialize`,
`notifications/initialized`, session headers, SSE negotiation — because raw JSON-RPC over
curl skips all of that, and "it should work statelessly" is exactly the kind of assumption
that produced the last system. Both `/mcp` and `/mcp/` are checked, and so is the refusal of
a client with the wrong token.

## Three ways to talk to it

All three hit the same gateway, the same tools, the same token. There is no privileged
back door that can drift from what agents see.

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
bb read -t -s -o shot.jpg https://news.ycombinator.com  # real browser + screenshot to a file
bb session create                                  # a logged-in profile to reuse
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

Ubuntu 24.04, Docker Engine, 2 GB swap, UFW allowing only 22, 80 (the certificate challenge) and 443,
`python3-venv` (for `make venv` and `make smoke`), Caddy on the host (not in compose, so a
stack restart never drops TLS).

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

**Size the box for a browser.** 2 vCPU / 4 GB. A 1 vCPU / 2 GB droplet is the configuration
whose watchdogs blew and whose Chromium the kernel OOM-killed under exactly this workload —
DOM extraction plus screenshots on one core. It will run; it will not be comfortable.

## Develop

```bash
make venv     # once
make test     # 167 tests, no Docker, no browser and no API key needed
```

The tests cover the SSRF guards — all four obfuscated-loopback forms, inward DNS answers,
the redirect-into-loopback exploit proven live, and the rule that the browser is handed the
cleared final URL — plus the single-flight lane, the tool result shapes, and the fact that
the gateway refuses to start unauthenticated and refuses to answer without a token. The CLI's
`ask` loop is tested against a stub model, so the suite needs no key and spends nothing, and
the plugin manifests are checked against the real tool list so a command cannot allow-list a
tool that does not exist.

## Layout

```
compose.yml          steel + gateway (+ agent-jev, profile jev; agent-browseruse, profile browseruse),
                     loopback-only, memory and CPU capped
Caddyfile            TLS and the only public surface (install on the host)
gateway/
  gateway/
    server.py        MCP over streamable HTTP, bearer-gated
    tools.py         the tools and their cards
    steel.py         REST client for the self-hosted browser
    orgo.py          Orgo cloud computers — every path and body from Orgo's own docs
    jev.py           client for agent-jev, the model behind act
    browseruse.py    client for agent-browseruse, the agent behind task(surface="browser")
    guard.py         the in-browser guard: one CDP client checking every request Chromium makes
    lock.py          the single browser lane
    security.py      URL scope classification — port this, never rewrite it
agents/browseruse/   Browser-Use in a container: server.py (no browser_use import; runs, times out, kills,
                     cleans up tabs) and runner.py (one task, confined to its own tab)
cli/                 the `bb` command line (its own package, pipx-installable)
.claude-plugin/      plugin + marketplace manifests
skills/ commands/    what the plugin teaches an agent
scripts/smoke.sh     the end-to-end proof
scripts/guard_probe.py  the in-flight redirect attack, run by smoke
tests/               167 tests; scope_vectors.json is shared with jev-automation
```
