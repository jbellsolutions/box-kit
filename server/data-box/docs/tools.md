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
- **Nothing paid runs without a plan the user approved.** Every paid request follows four steps,
  whatever the door: take in the request, survey every source, narrow it to a game plan (`plan`),
  and run it only after the user says yes (`execute` with `approve: true`). The only spend before
  approval is a plan's preflight: one real call per lane, at most 25 credits, reported in the plan.
- **Every paid call is capped.** Each paid step reserves its worst case before it runs and settles
  to the real charge after; a step that does not fit the approved amount is not started. `cost_usd`
  on every answer is what was actually spent.
- **Only the public web.** Loopback, private, link-local and file targets are refused, on every
  redirect hop too.

The OpenAPI document ([openapi.json](openapi.json)) is generated from the same tool cards the MCP
server lists (`make openapi`); a test fails if it drifts.

## `status`

What this box can do right now. Free; its only provider call is Firecrawl's free balance check.

Returns `components` (the free fetch, the ledger, and every provider with `configured`, what it is
`for` and a one-line `detail`; Firecrawl also shows `balance_credits`), `tools_working_now`,
`tools_unavailable` (each with a reason), `spend_last_24h_usd`, `plans_awaiting_approval`,
`plans_executing` and the last 10 calls.

```bash
data-box status
curl -s -H "Authorization: Bearer $DATABOX_TOKEN" https://<box>/api/v1/status
```

## `scrape`

One public URL to `markdown` (default), `text`, `html` or `links`.

The free rung runs at once. Paid rungs never run without approval: when the free fetch cannot
read the page, the answer says what stopped it (`blocked`) and carries a `plan` for the paid
ladder, with its worst-case cost. Show the plan to the user; on a yes, `execute` it.

| Rung | What | Cost | On this box |
|---|---|---|---|
| 0 `fetch` | Direct HTTP GET, pinned to the checked address, redirects checked hop by hop, 2 MB cap | free | yes, runs without a plan |
| 1 | Firecrawl `/v2/scrape`: JavaScript rendering, proxy `auto` | 1 credit (5 with a schema) | yes, in a plan |
| 2 | Decodo: residential re-fetch, then the Web Scraping API | per request | D3 |
| 3 | Bright Data Web Unlocker | per request | D3 |
| 4 | Firecrawl Browser Sandbox: clicks and logins, no proxy | 2 credits a minute | D3 |
| 5 | Hyperbrowser: stealth browser, proxies, CAPTCHA solving | 1-10 credits a page | D3 |
| 6 | browser-box `read`: the Steel browser, last resort | free (own box) | D3 |

Whether a page is "the real page" is judged by code: a block status (401, 403, 407, 429, 451, 503),
a challenge page (Cloudflare, DataDome, PerimeterX, Imperva, a captcha), or an almost-empty
JavaScript app shell. A 404 is an answer, not a block.

| Argument | |
|---|---|
| `url` | Public http(s) URL (required) |
| `format` | `markdown` \| `text` \| `html` \| `links` |
| `max_cost_usd` | Cap for the call (the free rung costs nothing) |
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

## `sources`

Step 2 on its own: every source that could serve a need, tier by tier, with whether each can run
on this box and why not. Free. Without a `url` it surveys for a pull.

| Tier | Sources | In a survey |
|---|---|---|
| 1 | Firecrawl: its Alexandria providers, read live through `find-tools` (price, page size, pagination, inputs, terms, field fit); web search, scrape, crawl, extract | runnable now |
| 1 | MoltSets (contacts, on the deduped shortlist), DiscoLike (companies) | listed; wired in D2 |
| 2 | Decodo, Bright Data | listed; wired in D3-D4 |
| 3 | Apify, the expensive backup's backup | listed; wired in D5, used only when no tier 1-2 lane fits |

```bash
data-box sources "roofing contractors in Austin TX" --fields '["phone","website"]'
```

## `plan`

Steps 1-3. Takes a request, surveys every source (the same survey as `sources`) and narrows it to a
game plan the user approves:

- **The survey reads the whole catalog that matters.** Every tool in the Alexandria categories the
  request is about (the vertical, plus the categories that hold the entity), each with its contract,
  on top of the skill's verified lanes and Firecrawl's own search. A tool that cannot serve (wrong
  entity, terms to accept, an input a plan cannot fill, an enrichment tool) is listed with why.
- **Lanes** ranked by records per credit x coverage x field fit, verified and new alike, each with its
  query x place cells, pages per cell, calls, credits and dollars. The first is the base layer; the
  rest are top-ups. The skill's caps hold: Bing at most 3 pages and 2 queries a place, Google Maps one
  call a cell and 2 queries a place, BBB up to 100 pages.
- **The budget**: the estimate plus 20% (or `max_cost_usd`), against the live Firecrawl balance.
- **Preflight** decides which lanes stay: one real call per lane (its first cell), at most 25
  credits and never past `max_cost_usd`. A lane whose preflight returns none of the entity is
  dropped and the next-ranked lane tried; each lane says `confirmed` or why it was not run. The
  records are kept, so execution does not buy those pages again.
- **The cost is a worst case**: every planned page. Execution usually stops well before it.
- **Warnings**: a named source that cannot run, an empty balance, an estimate over the cap.

A source the user named (`sources: ["bbb"]`, `"disco"`, `"bing"`) is honoured: only those lanes are
used, and the plan says so when one cannot run. A plan expires after 24 hours.

| Argument | |
|---|---|
| `request` | What is wanted, in plain words |
| `kind` | `pull` \| `search` \| `scrape` \| `crawl` \| `extract` (inferred when left out) |
| `entity`, `count`, `fields`, `queries`, `geo` | pull: what, how many, which fields, what to search, where |
| `sources` | Sources the user named |
| `url`, `urls`, `schema`, `prompt`, `format`, `limit` | scrape, crawl, extract and search |
| `max_cost_usd` | Most the whole plan may spend, preflight included |
| `preflight`, `max_lanes`, `oversample` | pull tuning (defaults: true, 3, 1.5) |
| `action` | `new` (default), `get`, `list`, `cancel` (with `plan_id`) |

```bash
data-box plan "roofing contractors" --geo '["Austin, TX"]' --count 50 --fields '["phone","website"]'
data-box plan --action get --plan-id plan_ab12cd34
```

## `execute`

Step 4: runs a plan, only with `approve: true`, which means the user said yes to it. It spends at
most the approved amount (the plan's budget, or a lower `max_cost_usd`), preflight included.

A pull runs its lanes in order and its cells in parallel (4 at a time), and dedupes across lanes
on name+phone and name+address. It stops spending as soon as spending stops paying:

- a cell stops at its first short page, or when a page brings under 30% new records (deep pages
  re-fetch the same chains);
- no call starts once the deduped list reaches the requested count;
- no call starts that could take the Firecrawl balance below zero (the balance is read every 15
  calls and tracked call by call in between, calls in flight included);
- nothing is spent past the approved amount, and a plan cannot grow mid-run: a bigger pull is a new
  plan, approved again.

The answer counts unique records, records found by two or more lanes, and off-target rows dropped. Running `execute`
again on the same plan resumes it; a page already bought is never bought again. The answer carries
counts, what each lane did and a sample; `job results` and `job export` read the rows. Records are
deleted after 30 days.

| Argument | |
|---|---|
| `plan_id`, `approve` | Required; `approve` must be `true` |
| `max_cost_usd` | Approve less than the plan's budget, never more |
| `drop_lanes` | Lanes the user struck out |
| `wait_seconds`, `request_id` | See the rules above |

```bash
data-box execute plan_ab12cd34 --approve true
data-box job export job_ab12cd34 --format csv > roofers.csv
```

## Coming next

Wired milestone by milestone, each only after a live end-to-end check (see
[roadmap.md](roadmap.md)): MoltSets and DiscoLike lanes (D2), the rest of the scrape ladder (D3),
Bright Data and Decodo data lanes (D4), Apify as tier 3 (D5), Jev in steps 2-3 (D6), and `leads`
(buyer-intent lead search) on plan and execute.
