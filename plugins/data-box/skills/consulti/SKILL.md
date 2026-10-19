---
name: consulti
description: Use for verified-email lead lists from Consulti (consulti.ai) - B2B people by title, industry and technology; local businesses from Google Maps with owner or role emails; YouTube and podcast creators; Instagram accounts - and for email verification. 1 lead credit per row returned, the cost reported on every response. Through data-box's plan -> approve -> execute once wired (milestone D6); until then only its free calls (credits, filter values) run without a plan.
---

# Consulti

A lead database where every row carries a verified email, reached over REST at `https://www.consulti.ai/api/v1` with `Authorization: Bearer <key>` (keys start `capi_`, made in Settings -> Integrations). Lead endpoints need the **Pro plan or higher**; verification works on any plan. It is tier 1 in data-box, wired in **D6**.

## When to use it

| Need | Endpoint | Cost |
|---|---|---|
| B2B people by title, industry, technology, place | `POST /leads/search` | 1 lead credit a row returned (page size up to 100) |
| Local businesses (Google Maps) with an email | `POST /local-leads/search` | 1 a row |
| YouTube channels or podcasts with an email | `POST /creator-leads/search` | 1 a row |
| Instagram accounts | `POST /instagram/search` | 1 a row |
| One person from name + company, or from an email | `POST /leads/find-by-name`, `POST /leads/enrich` | 1 on a match |
| Work email (+ free US mobile) from a LinkedIn URL | `POST /enrich/linkedin` | 1 when an email comes back |
| Is this email deliverable | `POST /verify` (5 for `/verify/catchall`) | 1 verification credit |
| Balances; canonical filter values | `GET /credits`, `GET /meta/{filter}` | free |

## How

1. Free first: `GET /credits` for the balance and `GET /meta/{filter}` for the exact filter values (industries, states, technologies). A filter value that is not canonical returns nothing and wastes a call.
2. In data-box (D6): `plan` with `sources: ["consulti"]`. The plan prices pages x size x 1 credit against `lead_credits`, previews one small page, and waits for approval.
3. `execute` reserves each page's worst case and settles to the `credits_used` Consulti reports.

Until D6, a paid Consulti call is a plan the user approves by hand: the page size, the page count and the worst-case credits, then stop.

## Never

- **Retry a search blindly.** A retried request is a new billable search; the `Idempotency-Key` header is accepted but does nothing today. On a timeout, read `GET /credits` before deciding.
- Treat a 402, 404 or 5xx as free: Consulti calls them billing-ambiguous (a reservation may have been taken, and its refund can fail silently). Check the balance.
- Check a key's prefix to decide whether it is valid: keys have been `capi_` and, in an older skill, `ctai_`.
- Put the key anywhere but the box's environment (`CONSULTI_API_KEY`).

## References

- [references/charter.md](references/charter.md), [references/handoff.md](references/handoff.md), [references/best-practices.md](references/best-practices.md), [references/lessons.md](references/lessons.md), [references/cost-map.md](references/cost-map.md), [references/recipes.md](references/recipes.md)
- [references/vendor-docs/pages/llms.txt](references/vendor-docs/pages/llms.txt): Consulti's full API reference for agents, mirrored 2026-09-30 (every endpoint, field, error, and the canonical filter values).
