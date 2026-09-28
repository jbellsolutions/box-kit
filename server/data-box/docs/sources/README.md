# Sources: what data-box can draw on, and which to reach for

data-box sits in front of these providers so a caller never has to choose between them by hand. The caller asks for a page, a search, a site, records or leads, and data-box picks the cheapest route that answers. This page is for the moments when you do want to choose, and for anyone changing data-box.

**Status as of 2026-09-23.**
- **Wired into a live tool:** only rung 0 of `scrape`, the box's own free fetch.
- **Everything else:** the provider's key is present or missing, and nothing more yet.

The milestone that wires each provider is on its page.

## Which to use

| You need | Reach for | Why |
|---|---|---|
| One public page | `scrape` (rung 0 first) | Free. It climbs to a paid rung only if the page is blocked or needs JavaScript |
| A page behind bot protection | `scrape` rungs 1–3: Firecrawl, then Bright Data Unlocker, then Decodo | Each rung is tried only if the one before failed, within the cap |
| A page that needs a logged-in or real browser | [browser-box](browser-box.md) (`scrape` rung 4, or browser-box directly) | The only real Chromium in the system |
| Search results, news, or research/government/developer data | `websearch` → [Firecrawl](firecrawl.md), including Alexandria | One call covers the web plus Alexandria's curated providers |
| Every page of a site | `crawl` → Firecrawl | Map first, then crawl within limits |
| Structured records from pages you already have | `extract` → Firecrawl | A schema or a prompt in, JSON out |
| Records from a specific platform (LinkedIn, Google Maps, Amazon, Instagram…) | `sources` then `run` → [Apify](apify.md) actor or [Bright Data](brightdata.md) dataset | Purpose-built scrapers beat scraping the pages yourself |
| Company lists by similarity or firmographics | `run` → [DiscoLike](discolike.md) | Paid per result; explicit calls only |
| A person's business contact details | `run` → [MoltSets](moltsets.md) | Paid; explicit calls only, capped, never stored outside the job |
| A different exit country, or a sticky IP | `scrape` rung 0b → [Decodo](decodo.md) or Bright Data proxy | Residential egress, metered by the byte |

## Rules every source follows

- **The cap is the caller's.**
  - A paid source runs only within `max_cost_usd`.
  - A step whose worst case doesn't fit the cap is not started.
- **Explicit only.**
  - Marketplace purchases, MoltSets, DiscoLike and lead searches never run on an automatic path, including Jev's.
  - A caller has to ask for them by name.
- **Contact data stays in the job that asked for it.**
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
| [browser-box.md](browser-box.md) | browser-box: a real browser | `DATABOX_BROWSERBOX_URL`, `DATABOX_BROWSERBOX_TOKEN` |

Jev (TypeSafe) and OpenRouter are engines, not sources. [how-it-works.md](../how-it-works.md) covers them.
