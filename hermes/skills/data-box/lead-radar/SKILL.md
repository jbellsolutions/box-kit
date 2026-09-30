---
name: lead-radar
description: Use for buyer intent - people publicly asking to buy something ("anyone know a good VA?") across Reddit, YouTube, TikTok, Instagram, Threads, LinkedIn, Facebook groups and Google - through Lead Radar V2, Justin's separate project. data-box calls its HTTP API as the `intent` lane of a plan (milestone D9) and never contains its code. Covers the API contract data-box expects, the lead-intent.v1 output, the cascade that classifies posts, and why High-tier leads are the only ones enriched.
---

# Lead Radar

Lead Radar V2 finds posts where someone asks for a product or service. It classifies each post as buyer, seller or other, gives buyers a tier (high, medium, low), and returns an evidence quote copied verbatim from the post.

It is **its own project**, in its own repository. data-box **calls** it and never contains it (Justin, 2026-09-30).

## When to use it

- "Find people asking for a fractional CFO", or "who is looking for a virtual assistant this week". That is intent, not a list of companies.
- **Not** for lists of businesses or contacts. Use the Alexandria, DiscoLike, MoltSets or GetLeads skills.

## How (D9, once Lead Radar ships its API)

1. `plan` with kind `intent` (intake sets it when the request is "people asking to buy X"). Lead Radar's `dry_run` estimate is the free preflight.
2. The plan shows the platforms, the days searched and the dollar cap. **Show it and wait for a yes.**
3. `execute`. It reserves `max_cost_usd`, starts `POST /radar/hunt`, polls `GET /radar/runs/{id}`, and settles to the `cost_usd` Lead Radar reports.
4. High-tier leads can be enriched through MoltSets or GetLeads, on the shortlist only.

The contract is in [references/handoff.md](references/handoff.md). Until the API exists, Lead Radar is a CLI (`radar hunt "<query>"`) in its own repo, run by its own operator.

## Never

- Treat a seller or a job ad as a buyer. `role` is decided before `tier`, and a seller is always tier none.
- Search Reddit until commercial access is recorded (charter).
- Post, comment or DM. Nothing in Lead Radar or data-box can.
- Change the Lead Radar repo from a data-box session. Another session owns it.

## References

- [references/charter.md](references/charter.md), [references/handoff.md](references/handoff.md), [references/best-practices.md](references/best-practices.md), [references/lessons.md](references/lessons.md), [references/cost-map.md](references/cost-map.md), [references/recipes.md](references/recipes.md)
- There is no vendor mirror: Lead Radar is Justin's project. Its spec is `LEAD_RADAR_V2_SPEC.md`; §6 is the contract and §11 the CLI and API. Both are summarized in the handoff.
