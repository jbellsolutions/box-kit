# Calling browser-box

browser-box is a **service you call**, not code you copy. One box runs the browsers; agents reach
it over MCP or HTTP with a URL and a token. If you are building an agent, a worker or a pipeline
that needs a browser, this page is all you need. You do not clone this repo, run `make up`, or
add a browser to your own project.

If you are about to put browser-box in another project's `compose.yml`, stop and read
[self-host.md](self-host.md) first. Copies are how one box became five.

## What you need

Two values, kept in your project's environment, never in code:

| Variable | What it is |
|---|---|
| `BROWSER_BOX_URL` | The box's MCP endpoint, ending in `/mcp`. The operator gives it to you; the live box is listed in [operations.md](operations.md). |
| `BROWSER_BOX_TOKEN` | The bearer token for that box. |

**Tokens today:** the box has one shared token (`BB_TOKEN` on the box). A token per caller, with
its own allowed tools and limits, comes with the multi-browser gateway. Until then, treat the
token as a password: keep it in `.env` files that are gitignored, and never print it.

## MCP

Every client below speaks streamable HTTP to the same endpoint and sees the same tools.

**Claude Code**

```bash
claude mcp add --transport http browser-box "$BROWSER_BOX_URL" \
  --header "Authorization: Bearer $BROWSER_BOX_TOKEN"
```

**Codex**

```bash
codex mcp add browser-box --url "$BROWSER_BOX_URL" --bearer-token-env-var BROWSER_BOX_TOKEN
```

**Hermes** (`config.yaml` under `mcp_servers`; the token goes in the profile's `.env`):

```yaml
browser-box:
  url: ${BROWSER_BOX_URL}
  headers:
    Authorization: Bearer ${env:BROWSER_BOX_TOKEN}
  connect_timeout: 60
  timeout: 960      # a browser task runs up to 900 s; raise to 1860 for computer tasks
  enabled: true
```

Then `hermes mcp test browser-box` from the profile you configured.

**Any other MCP client:** URL `$BROWSER_BOX_URL`, header `Authorization: Bearer <token>`,
transport streamable HTTP. Allow at least 960 s for a call: a browser `task` can run for 900 s,
and a computer `task` for up to 1800 s.

## HTTP/JSON

No MCP client needed. The base is the same URL without `/mcp`:

```bash
BASE="${BROWSER_BOX_URL%/mcp}"

# what this box offers right now
curl -fsS "$BASE/api/v1/tools"  -H "Authorization: Bearer $BROWSER_BOX_TOKEN"
curl -fsS "$BASE/api/v1/status" -H "Authorization: Bearer $BROWSER_BOX_TOKEN"

# one call
curl -sS "$BASE/api/v1/read" \
  -H "Authorization: Bearer $BROWSER_BOX_TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "https://news.ycombinator.com"}'
```

`POST /api/v1/<tool>` takes the tool's arguments as a JSON object. A 200 is the tool's result.
A 422 carries `{"error", "tool"}`: a refusal, or a part of the box that is down. The full shapes
are in [tools.md](tools.md) and `docs/openapi.json`.

## Before your first call

1. Call `status` (or `GET /api/v1/status`). It lists the tools that work right now and why any
   tool is down. A tool that is not listed is not configured on that box.
2. Read [choosing.md](choosing.md). Picking the cheapest tool that can do the job is the caller's
   part of the contract.
3. Every `read`, `act` scratch browser and `task` runs on a hosted browser of its own, so calls do
   not queue behind each other. At the plan's browser limit, or the box's monthly cap, a call is
   refused with a message saying so (or, for logged-out work, falls back to Browserbase and says
   `engine: "browserbase"`); retry later, or use `fetch`. Calls on one `session_id` wait for each
   other and then answer "busy"; `computer` answers busy while another call drives that desktop.

## What the box guarantees

- **Only the public web.** Loopback, private, link-local and internal addresses are refused before
  a browser opens or a request is made, `fetch` clears every redirect hop, and a page that lands
  off the public web is dropped ([security.md](security.md)).
- **One door, same answer.** MCP and HTTP run the same handlers with the same checks.
- **It says what it did.** Results name the page that was actually read (`final_url`), and paid
  work reports its cost. `status` shows recent calls and spend.
- **Hard-to-undo steps wait for you.** `act` returns `needs_confirmation` before a step that
  buys, deletes, sends or posts.

## What the box does not do for you

- Plan multi-step work. You are the brain; `act` takes steps you write, and only `task` plans on
  its own (slower and paid, see [choosing.md](choosing.md)).
- Log in for you, or remember a login. It keeps no logins and never touches a Browser Use profile:
  every browser, including a `session`'s, is fresh and logged out. Agents never type passwords. Work
  behind a login belongs to a tool built for it.
- Guarantee a CAPTCHA is solved. Solving is on by default (`BB_SOLVE_CAPTCHAS=1`) on both providers,
  but a challenge the provider cannot solve still comes back as a failed or blocked read.
