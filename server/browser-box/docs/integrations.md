# Connecting to browser-box

All routes hit the same gateway, the same tools, the same token — see
[architecture.md](architecture.md) and [tools.md](tools.md).

## Claude Code (MCP)

```bash
claude mcp add --transport http browser-box https://your-box/mcp \
  --header "Authorization: Bearer $BROWSER_BOX_TOKEN"
```

Or a project `.mcp.json` (the repo ships one, defaulting to a local box). Both expansion forms
below are verified live against Claude Code — `${VAR:-default}` resolves when the variable is
unset, and `BROWSER_BOX_TOKEN` expands in the header despite being a credential-shaped name
(`claude mcp list` prints the raw text, not the expanded value — a literal `${...}` there is not
a fault):

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

## The Claude Code plugin (in this repo)

The repo is its own plugin marketplace:

```
/plugin marketplace add jbellsolutions/browser-box
/plugin install browser-box@browser-box
```

That attaches the MCP server, a `browser-box` skill (`skills/browser-box/SKILL.md`) that teaches
fetch-before-read and what the refusals mean, and two commands: `/browse <url or question>` and
`/box-status` (`commands/`). Set `BROWSER_BOX_URL` and `BROWSER_BOX_TOKEN` first.
`claude plugin validate .` passes on this repo; `make plugin` re-runs it.

## The `bb` CLI (`cli/`)

```bash
pipx install ./cli                       # from a clone
bb login --url https://your-box --token <BB_TOKEN>
```

While the repo is private, the `git+https://…` install form needs a credential — clone first,
or make the repo public. Once public:

```bash
pipx install 'git+https://github.com/jbellsolutions/browser-box#subdirectory=cli'
```

```bash
bb status
bb fetch -t https://example.com
bb read -t -s -o shot.jpg https://news.ycombinator.com
bb session create
bb act "open news.ycombinator.com then click new"
bb task "report the top HN story's comment count"
bb task --cancel
bb tools
```

`bb ask` and `bb chat` run a model **in the CLI, on your machine** (needs
`OPENROUTER_API_KEY`) — the box still has no brain in it. Everything else (`fetch`, `read`,
`session`, `status`, `act`, `task`) needs no key.

## curl over HTTP/JSON

No MCP client needed — see [tools.md](tools.md#two-doors-one-set-of-tools) for the full request
shape and status codes:

```bash
curl -fsS "$BROWSER_BOX_URL/api/v1/fetch" \
  -H "Authorization: Bearer $BROWSER_BOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

## Hermes (Justin's agent)

Add an entry to `~/.hermes/config.yaml`:

```yaml
browser-box:
  url: https://<box>/mcp
  headers:
    Authorization: "Bearer ${env:BROWSER_BOX_TOKEN}"
  connect_timeout: 60
  timeout: 960
  enabled: true
```

Put the token in `~/.hermes/.env`:

```
BROWSER_BOX_TOKEN=<token>
```

Verify, then reload:

```bash
hermes mcp test browser-box
```

then `/reload-mcp`, or restart Hermes, so a running instance picks it up.

## `browser-box-pp-cli` (Go CLI)

A Go command-line tool generated from `docs/openapi.json` with Printing Press, in
`pp-cli/` in this repo with its own README (Apache-2.0, as generated; the rest of the repo is MIT). It keeps a local call ledger, a page cache, full-text
search, batched reads that retry busy refusals, session aliases, and status drift detection — state a plain curl
loop doesn't give you.

Install it from a clone with `make cli` (that is, `cd pp-cli && go install ./cmd/browser-box-pp-cli ./cmd/browser-box-pp-mcp`; `make cli-test` runs its tests), then set `BROWSER_BOX_TOKEN` and `BROWSER_BOX_BASE_URL`. `browser-box-pp-cli doctor` checks both. The ledger sees only calls made through this CLI or its own MCP server (`browser-box-pp-mcp`); agents talking to the box's `/mcp` directly are not recorded.
