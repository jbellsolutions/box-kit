---
name: firecrawl
description: Use for anything web-shaped through Firecrawl - search the web or news, scrape a page that a plain fetch cannot read, map or crawl a site, batch-scrape a URL list, or extract JSON from pages. Always through data-box's plan -> approve -> execute, which prices the call against the live credit balance before anything is spent. For lead and business lists use firecrawl-alexandria; for pages that need clicks or logins use firecrawl-browser.
---

# Firecrawl

Firecrawl is tier 1 in data-box and the default for anything web-shaped. It turns URLs into clean markdown or JSON, searches the web, and maps and crawls sites. It is billed in **credits**. Justin's account is on the Hobby plan: 5,000 credits a month, 5 concurrent browsers. On 2026-09-30 the balance was **-330**, so paid calls wait for credits.

## When to use it

| Need | data-box call | Price (credits) |
|---|---|---|
| Read one page the free fetch could not | `scrape` (returns a plan when rung 0 is blocked) -> `execute` | 1 a page, +4 with a JSON schema |
| Web or news results for a query | `plan` kind `search` -> `execute` | 2 per 10 results |
| Every page of a site | `plan` kind `crawl` -> `execute` | 1 a page |
| Structured fields out of known pages | `plan` kind `extract` -> `execute` | 5 a page |
| A list of businesses or people | use **firecrawl-alexandria** | per tool |
| Clicking, scrolling, logging in | use **firecrawl-browser** | 2 a browser minute |

Map (1 credit a call), batch scrape and the agent endpoint come to data-box in D3; until then they are not offered as plan kinds.

## How

1. Call data-box `plan` with the request (or `scrape` a URL: the free rung runs at once, and a blocked page comes back with a plan). The plan lists every source considered and the worst-case credits and dollars.
2. **Show the whole plan to the user and wait for a yes.** Never approve on their behalf.
3. `execute` with the plan id and `approve: true`. It spends at most the approved amount, never lets the balance go below the floor, and resumes without paying twice.
4. Read rows with `job action=results` or `action=export`.

Direct calls to `api.firecrawl.dev` are for free reads only: `GET /v2/team/credit-usage`, `GET /v2/team/queue-status`, and Alexandria discovery. Anything that costs credits goes through a plan. See [references/charter.md](references/charter.md).

## Never

- Spend credits outside an approved plan, or in a loop that has no page, query and cost cap. That is how 2026-09-28 happened ([references/lessons.md](references/lessons.md)).
- Add `"web"` to a search's `sources` just to discover Alexandria tools: `["alexandria"]` is free, `["web", "alexandria"]` pays for web results.
- Assume a failed page was free: Firecrawl charges 1 credit whenever the target answered, 403 and 404 included.
- Retry a timed-out paid call with a new request id: send the same `x-request-id` so a replay is not charged twice (D3).
- Put the API key in a URL, a log line, a skill file or a chat message.

## References

- [references/charter.md](references/charter.md): what Firecrawl is for here, its tier, what it may and may not do.
- [references/handoff.md](references/handoff.md): keys, state on the box, live evidence, open issues, next step.
- [references/best-practices.md](references/best-practices.md): how to get the most rows per credit.
- [references/lessons.md](references/lessons.md): dated incidents and the rule each produced.
- [references/cost-map.md](references/cost-map.md): every price, with a machine-readable table.
- [references/recipes.md](references/recipes.md): worked plans for common requests.
- [references/vendor-docs/](references/vendor-docs/PROVENANCE.md): Firecrawl's own docs, mirrored 2026-09-30 (`pages/llms-full.txt` is all of them).
