# Firecrawl: best practices

## Spend

- **Price the worst case.** Every planned page bought, every failed-but-reached page charged. data-box's plans already do this; a hand estimate should too.
- **Free fetch first.** data-box's rung 0 reads most public pages for nothing. Firecrawl is for the ones it cannot.
- **Cap every loop** by pages, queries and a unique-record target, and stop paging when a page is mostly records already seen.
- **Read the balance before, and every 15 calls during, a run** (`GET /v2/team/credit-usage`, free). Stop before it goes below the floor.
- **Use `maxAge`** for pages that change slowly: a cached scrape is faster, and repeated plans reuse it.

## Throughput

- Hobby runs **5 browsers at once**; more jobs queue, and the queue time counts against `timeout`. data-box runs 4 so Hermes keeps one.
- Check `GET /v2/team/queue-status` (free) before a large batch.
- A 429 means too many requests or a full queue: back off, do not hammer.

## Formats

- Ask only for the formats you need: `markdown` for reading, `links` for discovery, `json` only when the fields must be structured (+4 credits a page).
- `onlyMainContent: true` (the default here) drops navigation and footers.
- For extraction, prefer a JSON schema over a prompt: the result is checkable.

## Crawls

- Always set `limit`, and `includePaths` / `excludePaths` when only part of a site matters.
- Map first (1 credit) to see how big the site is, then set the crawl's `limit` from it (D3).
- A crawl that is stopped must be cancelled (`DELETE /v2/crawl/{id}`), or it keeps billing pages.

## Search

- `sources: ["web"]` for pages, `["news"]` for news. Alexandria discovery is `["alexandria"]` alone, which is free.
- Scraping search results multiplies the cost by the page count: search first, then scrape only the results worth reading.
