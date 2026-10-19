# Firecrawl browser: cost map

From Firecrawl's billing and browser pages, mirrored 2026-09-30. A credit is about $0.0038 on Hobby.

| What | Credits | Notes |
|---|---|---|
| Browser Sandbox session, code-driven | 2 a browser minute | one-minute minimum; bills until deleted or a TTL ends |
| Session with a `prompt` (Firecrawl's model picks steps) | 7 a browser minute | data-box does not use prompt mode |
| Interact on a scraped page | same per-minute rates | plus the scrape's 1 credit |
| Scrape with `actions` instead | 1 a page | no minutes: try this first |
| Listing sessions | free | |

Worst case for a plan: `ceil(ttl / 60) x 2` credits a session. A 300 s session is 10 credits, about $0.04.

```json
{
  "tool": "firecrawl-browser",
  "unit": "credit",
  "usd_per_unit": 0.0038,
  "checked": "2026-09-30",
  "source": "vendor-docs/pages/billing.md",
  "prices": [
    {"what": "browser session, code", "cost": 2, "per": "browser minute", "note": "one-minute minimum"},
    {"what": "browser session, prompt", "cost": 7, "per": "browser minute", "note": "not used by data-box"},
    {"what": "scrape with actions", "cost": 1, "per": "page", "note": "no minutes"},
    {"what": "list sessions", "free": true}
  ]
}
```
