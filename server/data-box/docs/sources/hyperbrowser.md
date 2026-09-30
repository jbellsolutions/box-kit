# Hyperbrowser

**Status (2026-09-28).** Scrape rung 5: the stealth browser, after Firecrawl's own browser and before browser-box. Justin has a paid plan. `HYPERBROWSER_API_KEY` is on the old Super Browser box (`/opt/super-browser/.env`) and moves to `/etc/data-box.env` in D3, when the rung is wired. Until then every scrape plan lists the rung as "not wired yet".

## What it gives data-box

Pages that need a real browser **and** stealth: bot protection that Firecrawl's scrape and the unblockers could not pass, where Firecrawl's Browser Sandbox (rung 4, no proxy or stealth) would be blocked too.

| Use | Endpoint | Notes |
|---|---|---|
| Scrape one page | `POST /api/scrape` `{url, sessionOptions{useStealth, useProxy, proxyCountry, solveCaptchas}, scrapeOptions{formats, onlyMainContent, waitFor}}`, then poll `GET /api/scrape/{id}` until `completed` or `failed` | Polled with a real timeout (the old adapter's fixed 20 s reported slow jobs as unfinished) |
| A session for clicking | `POST /api/session` → `wsEndpoint` (CDP) and `liveUrl`; `PUT /api/session/{id}/stop` | Always stopped in `finally` |

- **Auth:** `x-api-key: $HYPERBROWSER_API_KEY`
- **Price (vendor, 2026-09-28):** 1 credit = $0.001. A scrape is 1 credit, 10 with a proxy. Browser time is $0.10 an hour. Proxies and CAPTCHA solving need a paid plan; which tier Justin's is gets checked in D3.
- **No balance API.** Spend is metered from each response's `creditsUsed` and reserved at the worst case (10 credits a page) before the call.

## Primary docs

- https://docs.hyperbrowser.ai
