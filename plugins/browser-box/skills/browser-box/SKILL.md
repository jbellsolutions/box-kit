---
name: browser-box
description: Read, fetch, screenshot, click through any public web page through hosted browsers behind one gateway, hand it a whole browsing goal, and stand that gateway up on a VPS when it isn't running yet. Use when asked to "read this page", "what does this site say", "get the data from", "screenshot this", "fill in this form", "click through", "scrape", "go find out", or when a WebFetch was blocked, returned JavaScript instead of content, or hit a bot check. Also use for "is the browser box up", "start the browser box", "deploy browser-box".
allowed-tools: Bash, Read
---

# browser-box — one browser, one door

A **single gateway** in front of **hosted browsers** (Browser Use Cloud; Browserbase as the
emergency lane), over MCP. The host runs no browser. **You are the brain**, the box is the hands.
Two models can run in it, both opt-in: Jev (behind `act`) only picks which element a step means;
Browser-Use (behind `task`) plans steps for a goal you hand over. Neither decides what you are
trying to do.

Repo: `https://github.com/jbellsolutions/browser-box`

---

## Part 1 — Using it

### The tools

| Tool | Use it for | Cost |
|---|---|---|
| `fetch` | **Try this first.** Plain HTTP GET — server-rendered HTML, JSON, APIs, RSS, docs | free, instant |
| `read` | A hosted browser. Use when `fetch` came back empty or unrendered | ~$0.0003 a read |
| `session` | A fresh, logged-out browser of your own that stays open between calls, for `act` (no logins, ever) | browser time while open |
| `act` | Drive the browser in plain-words steps you plan: open, click, type, scroll | TypeSafe decisions + browser time |
| `task` | Hand a whole goal to an agent: `surface="browser"` (Browser-Use on a hosted browser) or `"computer"` (an Orgo desktop) | model tokens, reported per task, plus browser time |
| `computer` | A full Orgo cloud desktop you drive yourself: screenshot → decide → click/type/key/scroll/bash | Orgo, per hour |
| `status` | What is up, what is down, why, and what recent calls cost | free |

Everything but `fetch` and `status` is **listed only when the box has it configured**: `read`
needs a Browser Use or Browserbase key, `session` a Browser Use key, `act` a Browser Use key and a
TypeSafe key, `computer` an Orgo key. `task` lists only the surfaces it has. If you don't see one, this box doesn't have it — `status`
says so. There is no provider catalog, no readiness
walkthrough, no plan/verify/resume, no doctor variants. **If a tool is listed, it works.** If it
can't work right now, `status` says so in one line with the reason.

### The one rule that saves the most time

**`fetch` before `read`, every time.** Most pages are server-rendered; `fetch` answers them
instantly and for free. `read` opens a paid hosted browser (about $0.0003, a few seconds) and
counts against the box's monthly cap. Burning one on a page `fetch` could have answered is the
main way to make this slow and costly.

Escalate to `read` when `fetch` returns almost no text, returns a shell of `<script>` tags,
or returns a bot-check page.

### Clicking and typing: `act` or `task`?

**Measured (5 jobs × 3 runs, on the retired Steel engine; not rerun on hosted browsers):**
- `act` went 3/3 on forms, pagination, cookie state and a React to-do app, in 0.5–5 s.
- `task` took 30–130 s and failed the cookie job 2 of 3 times and the to-do app 3 of 3.
- Default to `act`. `act`'s one miss: asked for the first search result on Wikipedia, it clicked a red
"page does not exist" link. Read each step's `did` and correct it in the next turn.

**`act` when you can plan the steps.** Say each step in plain words — `"open https://…"`,
`"click the Pricing link"`, `"type 'running shoes' into the search box and press enter"` — up
to 4 joined by `then`. Jev picks the element in ~0.3 s; you see every step's outcome.
- `needs_clarification` → it wasn't sure which element you meant: answer `act(pick=<option>)`.
- `needs_confirmation` → the step looks hard to undo (buy, delete, send, post): answer
  `act(confirm=true|false)`. Nothing risky runs unconfirmed.
- It returns the URL and title, not the page's text: pass `read_page=true` to get the page's text,
  or `read(url)` (a fresh, logged-out load, so it will not show what you typed into a form).
- The tab stays where you left it between calls. Give `session_id` to work in a browser of your own;
  without it `act` uses one shared scratch browser that is forgotten after a few idle minutes. Every
  browser is fresh and logged out.

**`task(surface="browser")` when you would rather hand over the goal.** Browser-Use plans
each step with its own model. You get the answer, every step, the URLs, tokens and cost.
- A job takes ~30–130 s and under a cent; hand over what you would
  otherwise spend many turns steering.
- It gets a hosted browser of its own, so several tasks can run at once and a task never touches
  `act`'s tab. Its browser is stopped when it finishes: `read(final_url)` to look again.
- **It keeps running if you stop waiting** until its `timeout_seconds`. Call `task(cancel=true)` to
  stop every running browser task; each stopped task still reports what it did.
- A task takes no `session_id`: it always runs in a fresh, logged-out browser of its own. How many
  run at once is bounded by the agent container's memory (`BROWSERUSE_MEMORY`, default 1200m, about
  100-300 MB per task), not by a cap of ours.

### Computer use (Orgo)

`computer` is a whole Linux desktop **off this box**, with a browser and a shell. **You are the
eyes:** call `computer(action="screenshot")` — it comes back as a real image you can see — then
act on pixel coordinates from that image, then look again. Pass `screenshot_after: true` on an
action to get the next image in the same call.

- `scroll` needs `x` and `y`; without them Orgo warps the pointer to the top-left corner.
- `bash` is a real shell on that computer, inside the Orgo account.
- **A computer bills until it is stopped.** There is no auto-stop. Finish with `action="stop"`.
- One job drives a given computer at a time; a second waits or is told it is busy. A busy
  computer never blocks the browsers.

Can't see images, or the goal is long? `task(goal, surface="computer")` hands it to Orgo's own
computer-use agent and returns its answer. You lose sight of each step, so prefer `computer` when you can drive.
Orgo ignores step limits (its loop caps at 250); `timeout_seconds` is the real bound, and
hitting it closes the stream, which aborts the run.

### Screenshots

`read(url, screenshot=true)` photographs the same page load the text came from, so the picture and
the text match. Ask for one when the picture is the evidence, not by default. Browserbase (the
emergency lane) returns text and links only, no screenshot.

### Sessions (a browser of your own)

```
session(action="create")                    -> session_id + live_url (a view of that browser)
session(action="list")
session(action="release", session_id="...") -> close the browser; the session is gone
```

A session is a fresh, logged-out browser that stays open between calls, so `act` can work a page
step by step and several agents can each have their own. Pass its `session_id` to `act` or `read`.
It keeps **no logins, ever**: there is no `login` or `delete` action, and this box never touches a
Browser Use profile. Logged-in work belongs to a tool built for it, not here.
Anyone holding the `live_url` can drive the browser, so keep it to yourself. A session runs one
browser at a time: calls on the same `session_id` wait for each other and then answer "busy";
different sessions run side by side. An idle session's browser closes itself after a few minutes and
the session is gone; a call with its id is refused, so create a new one. If Browser Use cannot open a
browser, Browserbase is used instead. Don't create a session for a one-off public read.

### Refusals are answers, not bugs

Every URL is checked before any browser opens or connection is made. Refused: loopback, private
ranges, link-local, cloud metadata, and obfuscated forms (`0x7f000001`, `2130706433`, `127.1`).
Hostnames are resolved and **every** returned address checked. `fetch` clears each redirect hop
before following it, and a page that lands off the public web is dropped.

If you get `{"error": "refused: ..."}` the target is internal and the check worked. Report it
plainly. **Do not try to route around it.**

If you get "session ... is busy", another call is using that session's browser: wait, or use
another session. If it says a task holds it, `task(cancel=true)` stops that task. If a result says
`engine: "browserbase"`, Browser Use could not serve it and the emergency lane did; `fallback_reason`
says why. Other refusals name a cap or an outage: `status` says which.

### When something fails

Call **`status` before concluding a capability is missing.** It reports a component that is
down as down, with the reason, and lists what still works (`fetch` and `status` always do).
An unreachable box and a broken browser are different problems with different fixes.

---

## Part 2 — Connecting to it

All three routes hit the same gateway, the same tools, the same token.

### MCP (preferred)

```bash
claude mcp add --transport http browser-box https://your-box/mcp \
  --header "Authorization: Bearer $BROWSER_BOX_TOKEN"
```

Or a project `.mcp.json` — both expansion forms are verified against Claude Code:

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

> `claude mcp list` prints the **raw** manifest text, not the expanded value. A literal
> `${...}` in that output is not a fault.

### CLI

```bash
pipx install ./cli          # from a clone; git+https needs auth while the repo is private
bb login --url https://your-box --token <BB_TOKEN>

bb status
bb fetch -t https://example.com
bb read  -t -s -o shot.jpg https://news.ycombinator.com
bb session create
bb act "open https://example.com then click More information"
bb task --surface browser "find the top story on news.ycombinator.com and its comment count"
bb task --cancel
bb tools
```

`bb ask "<goal>"` and `bb chat` run a model **in the CLI, on this machine** (needs
`OPENROUTER_API_KEY`). The box still has no brain in it. Everything else needs no key.

### Plugin

```
/plugin marketplace add jbellsolutions/browser-box
/plugin install browser-box@browser-box
```

Set `BROWSER_BOX_URL` and `BROWSER_BOX_TOKEN` first.

---

## Part 3 — Spinning it up

**Check first.** `bb status`, or `curl -fsS https://your-box/health`. A box that is already
running does not need provisioning, and `make up` on a live host is safe but pointless.

### Host requirements

**Ubuntu 24.04 with Docker.** No browser runs on the host, so there is no Chromium to size it
for: the compose caps are 256 MB (gateway) and 1200 MB (agent-browseruse). The live droplet is
2 vCPU / 4 GB; a smaller one has not been tried. You need a Browser Use Cloud key
(`BROWSER_USE_API_KEY`) in `.env`.

```bash
# Docker, swap, firewall
curl -fsSL https://get.docker.com | sudo sh
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile \
  && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo ufw allow 22 && sudo ufw allow 443 && sudo ufw --force enable
```

### Bring the stack up

```bash
gh repo clone jbellsolutions/browser-box && cd browser-box
cp .env.example .env
make token                      # paste the value into BB_TOKEN in .env
chmod 600 .env
make up                         # builds the gateway (and agent-browseruse if its profile is on)
make status
```

`make` targets: `up` · `down` · `status` · `logs` · `test` · `plugin` · `smoke` · `token` · `venv`.

### Egress

There is no host egress rule to apply. The browsers run on Browser Use's (and, in an emergency,
Browserbase's) network, which has no route to this host's loopback or compose network. The
checks that remain are in `docs/security.md`.

### TLS

Caddy on the **host**, not in compose, so a stack restart never drops TLS:

```bash
sudo apt-get install -y caddy   # or the official repo: caddyserver.com/docs/install

# Substitute the domain at install time. `BB_DOMAIN=x cp ...` does NOT work: cp does no
# substitution, and Caddy reads {$BB_DOMAIN} from the caddy SERVICE's environment, not
# from the shell that copied the file. An unset value yields an empty site address.
sudo sed "s|{\$BB_DOMAIN}|box.example.com|" Caddyfile | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl reload caddy
```

### Prove it

```bash
make smoke
```

Lists the tools, calls `status`, reads a real page with a screenshot, asserts that obfuscated
loopback is refused, asserts that a public redirect into loopback is refused, runs `act` and
`task` when they are offered, and drives the endpoint
with a **real MCP client** (initialize, session headers, SSE) on both `/mcp` and `/mcp/`.
If `make smoke` passes, the box works. If it doesn't, the failing line names what broke.

---

## What it deliberately does not do

- **No brain in the box by default.** A model inside the tool, in a different body from the
  hands, is the design that failed twice. The calling agent decides. `task` is the one opt-in
  exception, and it only plans the steps of a goal you hand it.
- **No browser on the host.** The browsers are hosted and run side by side,
  up to the Browser Use plan's limit. Browser-Use is an *agent* that needs a browser, not a
  browser: each task drives a hosted browser the gateway opened for it.

### Known limits, stated plainly

1. **DNS rebinding** — a name that checks public can resolve private a moment later. For `fetch`
   that is this host; for the hosted browsers it is the provider's network.
2. **Requests a page makes after it loads** are not seen by the gateway; it checks the URL it
   hands a browser and where the page landed.
3. **No logins, no profiles.** This box never creates, opens, reads or deletes a Browser Use profile
   (the account also holds other tools' logged-in profiles). A session's `live_url` lets its holder drive
   that browser.
4. **CAPTCHA solving is on, there is no proxy.** Solving follows `BB_SOLVE_CAPTCHAS` (default 1) on
   both providers. A wall the provider cannot solve comes back as a failed or blocked read, and may
   fall back to Browserbase, which returns text and links only.

> **Never clone browser-box to "use" it** — attach by URL. One deployment, one code path,
> work running on the box you already pay for. Clone only on the host you are deploying to.
> Cloning to "install" is how the last system ended up with divergent copies giving opposite
> answers about what worked.
