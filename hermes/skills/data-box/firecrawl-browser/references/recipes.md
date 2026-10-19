# Firecrawl browser: recipes

Each is a sketch of what a D3 plan runs; the plan shows the TTL and worst-case credits before any session opens.

## A list behind a "Load more" button

1. `POST /v2/interact` `{"ttl": 180, "activityTtl": 60}` (worst case 6 credits).
2. Execute, bash: `agent-browser open https://example.com/directory`, then `agent-browser snapshot` to find the button's ref.
3. Execute, bash, repeated at most N times: `agent-browser click @e12`, then `agent-browser scrape` for the new rows. Stop when a click adds no rows.
4. `DELETE /v2/interact/{id}` in a `finally`.

## A page that renders only after scrolling

Try rung 1 first: `POST /v2/scrape` with `actions: [{"type": "scroll", "direction": "down"}, {"type": "wait", "milliseconds": 1500}]` costs 1 credit and no minutes. Only when the content needs state between steps does it become a session.

## A logged-in read with a saved profile

1. The user has saved the login in a profile (`profile: {"name": "crm", "saveChanges": true}` once, by hand, watching `liveViewUrl`).
2. The plan opens it read-only: `profile: {"name": "crm", "saveChanges": false}`, `ttl` 120.
3. Execute node: `await page.goto(url); return await page.content()`.
4. Delete the session.

## Continue from a scrape

`POST /v2/scrape` returns `scrapeId`; `POST /v2/scrape/{scrapeId}/interact` with `{"code": "...", "language": "node"}` acts on that same page; `DELETE /v2/scrape/{scrapeId}/interact` stops it. The session inherits the scrape's profile.
