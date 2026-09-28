# Firecrawl, including Alexandria

**Status (2026-09-23).** `FIRECRAWL_API_KEY` is present on the droplet. Nothing calls Firecrawl yet; it is wired in M3.

## What it gives data-box

| data-box tool | Firecrawl endpoint | Use |
|---|---|---|
| `scrape`, rung 1 | `POST /v2/scrape` | Pages the free fetch could not read (bot protection, JavaScript) |
| `websearch` | `POST /v2/search` | Web and news search, optionally scraping the top results |
| `websearch` with `index=alexandria:*` | `POST /v2/search` with `sources: ["alexandria"]` | Alexandria's curated data providers and indexes |
| `crawl` | `POST /v2/map`, `POST /v2/crawl` | Whole sites, as a job |
| `extract` | `POST /v2/extract` | A schema or a prompt → JSON records |
| catalog (`sources`, `run`) | Alexandria's tool list | Each Alexandria capability becomes a catalog entry |

**Alexandria** launched on 2026-09-22. It puts curated data providers and three indexes behind Firecrawl's search:
- **Providers:** about 82, among them FRED, SEC, SAM.gov and GitHub.
- **Capabilities:** 471, across those providers.
- **Indexes:** Research, Developer and Government.

These counts are Firecrawl's; data-box counts them itself when it builds its catalog in M4. Alexandria, `/agent` and the indexes run only on Firecrawl's cloud API. The self-hosted edition doesn't have them, and it would need about 8 GB of RAM, which the droplet doesn't have.

## How data-box calls it

- **Base URL:** `https://api.firecrawl.dev`
- **Auth:** `Authorization: Bearer $FIRECRAWL_API_KEY`
- **Cost:** credits per page or per result.

At the start of M3, data-box confirms each request shape and its credit cost against Firecrawl's current docs, and records the cost per call in the ledger. Nothing here states a price until it has been measured.

## Primary docs

- https://docs.firecrawl.dev
- Firecrawl's Alexandria launch notes (2026-09-22)
