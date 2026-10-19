# Firecrawl: cost map

Prices from Firecrawl's billing page, mirrored 2026-09-30 ([vendor-docs/pages/billing.md](vendor-docs/pages/billing.md)). A credit is about **$0.0038** on Hobby ($19 for 5,000); set `DATABOX_FIRECRAWL_USD_PER_CREDIT` to the real plan's rate.

| What | Credits | Notes |
|---|---|---|
| Scrape | 1 a page | charged whenever Firecrawl returned a document, **including 403 and 404 pages**; 0 when no document came back |
| JSON format (extract) | +4 a page | so an extract is 5 a page |
| PDF parsing | +1 a PDF page | |
| Enhanced proxy, or `auto` escalating to it | +0 | the escalated retry is not charged separately |
| Zero data retention | +1 a page | |
| Question, highlights, audio, video formats | +4 a page each | |
| PII redaction | +4 a page | |
| Search | 2 per 10 results, rounded up | scraping the results adds each page's scrape cost |
| Map | 1 a call | |
| Crawl | 1 a page | billed as each page finishes; an explicit `limit` is checked up front; no `limit` reserves nothing but defaults to 10,000 pages |
| Batch scrape | 1 a page | billed as each page finishes |
| Browser sandbox (`/v2/interact`) | 2 a browser minute, 7 with a `prompt` | one-minute minimum |
| Balance, queue status, Alexandria discovery | free | |

Plans: Hobby 5,000 credits a month and 5 concurrent browsers; Standard 100,000 and 25; Growth 500,000 and 50; Scale 1,000,000 and 100. Jobs beyond the concurrency wait in a queue, and the queue time counts against the request's `timeout`.

```json
{
  "tool": "firecrawl",
  "unit": "credit",
  "usd_per_unit": 0.0038,
  "checked": "2026-09-30",
  "source": "vendor-docs/pages/billing.md",
  "prices": [
    {"what": "scrape a page", "cost": 1, "per": "page", "note": "charged for 403/404 pages too; 0 when no document"},
    {"what": "json format", "cost": 4, "per": "page", "note": "on top of the scrape"},
    {"what": "pdf parsing", "cost": 1, "per": "pdf page"},
    {"what": "enhanced proxy", "cost": 0, "per": "page"},
    {"what": "zero data retention", "cost": 1, "per": "page"},
    {"what": "search", "cost": 2, "per": "10 results", "note": "rounded up; scraping results costs extra"},
    {"what": "map", "cost": 1, "per": "call"},
    {"what": "crawl", "cost": 1, "per": "page"},
    {"what": "batch scrape", "cost": 1, "per": "page"},
    {"what": "browser sandbox", "cost": 2, "per": "browser minute", "note": "7 with a prompt; one-minute minimum"},
    {"what": "balance and queue status", "free": true},
    {"what": "alexandria discovery", "free": true}
  ]
}
```
