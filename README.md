# Box Kit

Two small servers that give any AI agent real web abilities, each behind one MCP endpoint:

| Server | What it gives your agent | Free out of the box | Add your own keys for |
|---|---|---|---|
| **browser-box** | A real browser it drives: read JavaScript pages, click, type, log in and stay logged in, screenshots | `fetch`, `read`, `session`, `status` | `task` (Browser-Use, needs an OpenRouter key), `computer` (an Orgo cloud desktop) |
| **data-box** | Web data: any public URL to markdown, text, HTML or links, with a cost cap on every call | `scrape` (direct fetch), `job`, `status` | paid scraping sources (Firecrawl, Bright Data, Decodo, Apify) as they are wired in |

You run them yourself — on your own computer (Docker) or a small server — with **your own**
keys. Nothing here calls anyone else's server or bills anyone else's account.

## Quick start (your own computer)

Needs Docker (Docker Desktop or OrbStack on a Mac) and `make`.

```bash
git clone https://github.com/jbellsolutions/box-kit && cd box-kit
make up        # creates both .env files with fresh tokens, builds and starts both servers
make status    # browser-box 200, data-box 200
make env       # prints the four lines that point your agents at them
```

browser-box listens on `127.0.0.1:8080`, data-box on `127.0.0.1:8092` — this machine only.

## Connect your agent

**Claude Code** — put the `make env` lines in your shell profile, then:
```
/plugin marketplace add jbellsolutions/box-kit
/plugin install browser-box@box-kit
/plugin install data-box@box-kit
```
Each plugin brings its MCP server, a skill that teaches when to use which tool, and a few
slash commands (`/browse`, `/act`, `/box-status`, `/scrape`, `/data-box-status`).

**Hermes** — see [hermes/README.md](hermes/README.md): copy two skill folders, paste two
`mcp_servers` entries, add two tokens.

**Codex** —
```bash
codex mcp add browser-box --url http://127.0.0.1:8080/mcp --bearer-token-env-var BROWSER_BOX_TOKEN
codex mcp add data-box    --url http://127.0.0.1:8092/mcp --bearer-token-env-var DATABOX_TOKEN
```

**Anything else** — plain HTTP: `POST http://127.0.0.1:8080/api/v1/<tool>` (or `:8092` for
data-box) with `Authorization: Bearer <token>` and the tool's arguments as JSON. Specs at
`/openapi.json`.

## Costs — who pays for what

- The software is free (MIT). Chromium runs inside browser-box (Steel, open source), so reading
  and browsing pages costs nothing but your machine.
- **Paid only if you add a key**, billed to your account with that provider:
  OpenRouter (browser-box `task`, fractions of a cent per step), Orgo (per hour while a cloud
  desktop runs — stop it when done), Firecrawl / Bright Data / Decodo / Apify (data-box, per
  request). Every data-box call has a `max_cost_usd` cap (default $0.05); a paid step that
  would exceed it never starts.
- Running on a server instead of your computer: the server's monthly price.

## Run it on a server

So agents elsewhere (a cloud VM, a teammate) can reach it: [docs/SELF-HOST.md](docs/SELF-HOST.md)
— server size, HTTPS, and the firewall rule that keeps the browser off your private network.

## What's inside

```
plugins/browser-box, plugins/data-box   Claude Code plugins (MCP config, skills, commands)
hermes/                                 the same skills + a config snippet for Hermes
server/browser-box                      the browser server (Docker compose)
server/data-box                         the data server (Docker, or plain Python)
docs/SELF-HOST.md                       running it on a server
```

Server docs: [browser-box](server/browser-box/README.md) ·
[data-box: how it works](server/data-box/docs/how-it-works.md), [tools](server/data-box/docs/tools.md),
[sources](server/data-box/docs/sources/README.md).

## Safety built in

Both servers refuse loopback, private, link-local and file addresses — on every redirect too —
so an agent can't be tricked into reading things next to the server. browser-box's `act` stops
before steps that look hard to undo (buy, delete, send, post) and asks. Keep your tokens
private: anyone with a token can use that server and the keys on it.

`make test` runs both servers' test suites (no Docker, browser or keys needed).
