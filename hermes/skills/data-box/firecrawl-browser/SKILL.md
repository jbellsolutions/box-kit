---
name: firecrawl-browser
description: Use when a page needs a real browser to act on it - clicks, scrolling, pagination behind a button, a form, or a logged-in profile - and Firecrawl's plain scrape is not enough. Firecrawl's Browser Sandbox (POST /v2/interact) gives a remote Chromium you drive with code-written Playwright or agent-browser steps, billed per browser minute. In data-box it is scrape rung 4 (milestone D3). Not for bot-protected pages (no proxy or stealth) and not for volume: that is Hyperbrowser or browser-box.
---

# Firecrawl browser (Browser Sandbox and Interact)

A remote Chromium session on Firecrawl's side. You open it, run code in it, and close it. It has a CDP URL (connect your own Playwright) and a live-view URL a person can watch. It is billed **2 credits a browser minute** (7 when a `prompt` lets Firecrawl's model choose the steps), one-minute minimum.

## When to use it

- A page shows its data only after a click, a scroll, a "load more" or a form: rung 4 of data-box's scrape ladder.
- A site needs a logged-in session that a saved profile holds.

Not for: pages behind bot protection (the sandbox has **no proxy or stealth**: use Hyperbrowser, rung 5), many pages at once (browser-box), or a plain read (Firecrawl scrape, rung 1).

## How

In data-box this becomes a lane of a scrape plan in D3. The plan's code writes the steps; nothing free-form runs:
1. `POST /v2/interact` with `ttl` (30-3600 s, default 600) and `activityTtl` (10-3600 s, default 300); optionally `profile: {name, saveChanges}`. Returns `id`, `cdpUrl`, `liveViewUrl`.
2. `POST /v2/interact/{id}/execute` with `{code, language: "node" | "python" | "bash"}` (bash runs `agent-browser` commands such as `open`, `snapshot`, `click @e5`, `scrape`).
3. `DELETE /v2/interact/{id}` in a `finally`, always, so a failure never leaves minutes billing.

To act on a page you already scraped: `POST /v2/scrape/{scrapeId}/interact` with code, and `DELETE` the same path to stop. `/v2/browser` is an older name for the standalone session and still answers.

Until D3 wires it, show the user a plan (session length, worst-case minutes, credits) and wait for a yes before opening a session by hand.

## Never

- Leave a session open: delete it in a `finally`, and close any session left over from a crashed run before starting new ones.
- Let a `prompt` pick the steps inside a paid session (7 credits a minute, and steps nobody reviewed). data-box writes the code.
- Open two sessions that save to the same profile: the second gets a 409.
- Send it at bot-protected pages and pay minutes for a challenge screen.

## References

- [references/charter.md](references/charter.md): its place in the ladder and its limits.
- [references/handoff.md](references/handoff.md): what is wired, what D3 adds, evidence.
- [references/best-practices.md](references/best-practices.md): session hygiene and cheap minutes.
- [references/lessons.md](references/lessons.md): dated lessons.
- [references/cost-map.md](references/cost-map.md): prices, with a machine-readable table.
- [references/recipes.md](references/recipes.md): worked sessions.
- [references/vendor-docs/](references/vendor-docs/PROVENANCE.md): Firecrawl's browser and interact docs, mirrored 2026-09-30.
