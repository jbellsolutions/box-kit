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

**Live.** The ledger and the runner. The first paid steps (Firecrawl, inside plans) arrive with D1.

## The four steps: plan, then execute

Every paid request goes through the same four steps, whichever door it came through. They come from Justin's Hermes skill `firecrawl-alexandria` ([vendored here](../vault/skills/firecrawl-alexandria/SKILL.md)); `planning.py` and `execution.py` are its port.

| Step | Tool | What happens | Spends |
|---|---|---|---|
| 1. Take in the request | `plan` | Code reads the request and hints into an intake: kind (pull, search, scrape, crawl, extract), entity, count, fields, queries, places, named sources, cap | nothing |
| 2. Survey every source | `plan` (or `sources` alone) | Tier 1 first. Alexandria is read live and free: its category index (`GET /exchange/discover`), then every tool in the categories the request is about (its vertical, and the ones holding the entity), paged in full through `find-tools` with contracts, plus the skill's verified lanes, a semantic `find-tools` search and `/v2/search`'s ranking. Each tool comes with price, page size, pagination, inputs and field fit, and those that could serve get their data terms read (`terms/show`). Category lists are reused for 24 hours. MoltSets, DiscoLike, Decodo, Bright Data and Apify are listed with whether they can run here. A tool can serve only if it is a general directory for the entity (Bing, Google Maps and both BBBs are `businesses/search`) or its own description mentions what the request is about ("roof…" for roofing contractors); on the live catalog this keeps golf courses, event venues and grocery stores out of a roofers' pull. A lane the plan cannot fill, a terms-gated lane, an enrichment lane and an off-topic tool are listed with the reason they are not used | nothing (free calls) |
| 3. Narrow to a game plan | `plan` | Lanes ranked by records per credit x coverage x field fit, verified and new alike (a named source only). Preflight walks the ranking: one real call per lane, kept if it returns the entity, dropped (with why) if not, until `max_lanes` are kept. Each lane is split into query x place cells and pages within the skill's caps (Bing 3 pages and 2 queries a place, Maps 1 call and 2 queries a place, BBB up to 100 pages). Priced at the worst case in credits and dollars against the live balance, with a 20% margin as the budget | preflight: at most 25 credits and never past `max_cost_usd` |
| 4. Execute after approval | `execute` with `approve: true` | Covered below | at most the approved amount |

**A plan's life:** `preparing` → `awaiting_approval` → (`execute`) `approved` → `executing` → `done`, or back to `approved` when a run stops early (budget, balance, errors or a cancel), so `execute` can resume it. A plan not approved within 24 hours becomes `expired`; a plan that failed while being prepared is `cancelled` with what its preflight spent.

**Execution.** One job per `execute`:
- Its cap is the approved amount minus what the plan already spent (preflight and earlier runs), so resumes share one budget.
- Lanes run in the plan's order, the base layer first. Cells run in parallel, 4 at a time (Firecrawl's Hobby plan runs 5 jobs at once; one is left for other users of the key).
- A cell's pages run in order and stop at the first short or empty page. No new call starts once the deduped list reaches the requested count.
- Each call reserves its listed price in the ledger first and settles to the credits Firecrawl reports. A refusal (4xx) costs nothing; an unknown outcome (timeout, 5xx, a cancel mid-call) is charged in full.
- A cell also stops when a page brings under 30% new records: deep pages of Bing and Maps re-fetch the same chains.
- The Firecrawl balance is read before the first call and every 15 calls, and tracked call by call in between (calls in flight included). No call starts that could take it below `DATABOX_FIRECRAWL_BALANCE_FLOOR` (0).
- Records that are not the entity (for a business, a name plus a phone, address or website) are counted as off-target and left out of the list.
- A lane that fails 3 times is skipped for the rest of the run.

**Files.** Each plan has a folder, `<state>/plans/<plan_id>/` (mode 0700):
- `raw.jsonl`: every record, tagged with its lane, place, query and page;
- `done.txt`: every page already bought, and how many records it had, so a resume never buys it again;
- `records.jsonl`: the deduped list, merged across lanes on normalised name+phone and name+address (then name+website); each row names every lane that found it;
- `contracts.json`: the lanes' contracts as read when the plan was made.

`job results` and `job export` read `records.jsonl`. Folders are deleted after `DATABOX_RETENTION_DAYS` (30), because they can hold contact data.

**What approval means.** data-box cannot see a person. It enforces that no paid call runs without an approved `plan_id`, that the approved amount binds the spend, and that plans expire. The plugin's skill tells every calling agent to show the whole plan to the user and wait for a yes.

## The scrape ladder

`scrape` runs the free rung at once. When it cannot read the page, the answer says why and carries a plan for the paid rungs; nothing paid runs until that plan is executed.

| Rung | What | Cost | State |
|---|---|---|---|
| 0 | Pinned, redirect-checked GET from the box | free | **live** |
| 1 | Firecrawl `/v2/scrape`: JavaScript rendering, proxy `auto` | 1 credit, 5 with a schema | D1, in a plan |
| 2 | Decodo: residential re-fetch, then the Web Scraping API | per request | planned (D3) |
| 3 | Bright Data Web Unlocker | per request | planned (D3) |
| 4 | Firecrawl Browser Sandbox (`/v2/interact`): clicks, scrolls and logins; no proxy or stealth | 2 credits a minute | planned (D3) |
| 5 | Hyperbrowser: stealth browser with proxies and CAPTCHA solving | 1 credit a page, 10 with a proxy ($0.001 a credit) | planned (D3) |
| 6 | browser-box `POST /api/v1/read`: the Steel browser, last resort. A busy browser lane counts as a failure | own hardware | planned (D3) |

**Is this the real page?** `fetch.judge` decides this in code first:
- **Blocked:** status 401, 403, 407, 429, 451 or 503.
- **Challenge:** a known challenge marker on a short page.
- **Needs JavaScript:** a page with almost no text that is an app shell.
- **HTTP error:** any other 4xx or 5xx.
- **The page itself:** 404, 410, and short real pages are answers, not failures.

When code can't tell, Jev is asked (D6 onward).

**Planned (D3).** A per-domain memory, which remembers the rung that worked so later plans skip rungs known to fail.

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

**Through a proxy (D3).** DNS resolves at the proxy, so pinning no longer binds the connection. The guard therefore:
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

**The only measurement so far** comes from the archived dispatcher: Jev routed 2 of 12 requests by itself, with a median of 314 ms. D6 measures how often it can decide alone on real traffic. Until a capability is certified on held-out cases, Jev only runs in shadow for it.

**Planned.** D6: Jev ranks lanes among the candidates code built and checks preflight samples, in shadow first, then live one capability at a time.

## The survey instead of a catalog

The old plan built a searchable catalog of every source (M4). The survey replaces it: step 2 reads Alexandria's contracts live through Firecrawl's free `find-tools`, so prices, inputs and pagination are never stale, and the lanes Justin's skill verified live are kept as ranking priors in `recipes.py`. Tier 2 and 3 sources join the survey as they are wired (Bright Data datasets and Decodo templates in D4, Apify Store search in D5).

## Lead intent (D7)

`leads` brings the lead-intent work back from `jbellsolutions/lead-radar` as `src/data_box/leads/`. Its known problem is yield: it found zero qualified buyers on real data. That has two causes.
- **Sourcing.** LinkedIn post search surfaces sellers.
- **Gating.** Real requests were held back by all-must-pass gates.

The fix:
- a funnel report per venue;
- searching where buyers actually post;
- buyer-language queries;
- a code prefilter before Jev;
- gates recalibrated on at least 300 labeled real candidates.

It is rebuilt on plan and execute: the lead search is a plan the user approves, and MoltSets and DiscoLike enrichment runs only on qualified leads, inside the plan's budget.
