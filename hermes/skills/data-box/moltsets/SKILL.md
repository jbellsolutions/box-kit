---
name: moltsets
description: Use for people and company contact data from MoltSets - search people or companies with exact-match filters, then reveal verified business emails, personal emails and carrier-verified mobile phones for a deduped shortlist (by LinkedIn URL, name or email). Flat monthly plans metered by rolling 5-hour and weekly fair-use windows; misses are free. REST at api.moltsets.com/api/v1/tools/<tool>, Bearer key plus a User-Agent. Through data-box's plan -> approve -> execute once wired (milestone D5).
---

# MoltSets

A B2B contact-data API. It covers:
- **People and company search:** `search_people`, `search_companies`.
- **Enrichment:**
  - from a LinkedIn profile: `linkedin_to_business_email`, `linkedin_to_best_email`, `linkedin_to_mobile_phone`;
  - reverse lookups: `reverse_email_lookup`, `reverse_linkedin_lookup`, `email_to_linkedin`;
  - `ip_to_company`.
- **Account reads:** `get_account`, `get_billing`, `get_usage`.

Every tool is `POST https://api.moltsets.com/api/v1/tools/<tool>`, with `Authorization: Bearer <key>` and **a non-empty `User-Agent`**; without it, 403. The MCP is at `mcp.moltsets.com/mcp`.

## When to use it

- **Contacts for a shortlist.** You have company domains or LinkedIn URLs and need emails or mobiles. Charges apply only when data comes back.
- **People by title, seniority, department and place.** Use `search_people`, 25 a page.
- **Not** for discovering companies at scale. DiscoLike or Alexandria do that more cheaply, and MoltSets reveals the contacts afterwards.

## How

1. **Free:** `get_account` for the plan, token balances and the fair-use windows with `resets_at` (UTC). The call still counts as a request.
2. **Probe:** `search_people` with `limit: 1`, to read `total`. `total` stops at 10,000, so a 10,000 means "at least".
3. **In data-box (D5):** `plan` with MoltSets as a discovery or enrichment lane.
   - The plan shows the records it will draw against the smallest window, minus a floor.
   - Enrichment runs only on the deduped shortlist.
   - Misses (`status: "not_found"`) are free and go to `misses.jsonl`.
4. **Show the plan, get a yes, `execute`.**

## Never

- Send `department` and `functional_area` together. They are the same data, and MoltSets refuses the pair.
- Walk pages past what the plan approved. Every record returned draws from the 5-hour pool: `limit: 25` over 5 pages is 125 search records.
- Plan personal email, MAID (`email_to_maid`) or SHA256 tools without Justin's say-so. They are also refused (`plan_restricted`) on the $397 and $997 plans.
- Assume a helper's side effects are harmless. The Hermes `moltsets_leads.py` starts an `lw ingest` into lead-warehouse after a CSV search; data-box does not.

## References

- [references/charter.md](references/charter.md), [references/handoff.md](references/handoff.md), [references/best-practices.md](references/best-practices.md), [references/lessons.md](references/lessons.md), [references/cost-map.md](references/cost-map.md), [references/recipes.md](references/recipes.md)
- [references/vendor-docs/](references/vendor-docs/PROVENANCE.md): MoltSets' `llms.txt`, the developer `llms.txt` and `llms-full.txt` (every endpoint, rate limits, errors), and the pricing page, mirrored 2026-09-30.
