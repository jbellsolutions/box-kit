---
name: getleads
description: Use for B2B contact lists and enrichment from GetLeads (getleads.io) - 402M contacts searched by company, title, seniority, place and email status, then work emails and phones for a shortlist. A flat $497-a-month plan with fair-use caps (500,000 rows a day, 6,000,000 a month by default) instead of per-row credits. REST at app.getleads.io/api/v1 with a glb_live_ key, or its MCP server by sign-in. Through data-box's plan -> approve -> execute once wired (milestone D6).
---

# GetLeads

A B2B contact database built for agents: 402M contacts, 150+ fields each. It is reached two ways:
- **REST:** `https://app.getleads.io/api/v1/...`, with `Authorization: Bearer glb_live_<keyId>_<secret>` or `X-API-Key`.
- **MCP:** `https://app.getleads.io/api/mcp`, where most clients sign in with no key.

Justin's account: none yet. The plan is $497 a month for unlimited use, or $248.50 on the partner plan.

## When to use it

| Need | Endpoint | Cost on the unlimited plan |
|---|---|---|
| How many contacts match | `POST /contacts/search/count` | free |
| Contacts by company, title, seniority, country, email status | `POST /contacts/search` | rows count against the fair-use windows |
| All rows of a big match | `POST /contacts/search/export` (CSV on S3, 50,000 a request) | same |
| Decision makers or colleagues at a company | `POST /contacts/lookup/decision-makers`, `.../colleagues` | same |
| A person from a work email, a LinkedIn URL, or name + company | `POST /enrich/from-email`, `/from-linkedin`, `/from-person` | same, one item where `success` is true |
| Allowed filter values | `GET /contacts/filter-values` | free |
| Remaining daily and monthly rows | `GET /usage/fair-use` | free |

LinkedIn scraping products (profile monitoring, website visitors, company followers) bill a separate prepaid wallet in dollars. data-box does not plan them.

## How

1. Free first: `GET /usage/fair-use` for the windows, `GET /contacts/filter-values` for exact values, `POST /contacts/search/count` to size the query. Narrow the query until it matches fewer than 50,000.
2. In data-box (D6): `plan` with `sources: ["getleads"]`. The plan shows rows against the binding window and an amortized dollar cost, and waits for approval.
3. `execute` pages `contacts/search` with `offset` until `has_more` is false or the target is met, then enriches only the deduped shortlist.

Until D6, or when the caller is signed in to the MCP and data-box has no key, GetLeads is **caller-side**: the calling agent uses its own MCP tools, and the survey says so.

## Never

- Page past 50,000 matches: the order is unstable above that, so pages repeat and skip. Count first.
- Resell or redistribute raw contact data as a dataset. That is against GetLeads' fair-use policy.
- Put the key anywhere but the box. data-box keeps it as `GETLEADS_API_KEY` in `/etc/data-box.env`; it never goes in a URL, log, commit, skill or chat.
- Treat "unlimited" as uncapped: 402 means a window is spent.

## References

- [references/charter.md](references/charter.md), [references/handoff.md](references/handoff.md), [references/best-practices.md](references/best-practices.md), [references/lessons.md](references/lessons.md), [references/cost-map.md](references/cost-map.md), [references/recipes.md](references/recipes.md)
- [references/vendor-docs/pages/api-docs.md](references/vendor-docs/pages/api-docs.md): the full REST and MCP reference, mirrored 2026-09-30. It is also in `fair-usage.md`, `thinking-mode.md` (the MCP guide) and `ask.txt` (the FAQ).
