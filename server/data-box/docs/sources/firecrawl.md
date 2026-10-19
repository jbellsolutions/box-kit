# Firecrawl, including Alexandria

**Status (2026-09-28).** Tier 1, and the default for anything web-shaped. `FIRECRAWL_API_KEY` is set on the droplet. D1 wires it: every `plan` surveys Alexandria through it, and `execute` runs its lanes. The account's balance was **-330 credits** on 2026-09-28 (down from about 4,950 that morning, most likely the Hermes firecrawl profile), so a live paid pull needs credits added first. `status` shows the balance.

## What it gives data-box

| data-box step | Firecrawl endpoint | Cost |
|---|---|---|
| Survey (step 2): Alexandria's category index | `GET /exchange/discover` → `cohorts: [{cohort, about, providers}]` | free |
| Survey: every tool in a category, with contracts | `find-tools` with `{categories: [id], level: "tools", expand: ["options", "response"], limit: 100}`, following `next` | free |
| Survey: one tool's contract, or a semantic search | `POST /v2/scrape` with `{"alexandria": {"provider": "firecrawl", "capability": "find-tools", "options": {...}}}` | free |
| Survey: tools ranked for a plain-language need | `POST /v2/search` with `sources: ["alexandria"]` | free |
| Survey: a provider's data terms | the same call with capability `terms/show` | free |
| Balance, before a plan and every 15 calls of a run | `GET /v2/team/credit-usage` | free |
| Pull lanes (step 4) | `POST /v2/scrape` with `{"alexandria": {provider, capability, options}}` | the tool's listed price |
| `plan` kind `search` | `POST /v2/search` | 2 credits per 10 results |
| `plan` kind `scrape`, scrape rung 1 | `POST /v2/scrape` with `proxy: "auto"` | 1 credit (+4 with a JSON schema) |
| `plan` kind `crawl` | `POST /v2/crawl`, then polling | 1 credit a page |
| `plan` kind `extract` | `POST /v2/scrape` with a `json` format | 5 credits a page |
| Scrape rung 4 (D3) | Browser Sandbox, `POST /v2/interact` | 2 credits a minute; no proxy or stealth |

Prices are Firecrawl's published ones (docs.firecrawl.dev, 2026-09-28); Alexandria tools carry their own `creditsCost`, read live in every survey. The Hobby plan is 5,000 credits a month for $19, about $0.0038 a credit, and runs 5 jobs at once. `DATABOX_FIRECRAWL_USD_PER_CREDIT` converts credits to dollars for plans and the ledger; set it to the real plan's rate.

**Alexandria** launched on 2026-09-22: about 82 providers and 471 capabilities (Firecrawl's figures), plus the Research, Developer and Government indexes. It runs only on Firecrawl's cloud API.

## Lane cheatsheet for US business leads

Verified live by Justin's `firecrawl-alexandria` skill (2026-09) and kept as ranking priors in [`recipes.py`](../../src/data_box/recipes.py). A plan always re-reads the live contract and preflights each lane.

| Lane | Credits | Page | Use |
|---|---|---|---|
| `bbb-business-profiles-ratings-complaint/businesses/search` | 1 a call | 15, paginated to page 100; partition by state or city | Cheapest listing call; skews to accredited firms, so never the only lane. No website in search results |
| `bing-com/businesses/search` | 5 a call | up to 30 (`count`), pages 1-5; silently truncates near page 5 | Name, address, phone, website. At most 3 pages and 2 queries a metro |
| `maps-google-com/businesses/search` | 5 a call | up to 20, no pagination | One call per "category in city" cell; overlaps Bing on chains, so dedupe |
| `houzz-com/professionals/search` | 5 a page | | Home-trades professionals |
| `apollo/people/search` | 0 | | Free identity discovery once its terms are accepted |
| `bbb-.../businesses/profile` | per call | one business | Website, email (obfuscated), LinkedIn; shortlist only |
| `apollo/people/match`, `fullenrich/contacts/work-email` | 30 / 20 a record | | Email reveal: deduped shortlist only |

Expected ranking, from the contracts as read on 2026-09-28 (to be confirmed by the first live survey): with `fields: ["phone", "website"]` Bing leads (it returns both) and BBB and Maps are top-ups; asked for phone only, BBB's 15 records a credit lead.

These are priors, not the list. Every plan reads every tool in the Alexandria categories the request is about and ranks all that can serve. A tool nobody verified can serve only if it is a general directory for the entity or its description mentions the request's topic; the 2026-09-28 live survey for roofers otherwise marked GolfNow, SeatGeek and Trader Joe's as lanes, and ranked TickPick above Bing on records per credit. Such a lane is used when its preflight returns the entity, and dropped (with why) when it does not.

**Anti-patterns** the plan guards against: BBB as the only source for a broad vertical; per-record people search for discovery; deep Maps or Bing pagination without page and query caps; Bing and Maps sweeps without dedupe keys.

## What burned ~8,000 credits on 2026-09-28, and what stops it here

A Hermes realtor pull quoted about 1,300 credits and spent about 8,000, driving the balance to -330:

| What happened | data-box |
|---|---|
| Bing paged up to 8 pages deep x 4 queries a metro: 2,018 calls instead of ~200 | At most 3 pages and 2 queries a place on Bing, 1 call and 2 queries on Maps; only the base layer pages |
| 30,002 Bing rows collapsed to 7,508 unique (~75% repeats) | A cell stops when a page brings under 30% new records |
| The target moved to 30,000 raw rows mid-run, without a new budget | A plan cannot grow: the approved amount binds every run of it; a bigger pull is a new plan |
| The balance went negative | No call starts that could take the balance below the floor (0) |
| Raw rows were the target | The deduped count is the target; the plan's oversample covers dedupe, it is not a quota |

## Terms

Some providers need their data terms accepted before their tools run (`THIRD_PARTY_DATA_TERMS_REQUIRED`). data-box never accepts terms itself: the survey lists such a lane as unable to run and says why. A person accepts them in Firecrawl (`firecrawl alexandria terms accept <provider> ...`), after reading them; some restrict storage or model training.

## How data-box calls it

- **Base URL:** `https://api.firecrawl.dev` (`FIRECRAWL_API_BASE` to override)
- **Auth:** `Authorization: Bearer $FIRECRAWL_API_KEY`
- **Client:** [`providers/firecrawl.py`](../../src/data_box/providers/firecrawl.py). A port of the skill's `alexandria.py` without its four defects: it never swaps in a different tool when the one asked for is missing, it refuses a call missing a required input before sending it, it never pays on its own (plans and the ledger decide), and an empty or error result is a failure, not a success.
- **Failures:** 402 is "out of credits" and stops a run; a 429 is retried once; a timeout or 5xx is an unknown outcome and is charged in full.

## Primary docs

- https://docs.firecrawl.dev
- The skill: [vault/skills/firecrawl-alexandria](../../vault/skills/firecrawl-alexandria/SKILL.md)
