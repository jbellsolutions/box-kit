# data-box tools

Every tool has the same name and the same arguments over every door:

| Door | How |
|---|---|
| MCP | `https://<box>/mcp` (streamable HTTP), `Authorization: Bearer $DATABOX_TOKEN` |
| HTTP/JSON | `POST https://<box>/api/v1/<tool>` with the arguments as the JSON body; `GET /api/v1/status`; spec at `GET /openapi.json` |
| CLI | `data-box <tool> [first-argument] [--name value ...]` (set `DATABOX_URL` and `DATABOX_TOKEN`) |

Rules that hold for every tool:

- **A listed tool works.** A verb whose provider is not configured is not listed at all; `status`
  names every provider, whether it is configured, and what it would add.
- **A refusal is an answer.** It comes back as `{"error": "...", "tool": "..."}`, HTTP 422 on the JSON
  door. Read the reason; do not retry a refusal unchanged.
- **Anything slow is a job.** Pass `wait_seconds` (0-60, default 30). Finished in time: the result
  comes back inline with its `job_id`. Not finished: you get `{job_id, status}`; follow it with `job`.
- **Retries are safe with `request_id`.** The same `request_id` with the same arguments returns the
  first call's job instead of running (and paying) again; with different arguments it is refused.
- **Every paid call is capped.** `max_cost_usd` is the most a call may spend. Each paid step reserves
  its worst case before it runs and settles to the real charge after; a step that does not fit is
  not started. `cost_usd` on every answer is what was actually spent.
- **Only the public web.** Loopback, private, link-local and file targets are refused, on every
  redirect hop too.

The OpenAPI document ([openapi.json](openapi.json)) is generated from the same tool cards the MCP
server lists (`make openapi`); a test fails if it drifts.

## `status`

What this box can do right now. Free, touches no provider.

Returns `components` (the free fetch, the ledger, and every provider with `configured`, what it is
`for` and a one-line `detail`), `tools_working_now`, `tools_unavailable` (each with a reason),
`spend_last_24h_usd` and the last 10 calls.

```bash
data-box status
curl -s -H "Authorization: Bearer $DATABOX_TOKEN" https://<box>/api/v1/status
```

## `scrape`

One public URL to `markdown` (default), `text`, `html` or `links`.

It climbs a ladder and stops at the first rung that returns the real page, never spending past
`max_cost_usd` (default $0.05):

| Rung | What | Cost | On this box |
|---|---|---|---|
| 0 `fetch` | Direct HTTP GET, pinned to the checked address, redirects checked hop by hop, 2 MB cap | free | yes |
| 0b | The same GET through a residential proxy (Decodo, then Bright Data on port 44445) | per GB | not yet |
| 1 | Firecrawl scrape | credits | not yet |
| 2 | Bright Data Web Unlocker | per request | not yet |
| 3 | Decodo Web Scraping API with JavaScript rendering | per request | not yet |
| 4 | browser-box `read`: a real browser | free (own box) | not yet |

Whether a page is "the real page" is judged by code: a block status (401, 403, 407, 429, 451, 503),
a challenge page (Cloudflare, DataDome, PerimeterX, Imperva, a captcha), or an almost-empty
JavaScript app shell. A 404 is an answer, not a block. When the ladder stops short, `blocked` says
what stopped it and `rungs_tried` lists each rung, its cost and why it was left.

| Argument | |
|---|---|
| `url` | Public http(s) URL (required) |
| `format` | `markdown` \| `text` \| `html` \| `links` |
| `max_cost_usd` | Cap for paid rungs (0-25) |
| `wait_seconds`, `request_id` | See the rules above |

```bash
data-box scrape https://example.com
data-box scrape https://news.ycombinator.com --format links
```

## `job`

Follow anything that runs as a job. Free.

| Action | Does |
|---|---|
| `get` | The job and its result; `wait_seconds` waits for it to finish |
| `list` | Recent jobs; filter with `status` or `tool` |
| `cancel` | Stop it. Paid steps already taken stay charged |
| `results` | Page through its items (`offset`, `limit`) |
| `export` | All items as `csv`, `json` or `jsonl` (the CLI writes the content straight to stdout) |

```bash
data-box job list
data-box job get job_ab12cd34 --wait-seconds 30
data-box job export job_ab12cd34 --format csv > rows.csv
```

## Coming next

These verbs are designed and appear here only once they pass a live end-to-end check (see the
plan in [CHARTER.md](../CHARTER.md)): `websearch`, `crawl` and `extract` (Firecrawl, including
Alexandria), `sources` and `run` (a searchable catalog of Apify actors, Bright Data datasets and
scrapers, Alexandria capabilities, Decodo templates, MoltSets and DiscoLike), `ask` (a plain-language
request, routed by Jev) and `leads` (buyer-intent lead search).
