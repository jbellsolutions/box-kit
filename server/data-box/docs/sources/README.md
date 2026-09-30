# Sources: what data-box can draw on, and which to reach for

data-box sits in front of these providers so a caller never has to choose between them by hand. The caller asks for a page, a search, a site, records or leads, and data-box picks the cheapest route that answers. This page is for the moments when you do want to choose, and for anyone changing data-box.

**Status as of 2026-09-28.**
- **Wired:** `scrape` rung 0 (the box's own free fetch) on the hosted box; Firecrawl, inside plans, in the D1 code.
- **Everything else:** listed in every survey, with the milestone that wires it.

## The tiers

Every paid request is a plan, and a plan surveys sources in this order (Justin, 2026-09-28):

| Tier | Sources | When |
|---|---|---|
| 1 | [Firecrawl](firecrawl.md) (with Alexandria's providers), [MoltSets](moltsets.md), [DiscoLike](discolike.md) | First choice for data and leads. Firecrawl for anything web-shaped; MoltSets for contacts, on the shortlist; DiscoLike for companies |
| 2 | [Decodo](decodo.md), then [Bright Data](brightdata.md) | When tier 1 cannot serve |
| 3 | [Apify](apify.md) | The backup's backup: expensive, only when no tier 1-2 lane fits, only in an approved plan |

The scrape ladder after the free fetch: Firecrawl → Decodo → Bright Data → Firecrawl's browser → [Hyperbrowser](hyperbrowser.md) → [browser-box](browser-box.md). Fleets of browsers stay browser-box's job.

## Which to use

| You need | Reach for | Why |
|---|---|---|
| One public page | `scrape` | Free. When the page is blocked, the answer carries a plan for the paid rungs |
| A list of businesses or people (leads) | `plan` (kind `pull`) → `execute` after a yes | Surveys every lane, preflights them, dedupes across them |
| To know where some data could come from | `sources` | The survey alone, free |
| Search results or news | `plan` kind `search` | Firecrawl search, 2 credits per 10 results |
| Every page of a site | `plan` kind `crawl` | Firecrawl crawl, 1 credit a page |
| Structured records from pages you already have | `plan` kind `extract` | A schema or a prompt in, JSON out |
| A page that needs clicks, a login or a real browser | [browser-box](browser-box.md) directly | The only real Chromium in the system |

## Rules every source follows

- **Nothing paid without an approved plan.**
  - A paid source runs only inside a plan the user approved, within its budget.
  - A step whose worst case doesn't fit what is left of the budget is not started.
  - Nothing paid runs on an automatic path, including Jev's.
- **Contact data stays with the plan that asked for it.**
  - It never goes into logs, learnings or the repo.
  - It is deleted after the retention period.
- **The public web only.**
  - Target URLs pass the URL guard before any provider is asked to fetch them.
  - Proxied traffic is checked locally before it leaves the box.
- **Keys are environment variables named in [`config.py`](../../src/data_box/config.py).**
  - Values live only in `/etc/data-box.env` on the droplet, or in a developer's gitignored `.env.local`.
  - `status` names every provider and whether its key is set.

## The providers

| Page | Provider | Env vars |
|---|---|---|
| [firecrawl.md](firecrawl.md) | Firecrawl, including Alexandria | `FIRECRAWL_API_KEY` |
| [apify.md](apify.md) | Apify Store | `APIFY_TOKEN` |
| [brightdata.md](brightdata.md) | Bright Data: Unlocker, SERP, datasets, proxy | `BRIGHTDATA_API_KEY`, `BRIGHTDATA_PROXY_USER`, `BRIGHTDATA_PROXY_PASSWORD` |
| [decodo.md](decodo.md) | Decodo: residential proxy, Web Scraping API | `DECODO_PROXY_USER`, `DECODO_PROXY_PASSWORD`, `DECODO_SCRAPER_API_TOKEN` |
| [moltsets.md](moltsets.md) | MoltSets: people and company contact data | `MOLTSETS_API_KEY` |
| [discolike.md](discolike.md) | DiscoLike: company discovery | `DISCOLIKE_API_KEY` |
| [hyperbrowser.md](hyperbrowser.md) | Hyperbrowser: a stealth browser | `HYPERBROWSER_API_KEY` |
| [browser-box.md](browser-box.md) | browser-box: a real browser | `DATABOX_BROWSERBOX_URL`, `DATABOX_BROWSERBOX_TOKEN` |

Jev (TypeSafe) and OpenRouter are engines, not sources. [how-it-works.md](../how-it-works.md) covers them.
