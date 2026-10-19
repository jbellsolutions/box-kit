# browser-box CLI

**Your own browser box from the command line, plus the memory the box does not keep: call history, a page cache, full-text search and batched reads that retry busy refusals.**

browser-box is a gateway on your own server, behind one token, that hands out hosted browsers. This CLI calls every tool it offers (fetch, read, session, act, task, computer, status) and writes each call it makes through to a local ledger, so history, find and cache work long after the box has forgotten. The ledger sees only calls made through this CLI or its own MCP server, not other clients of the box. queue read serializes a list of reads and retries a "busy" refusal.

## Install

This CLI lives in the private `jbellsolutions/browser-box` repo, in `pp-cli/`. It is not in the
public Printing Press library, so `npx … printing-press-library` and `go install github.com/…@latest`
do not apply. Build it from a clone (Go 1.26.6 or newer):

```bash
git clone git@github.com:jbellsolutions/browser-box.git
cd browser-box
make cli
```

`make cli` runs `cd pp-cli && go install ./cmd/browser-box-pp-cli ./cmd/browser-box-pp-mcp`, which
puts both binaries in `$(go env GOPATH)/bin` (usually `~/go/bin`). Put that directory on your
`PATH`. `make cli-test` runs the tests.

## Agent skill

`SKILL.md` in this directory is the agent skill. Copy it into your agent's skills directory as
`pp-browser-box/SKILL.md`: for example `~/.claude/skills/pp-browser-box/` for Claude Code, or
`~/.hermes/skills/pp-browser-box/` for Hermes. Then restart the agent session.

## Use as an MCP server

`browser-box-pp-mcp` exposes the same commands as MCP tools over stdio. Every call it makes goes
into the same local ledger as the CLI. Claude Desktop config
(`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "browser-box": {
      "command": "browser-box-pp-mcp",
      "env": {
        "BROWSER_BOX_BASE_URL": "https://<your-box>",
        "BROWSER_BOX_TOKEN": "<your-token>"
      }
    }
  }
}
```

Claude Code: `claude mcp add browser-box -e BROWSER_BOX_BASE_URL=https://<your-box> -e BROWSER_BOX_TOKEN=<your-token> -- browser-box-pp-mcp`.

If your agent speaks MCP over HTTP, it can use the box's own `/mcp` endpoint directly instead. That
endpoint has the same seven tools but no ledger.

## Authentication

One bearer token, BB_TOKEN from the box's .env. Export it as BROWSER_BOX_TOKEN. Point the CLI at your box with BROWSER_BOX_BASE_URL (for example https://your-box.example.com).

## Quick Start

```bash
# Checks config and token, and that the box answers
browser-box-pp-cli doctor

# What is up on the box, what is down and why
browser-box-pp-cli status --agent

# Read a page in the box's real browser
browser-box-pp-cli read --url https://example.com --agent

# The call you just made, now in your local ledger
browser-box-pp-cli history --agent

```

## Unique Features

These capabilities aren't available in any other tool for this API.

### Local memory the box does not keep
- **`history`** — See every call you made through this CLI, what it cost and why it failed, long after the box forgot it.

  _Reach for this before re-running a task to check whether it already ran, failed, or cost too much._

  ```bash
  browser-box-pp-cli history --tool task --since 7d --agent
  ```
- **`cache`** — Get a page you already read back instantly, without opening a browser.

  _Use it instead of read when the page was read recently and freshness does not matter; it opens no browser and costs nothing._

  ```bash
  browser-box-pp-cli cache https://news.ycombinator.com --agent
  ```
- **`find`** — Ask which page you read said something, across everything read so far.

  _Use it to recover a fact from earlier reading without re-opening pages._

  ```bash
  browser-box-pp-cli find "example domain" --agent --select url,title
  ```

### Batching reads
- **`queue read`** — Read a list of pages one after another, retrying when the box answers "busy".

  _Use it whenever you have more than one URL to read; it retries a busy refusal for you. Reads on the box run in parallel anyway, so this is for politeness and a tidy ledger, not a queue the box needs._

  ```bash
  browser-box-pp-cli queue read https://example.com https://news.ycombinator.com --agent
  ```
- **`alias`** — Name an open browser session so you can tell later which one it is and release it.

  _Use it to keep track of which open session is which; pass its session_id to read or act to work in that browser. Sessions are fresh and logged out._

  ```bash
  browser-box-pp-cli alias get crm --agent
  ```
- **`drift`** — See only what changed on the box since you last looked.

  _Use it at the start of a session to spot a component that went down since the last run._

  ```bash
  browser-box-pp-cli drift --agent
  ```

## Recipes

### Read a page and keep only what matters

```bash
browser-box-pp-cli read --url https://news.ycombinator.com --agent
```

Rendered read in a hosted browser: title, final URL, text and links as JSON.

### Drive the browser in plain words

```bash
browser-box-pp-cli act --command "open https://news.ycombinator.com then click new" --agent
```

Jev picks each element in about 0.3 s; a needs_clarification or needs_confirmation answer is resolved with --pick or --confirm.

### Batch-read several pages

```bash
browser-box-pp-cli queue read https://example.com https://news.ycombinator.com --agent
```

Serializes the reads and retries "busy" refusals.

### Find something you read earlier

```bash
browser-box-pp-cli find "example domain" --agent --select url,title,snippet
```

Full-text search over cached pages with the output narrowed to three fields; no browser call.

### Hand off a goal and check its cost

```bash
browser-box-pp-cli task --goal "Find the top story on news.ycombinator.com and report its title" --agent
```

Browser-Use does the whole goal and answers with status, answer, steps and estimated_cost_usd; history --tool task shows what tasks have cost.

### What did the box cost this week

```bash
browser-box-pp-cli history --tool task --since 7d --agent --select tool,summary,status,cost_usd
```

The local ledger keeps every call; the box itself forgets after 10.

## Usage

Run `browser-box-pp-cli --help` for the full command reference and flag list.

## Paths & environment variables

This CLI separates local files into four path kinds:

| Kind | Contents |
|------|----------|
| `config` | User-editable settings such as `config.toml` and saved profiles |
| `data` | Durable local data: `credentials.toml`, `data.db`, cookies, browser-session proof files, and other auth sidecars |
| `state` | Runtime state such as persisted queries, jobs, and `teach.log` |
| `cache` | Regenerable HTTP/cache files |

Each kind resolves independently. The ladder is:

1. Per-kind env var: `BROWSER_BOX_CONFIG_DIR`, `BROWSER_BOX_DATA_DIR`, `BROWSER_BOX_STATE_DIR`, or `BROWSER_BOX_CACHE_DIR`
2. `--home <dir>` for this invocation
3. `BROWSER_BOX_HOME` for a flat relocated root
4. XDG env vars: `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`
5. Platform defaults matching existing installs

For containers and agent sandboxes, prefer a single relocated root:

```bash
export BROWSER_BOX_HOME=/srv/browser-box
browser-box-pp-cli doctor
```

Under `BROWSER_BOX_HOME=/srv/browser-box`, the four dirs resolve to `/srv/browser-box/config`, `/srv/browser-box/data`, `/srv/browser-box/state`, and `/srv/browser-box/cache`.

MCP servers do not receive CLI flags from the host. Put relocation in the host `env` block:

```json
{
  "mcpServers": {
    "browser-box": {
      "command": "browser-box-pp-mcp",
      "env": {
        "BROWSER_BOX_HOME": "/srv/browser-box"
      }
    }
  }
}
```

Precedence matters in fleets: an ambient per-kind variable such as `BROWSER_BOX_DATA_DIR` overrides an explicit `--home` for that kind. Use `BROWSER_BOX_HOME` or the per-kind variables for durable fleet relocation; treat `--home` as the weaker per-invocation lever.

Relocation is one-way. Unsetting `BROWSER_BOX_HOME` does not move files back to platform defaults, and `doctor` cannot find credentials left under a former root. Move the files manually before unsetting relocation variables.

Existing installs keep working because the platform-default rung matches the legacy layout. On the first auth write, stored secrets leave `config.toml` and are consolidated into `credentials.toml` under the data directory. Run `browser-box-pp-cli doctor --fail-on warn` to check path and credential-location warnings in automation.

## Commands

### act

Manage act

- **`browser-box-pp-cli act`** - Drive the browser step by step in plain words: "open https://…", "click the Pricing link", "type 'running shoes' into the search box and press enter", "scroll down", "go back". You plan the steps; Jev, a decision model that never writes text, picks which element on the page each step means (typically ~0.3 s; page loads take longer). Up to 4 steps joined by "then" or "and" run in order.
When Jev is unsure it asks instead of guessing: status needs_clarification with options — answer with act(pick=<option pick>). Anything that looks hard to undo (buy, delete, send, post) comes back as needs_confirmation — answer with act(confirm=true) or act(confirm=false). Nothing risky runs unconfirmed.
Prefer act over task whenever you can say the steps: measured on search, forms, pagination, state and a JS app, it was 10–60x faster and as or more accurate on all but search (see the README). Read each step's did: a click on a link marked (page does not exist) is a wrong pick, so say which one you meant.
Use for clicking, typing, forms and multi-page flows. Do NOT use just to read a public page: fetch or read is cheaper. The tab stays where you left it between calls. Give session_id to work in a browser of your own (see session); without it act uses one shared scratch browser that closes after a few idle minutes. Every browser is fresh and logged out.
Private and internal addresses are refused: every URL is checked before it opens, and a step that lands off the public web is undone and reported as refused.
Returns: status (done | failed | needs_clarification | needs_confirmation), steps (what ran and how each went), url, title, and the page's text when read_page=true.

### computer

Manage computer

- **`browser-box-pp-cli computer`** - Drive an Orgo cloud computer: a full Linux desktop with a browser and a shell, running OFF this box. You are the eyes — take a screenshot, decide, act, screenshot again. Coordinates are pixels in the most recent screenshot.
Actions: screenshot | click(x, y[, button, double]) | type(text) | key(key, e.g. "Return", "ctrl+c") | scroll(x, y[, direction, amount]) | bash(command) | start | stop.
Do NOT use for a web page that fetch or read can answer: this is a whole computer, billed per hour.
bash is a real shell on that computer, inside your Orgo account.
A computer bills until it is stopped. Call action=stop when you are finished.

### fetch

Manage fetch

- **`browser-box-pp-cli fetch`** - Plain HTTP GET, no browser. Fastest and free. Use it FIRST for any page that is server-rendered HTML, JSON or plain text — news sites, docs, APIs, RSS.
Do NOT use when: the page needs JavaScript to render, is behind a login, or blocks bots.
Returns: text (HTML stripped to readable text), status_code, final_url.

### read

Manage read

- **`browser-box-pp-cli read`** - Open a URL in the real browser and return its rendered text, links and optionally a screenshot. Use when fetch returned nothing useful because the page renders with JavaScript.
Do NOT use when: fetch already answered (this costs a browser slot), or the task needs clicking and typing rather than reading.
Each read gets its own hosted browser (Browser Use Cloud, when status shows it), so reads run side by side up to the plan's limit; there is no queue on this host. If that browser fails or the site blocks it, engine="auto" falls back to Browserbase when configured; the result's engine and fallback_reason say which ran and why. Reads are public and logged out: never for a page that needs a session.
The screenshot is of the same page load the text came from. Ask for it when the picture is the evidence.
Returns: text, title, links, status_code, and screenshot_base64 (JPEG) when asked for.

### session

Manage session

- **`browser-box-pp-cli session`** - A browser of your own that stays open between calls, so act can work a page step by step and several agents can each drive their own at the same time. Every session is fresh and logged out, and is forgotten when it closes: this box keeps no logins and never uses a saved profile.
create -> a new session, with its browser open: returns session_id and live_url (a view of that browser).
list   -> the sessions open now.
release -> close the session's browser; the session is gone. There is no login and no delete.
A session runs one browser at a time: calls on the same session_id wait for each other; different sessions run side by side. An idle session's browser closes itself after a few minutes, and the session with it. live_url lets whoever holds it drive that browser: keep it to yourself.
Do NOT create a session for public pages: read and act without session_id use a fresh, logged-out browser.

### status

Manage status

- **`browser-box-pp-cli status`** - What is running, what is healthy, and what the last calls cost. Call this when a tool fails, before assuming a capability is missing. It answers honestly: a component that is down is reported as down, with the reason.

### task

Manage task

- **`browser-box-pp-cli task`** - Hand a whole goal to an agent and wait for its answer. Use it when you would rather not plan the steps yourself; you lose sight of each step, and every step costs model time.
Measured against act: 30–130 s per job, and less reliable. It failed a two-URL cookie job 2 of 3 times and a JS to-do app 3 of 3. Check its answer before trusting it.
surface="browser": Browser-Use works the goal in a hosted browser of its own, with a model choosing each step (one model call per step; a few steps take ~10-40 s). Several tasks run side by side, with no cap of ours. A task takes no session_id and always runs in a fresh, logged-out browser. Its browser is stopped when it finishes: to look at the last page again, read final_url. Returns status (done | failed | incomplete | timed_out | cancelled | stopped), answer, steps, urls, final_url, tokens and estimated_cost_usd.
It runs until it finishes even if you stop waiting: this endpoint cannot hear a client give up. task(cancel=true) stops every running browser task, and each still reports what it did.
surface="computer": Orgo's hosted computer-use agent (Claude) works an Orgo desktop until the goal is done. Orgo ignores max_steps and caps its loop at 250 steps; timeout_seconds is the real bound, and hitting it aborts the run.
Do NOT use when one fetch or read answers it, or when you can drive the steps yourself with act or computer: that is faster, cheaper and you see every step.

### tools

Manage tools

- **`browser-box-pp-cli tools`** - The tools this box offers right now, with their input schemas


### Self-learning loop

This CLI caches per-question discovery so repeat queries skip the walk and structurally similar queries get answered via entity substitution. The loop also self-captures: every invocation is journaled locally, and failed-flag corrections plus fresh teaches surface as candidates on the next `recall` for confirm/reject judgment. Agents call `recall` before discovery and fire `teach &` after answering. See the `## Automatic learning` section in `SKILL.md` for the full protocol.

- **`browser-box-pp-cli recall <query>`** - Look up cached resources for a query before running discovery
- **`browser-box-pp-cli teach`** - Record a query -> resource mapping (silent on success, safe to background with `&`)
- **`browser-box-pp-cli learnings list`** - Inspect taught rows
- **`browser-box-pp-cli learnings forget <query>`** - Undo a teach
- **`browser-box-pp-cli learnings candidates`** - List auto-captured candidates awaiting confirm/reject
- **`browser-box-pp-cli learnings stats`** - Local loop metrics: recall hit rate, teach-to-reuse, playbook resolution, candidate counts
- **`browser-box-pp-cli teach-pattern`** - Install a query/resource template up front
- **`browser-box-pp-cli teach-lookup`** - Add an entity mapping (e.g. country code, team alias) for pattern substitution

Pass `--no-learn` or set `BROWSER_BOX_NO_LEARN=true` to disable the loop for deterministic flows.

The local store's schema version stamp is one-way: once this version of `browser-box-pp-cli` opens the database, older binaries refuse it with a version error — upgrade the binary rather than downgrading.

## Output Formats

```bash
# Human-readable table (default in terminal, JSON when piped)
browser-box-pp-cli fetch --url https://example.com

# JSON for scripting and agents
browser-box-pp-cli fetch --url https://example.com --json
# Filter to specific fields by name
browser-box-pp-cli fetch --url https://example.com --json --select <field>[,<field>...]

# Dry run — show the request without sending
browser-box-pp-cli fetch --url https://example.com --dry-run

# Agent mode — JSON + compact + no prompts in one flag
browser-box-pp-cli fetch --url https://example.com --agent
```

## Agent Usage

This CLI is designed for AI agent consumption:

- **Non-interactive** - never prompts, every input is a flag
- **Pipeable** - `--json` output to stdout, errors to stderr
- **Filterable** - `--select <field>[,<field>...]` returns only fields you need
- **Previewable** - `--dry-run` shows the request without sending
- **Explicit retries** - add `--idempotent` to create retries when a no-op success is acceptable
- **Explicit confirmation** - `--agent` does not imply `--yes`; pass `--yes` separately only after the target, arguments, and side effects are clear
- **Piped input** - write commands can accept structured input when their help lists `--stdin`
- **Offline-friendly** - local memory: history, cache and find answer from the ledger this CLI writes on every call, with no call to the box. sync, search, import, export and workflow are hidden: the box has no listable resources for them to act on
- **Agent-safe by default** - no colors or formatting unless `--human-friendly` is set

Exit codes: `0` success, `2` usage error, `3` not found, `4` auth error, `5` API error, `7` rate limited, `10` config error.

## Health Check

```bash
browser-box-pp-cli doctor
```

Verifies configuration, credentials, and connectivity to the API.

## Configuration

Run `browser-box-pp-cli doctor` to see the resolved config, data, state, and cache directories. The platform-default config path is `~/.config/browser-box-pp-cli/config.toml`; `--home`, `BROWSER_BOX_HOME`, and per-kind env vars can relocate it.

Static request headers can be configured under `headers`; per-command header overrides take precedence.

Environment variables:

| Name | Kind | Required | Description |
| --- | --- | --- | --- |
| `BROWSER_BOX_TOKEN` | per_call | Yes | The box's BB_TOKEN (from its .env). |
| `BROWSER_BOX_BASE_URL` | config | No | The box's origin, e.g. `https://your-box.example.com`. |
| `BROWSER_BOX_NO_LEDGER` | config | No | Set to any value to stop writing the local call ledger. |

### agentcookie (optional)

If you use agentcookie to sync secrets across machines, this CLI auto-adopts agentcookie-managed credentials with no extra setup. When the daemon writes to this CLI's config, `browser-box-pp-cli doctor` reports `agentcookie: detected` and `auth status` labels the source as `agentcookie`. Skip this section if you don't use agentcookie - the CLI works the same as any other.

## Troubleshooting
**Authentication errors (exit code 4)**
- Run `browser-box-pp-cli doctor` to check credentials
- Verify the environment variable is set: `echo $BROWSER_BOX_TOKEN`
**Not found errors (exit code 3)**
- `alias get` exits 3 for an alias that does not exist: `browser-box-pp-cli alias list` shows yours

### API-specific
- **HTTP 422 busy** — A session or an Orgo computer is in use by another call: batch your reads with browser-box-pp-cli queue read, which waits and retries
- **Busy because another call is using that session's browser** — Wait, or use another session; a browser task no longer holds a session
- **HTTP 422 refused: private or loopback address** — The box only reaches the public web; use a public URL
- **HTTP 404 tool is not offered on this box** — Run browser-box-pp-cli status to see which component or key is missing
- **HTTP 401 unauthorized** — export BROWSER_BOX_TOKEN with the BB_TOKEN from the box's .env

## Sources & Inspiration

This CLI was built by studying these projects and resources:

- [**browser-use**](https://github.com/browser-use/browser-use) — Python (116053 stars)
- [**agent-browser**](https://github.com/vercel-labs/agent-browser) — Rust (43111 stars)
- [**steel-browser**](https://github.com/steel-dev/steel-browser) — TypeScript (7684 stars)

Generated by [CLI Printing Press](https://github.com/mvanhorn/cli-printing-press)
