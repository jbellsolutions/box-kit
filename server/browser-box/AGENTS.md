# AGENTS.md — working in and with browser-box

Read [CHARTER.md](CHARTER.md) first. It is short, and it governs everything below.

There are two kinds of agent here: those **using** the box (browsing for a user) and those
**changing** this repo. Both sections apply to you if you do both.

## Using the box

**Connect.** One URL, one bearer token (`BROWSER_BOX_URL`, `BROWSER_BOX_TOKEN`).
- MCP: `https://<box>/mcp` (streamable HTTP). Setup for Claude Code, the plugin and Hermes:
  [docs/integrations.md](docs/integrations.md).
- HTTP/JSON: `POST https://<box>/api/v1/<tool>` with the tool's arguments as the body;
  `GET /api/v1/status`; spec at `GET /openapi.json`. See [docs/tools.md](docs/tools.md).
- Command line: `bb` (Python, [cli/](cli/)) or `browser-box-pp-cli` (Go, [pp-cli/](pp-cli/)),
  which also keeps a local history, page cache and search of everything you read.

**Choose the tool.**

| You need | Use | Not |
|---|---|---|
| A page's text, and it is server-rendered | `fetch` | `read` (a paid hosted browser) |
| A page that needs JavaScript, or a screenshot | `read` | `task` |
| Several steps you can name: open, click, type, scroll | `act` (up to 4 steps joined by "then") | `task` (slower, and failed state and SPA jobs in the benchmark) |
| A whole goal you would rather not plan, e.g. a search | `task(surface="browser")` | `act` |
| A browser of your own across several `act` calls, or one per agent | `session` create, pass its `session_id` to `act` and `read`, `release` when done | a session for a one-off read |
| A logged-in site | not this box: it keeps no logins. Use a tool built for it (for example a lead-gen tool) | `session`, which is always logged out |
| A full desktop | `computer` (you drive from screenshots) or `task(surface="computer")` | `read` |
| To know why something failed | `status` | guessing |

**Read the answers.**
- A refusal (`{"error": ...}`, HTTP 422 on the JSON door) is an answer: private address, a cap
  reached, a session busy, component down. Report it; do not retry a refusal unchanged, except
  "session busy" (another call is using that session's browser), which clears.
- `act` returning `needs_clarification`: answer with `act(pick=...)`. `needs_confirmation`: the
  step looks hard to undo. **Ask the user**, then `act(confirm=true|false)`.
- `task` keeps running if you stop waiting. `task(cancel=true)` stops every running browser task and
  its hosted browser.
- A result with `engine: "browserbase"` ran on the emergency lane; `fallback_reason` says why. `read`,
  `act` (any session) and `task` can fall back when Browser Use cannot open a browser.
- A `session` is gone once released or closed when idle; a call with its id is refused. Create a new one.
- `computer` bills per hour until `action="stop"`.

**Be a good neighbour.** Every read and task is a paid hosted browser, and the box shares one
Browser Use account and monthly cap among all its callers. Use `fetch` when it answers, keep
`read` screenshots for when the picture is the evidence, and cancel tasks you abandon. Release a
`session` when you finish with it.

## Changing the repo

**Layout.** `gateway/gateway/` is the whole server: `tools.py` (tool cards and handlers),
`server.py` (MCP + auth + the shared `run_tool`), `rest.py` (HTTP/JSON door and OpenAPI),
`security.py` (URL scope; port it, never rewrite it), `cloud.py` (Browser Use Cloud),
`sessions.py` (fresh browsers kept open between calls), `stepper.py` and `decide.py` (act and its decision model),
`browserbase.py` (the emergency lane), `lock.py` (the lane lock, for Orgo computers only), and
clients for Browser-Use and Orgo. `agents/browseruse/` is the Browser-Use container. There is no
browser on this host. `tests/` holds the suite. Details: [docs/architecture.md](docs/architecture.md).

**Commands.**

```bash
make venv          # once
make test          # the full suite: no Docker, browser or API key needed
make openapi       # after any tool-card change; commit docs/openapi.json
make plugin        # validate plugin + marketplace manifests
make up && make smoke        # the end-to-end proof against a running stack
```

Run the suite directly with `PYTHONPATH=gateway .venv/bin/python -m unittest discover -s tests -t .`.
Without `PYTHONPATH=gateway` you get import errors that are not real failures.

**Rules for changes.**
- Branch, test first (a test that fails without your change), then the change. Pull request into
  `main`; never push to `main` directly.
- A new tool or surface needs: its card in `tools.py`, a handler, tests, a regenerated
  `docs/openapi.json`, a README row, a `docs/tools.md` entry, a skill update, and a live smoke run.
- Never weaken `security.py`, `safe_target`, the Orgo lane or a spend cap to make something pass. If
  a test of those fails, the change is wrong until proven otherwise.
- Keep numbers in docs measured and dated. If you cannot measure it, do not state it.
- Commit messages end with the co-author line your harness requires.

**Deploying** is the user's call, every time. The runbook is [docs/operations.md](docs/operations.md).
The live box has no GitHub credentials: code arrives as a `git bundle`.

## Related repositories

- Jev's own repository. This repo no longer builds from it (the
  `agent-jev` container, `JEV_DIR` and `JEV_REF` are gone; `act` calls TypeSafe's decision API
  directly). Its work in progress is not yours to change from here.
