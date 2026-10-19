# Bright Data

**Status (2026-09-23).**
- **API key:** verified with the account's zones and the dataset list, and set on the droplet.
- **Wiring:** tier 2. Nothing calls Bright Data yet. The Web Unlocker becomes scrape rung 3 in D3; SERP, datasets and scrapers join the survey as tier 2 data lanes in D4, used when tier 1 cannot serve.
- **Proxy:** `BRIGHTDATA_PROXY_USER` / `BRIGHTDATA_PROXY_PASSWORD` have not been supplied.

## What it gives data-box

| data-box tool | Bright Data product | Account zone (seen 2026-09-23) |
|---|---|---|
| `scrape`, rung 2 | Web Unlocker | `mcp_unlocker` (unblocker) |
| `websearch` fallback | SERP API | `serp_api1`, `serp_api2` (serp) |
| catalog, `run` | Datasets (marketplace), Web Scraper API, Discover | — |
| `scrape`, rung 0b | Residential proxy | — |

The account also has a `mcp_browser` (Browser API) zone. data-box doesn't use it; browser-box is the browser.

**Datasets:** 1,762, measured through `GET /datasets/list` on 2026-09-23. That is well above Bright Data's "700+" marketing figure. In D4 the survey lists the datasets that fit a request, replacing the nine dataset IDs Super Browser hard-coded.

## How data-box calls it

- **Base URL:** `https://api.brightdata.com`
- **Auth:** `Authorization: Bearer $BRIGHTDATA_API_KEY`
- **Web Unlocker and SERP:** `POST /request` with `{zone, url, format}`. The exact body is confirmed against Bright Data's docs at the start of D3.
- **Datasets:**
  - `GET /datasets/list` lists them.
  - `POST /datasets/v3/trigger` starts a collection, and `GET /datasets/v3/snapshot/{id}` reads it.
  - Marketplace datasets are previewed by default; a purchase needs `confirm_purchase: true` and a cap.
- **Proxy:** `brd.superproxy.io:44445`, with the zone, country and session in the username. The old ports 22225 and 33335 are refused by a test, because their certificates expire on 2026-09-25.

Bright Data also runs an MCP server (`mcp.brightdata.com`). data-box uses the REST API instead, so every call goes through data-box's cap and ledger.

## Notes

- `GET /customer/balance` returns 403 with this key: the key has no billing scope. Spend is reconciled from data-box's own ledger and Bright Data's usage stats instead.

## Primary docs

- https://docs.brightdata.com
