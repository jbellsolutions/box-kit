# Consulti: lessons

## 2026-09-30: the docs were free all along

- **What happened:** the plan for making data-box the data tool repository assumed Consulti's docs page blocked plain fetches and would need a paid fetch through data-box's own scrape plan. The page does block (429), but `www.consulti.ai/llms.txt` carries the complete API reference and is free.
- **Rule:** before paying to read a vendor's docs, look for `llms.txt`, `llms-full.txt` and `openapi.json` at the site root.

## 2026-09-30: a retry is a new charge

- **What happened:** Consulti's reference says an `Idempotency-Key` header is accepted but has no effect, and a retried search is billed again; 402, 404 and 5xx may already have reserved credits.
- **Rule:** data-box never re-sends a paid Consulti call on an unknown outcome; it reads `GET /credits` and records the call as charged until the balance says otherwise.

## 2026-09-28: the credit burn that shaped every lane

- **What happened:** a Hermes lead pull that paged Firecrawl lanes without caps spent about 8,000 credits for a list quoted at about 1,300.
- **Rule:** every Consulti lane has a page cap, a row target and a stop when pages repeat, like every other lane.
