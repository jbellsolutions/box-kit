# How data-box works

This page covers what happens to a request from the moment it arrives. Every part is marked **live**, meaning it runs on the hosted box today, or **planned**, with the milestone that brings it. Tool arguments are in [tools.md](tools.md); providers are in [sources/](sources/README.md).

## One request, three doors

Every door ends in the same function (`server.make_dispatch`):

| Door | Endpoint | Notes |
|---|---|---|
| MCP | `POST /mcp` | Streamable HTTP, stateless, JSON responses |
| HTTP/JSON | `POST /api/v1/<tool>`, `GET /api/v1/status` | The body is the arguments; the spec is at `/openapi.json` |
| CLI | `data-box <tool>` | A thin client of the HTTP door |

The shared function works in this order:
1. **Check the bearer token.** It is compared in constant time. A missing or wrong token gets a 401.
2. **Check the tool is offered here.** A tool the box does not offer gets a 404.
3. **Validate the arguments** against the tool card's JSON Schema. Invalid arguments get a 400, with the schema's reason.
4. **Run the handler.**
5. **Return the answer.** A refusal comes back as `{"error": ...}`, which the HTTP door sends as a 422.

`/health` needs no token. It reports only liveness and the deployed revision, never what is configured.

**Live.** All three doors.

## Jobs and money

Anything that can take more than a moment runs as a **job** (`jobs.Runner`). The caller waits up to `wait_seconds` (at most 60). A finished job's result comes back inline. An unfinished one comes back as a `job_id`, which the caller polls or cancels with `job`.

The ledger (`ledger.Ledger`, SQLite) stores money as integers in millionths of a dollar, so rounding never drifts.

| Rule | How |
|---|---|
| Cap | Each call carries `max_cost_usd`, the job's budget |
| Reserve before spending | Before a paid step runs, it reserves its worst-case cost. If that would exceed the budget, the step is refused and never starts |
| Settle after | Once the provider reports the real cost, the reservation settles to it |
| Crash safety | On start, jobs left running are marked `interrupted`, and their open reservations are charged in full |
| Idempotency | A repeated `request_id` with the same arguments returns the first job. With different arguments, it is refused |

**Live.** The ledger and the runner. No paid step exists yet; the first ones arrive in M3.

## The scrape ladder

`scrape` climbs one rung at a time. It moves up only when the rung below fails, and never past `max_cost_usd` (default $0.05).

| Rung | What | Cost | State |
|---|---|---|---|
| 0 | Pinned, redirect-checked GET from the box | free | **live** |
| 0b | The same GET through a residential proxy (Decodo, then Bright Data). Used when a country is asked for, or when rung 0 was blocked by IP | per GB | planned (M3) |
| 1 | Firecrawl `/v2/scrape` | credits | planned (M3) |
| 2 | Bright Data Web Unlocker | per request | planned (M3) |
| 3 | Decodo Web Scraping API, with JavaScript rendering | per request | planned (M3) |
| 4 | browser-box `POST /api/v1/read`: a real Chromium. A busy browser lane counts as a failure | own hardware | planned (M3) |

**Is this the real page?** `fetch.judge` decides this in code first:
- **Blocked:** status 401, 403, 407, 429, 451 or 503.
- **Challenge:** a known challenge marker on a short page.
- **Needs JavaScript:** a page with almost no text that is an app shell.
- **HTTP error:** any other 4xx or 5xx.
- **The page itself:** 404, 410, and short real pages are answers, not failures.

When code can't tell, Jev is asked (M5 onward).

**Planned (M3).**
- A per-domain memory, which remembers the rung that worked so later calls skip rungs known to fail.
- A `better_source` hint when the catalog has a recipe for the domain (a LinkedIn profile, an Amazon product). The hint is advice; `scrape` never spends on a catalog source by itself.

## The URL guard

`security.py` is a copy of browser-box's guard, and both repos test it against the same byte-identical `scope_vectors.json`, so the two boxes refuse the same URLs.

**What gets refused, before any connection:**
- loopback, private, link-local, shared (100.64.0.0/10), reserved and unspecified addresses;
- cloud metadata endpoints such as 169.254.169.254, which are link-local;
- bare hostnames with no dot, which resolve through internal DNS;
- non-HTTP schemes;
- disguised loopback forms such as `0x7f000001`, `2130706433` and `127.1`.

**How a fetch is made safe:**
- Every address a name resolves to is checked, not just the first.
- The connection is pinned to a checked address, IPv4 first, falling back to the next checked address.
- Redirects are followed by hand: at most 5 hops, each checked before it is followed.
- Only ports 80 and 443 are allowed.
- Bodies stop at 2 MB.

**Through a proxy (M3).** DNS resolves at the proxy, so pinning no longer binds the connection. The guard therefore:
- resolves the name locally and refuses any non-public address before sending CONNECT;
- re-checks every redirect hop;
- keeps the byte cap.

## Jev, and the LLM behind it

Jev is TypeSafe's `jev-latest` (`POST https://api.typesafe.ai/v1/systemone`).
- **What it answers:** it picks one of up to 255 options (`choice`), answers yes/no (`noul`), or gives a rubric score (`score`).
- **Vendor figures:** about 150–500 ms per call, at $0.042 per million input tokens.
- **What it never does:** it never generates text.

So data-box orders the work this way:
1. **Code first.** A bare URL goes to `scrape`, a job ID goes to `job`, and so on.
2. **One Jev call next.** It picks the tool and answers "are all inputs present?". It picks each argument from candidates that code extracted: URLs, quoted phrases, enums, and the top catalog sources.
3. **Run directly or hand to the LLM.** The request runs directly only when every answer is at least 0.95 **and** the capability is certified. Otherwise the LLM (OpenRouter, GLM 5.3 Flash by default) handles it, with Jev's shortlist as hints.
4. **Jev as checker.** Jev also checks results: is the page blocked, does this result answer the request, does a claim match its source, are two records the same entity, and the lead-intent gates.

**The only measurement so far** comes from the archived dispatcher: Jev routed 2 of 12 requests by itself, with a median of 314 ms. M6 measures how often it can route alone on real traffic. Until a capability is certified on held-out cases, Jev only runs in shadow for it.

**Planned.** M5 (shadow) and M6 (live, one capability at a time).

## The source catalog (M4)

One searchable catalog covers every source data-box can run.

**Rows (SQLite):**
- `sources`: one row per source, with id, kind, inputs, price and whether it can run;
- `sources_fts`: a full-text index over those rows;
- `source_outcomes`: past runs' cost and record counts, which feed ranking.

**Ranking:** full-text score first, then filters, then boosts in this order: a curated recipe, then past success, then popularity.

**Quality bar:** the right source in the top 10 for at least 90% of 50 labeled queries.

**Notes:**
- **Generated:** one Obsidian-openable note per source, under `/var/lib/data-box/vault/catalog/<provider>/`. `make vault-pull` copies them into the Obsidian vault.
- **Hand-written:** provider guides and recipes live in the repo's `vault/`.

## Lead intent (M7)

`leads` brings the lead-intent work back from `jbellsolutions/lead-radar` as `src/data_box/leads/`. Its known problem is yield: it found zero qualified buyers on real data. That has two causes.
- **Sourcing.** LinkedIn post search surfaces sellers.
- **Gating.** Real requests were held back by all-must-pass gates.

The fix:
- a funnel report per venue;
- searching where buyers actually post;
- buyer-language queries;
- a code prefilter before Jev;
- gates recalibrated on at least 300 labeled real candidates.

MoltSets and DiscoLike enrichment runs only after a lead qualifies, with a cap per lead.
