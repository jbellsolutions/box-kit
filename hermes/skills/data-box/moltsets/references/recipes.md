# MoltSets: recipes

All paid steps run inside an approved data-box plan (milestone D5).

## "Work emails for the 400 owners on this deduped list" (enrichment on the shortlist)

1. **Free:** `get_account` for the enrichment window's headroom.
2. **Plan:** 400 lookups with `linkedin_to_business_email`, in 4 batches of 100.
   - The plan shows the draw against the window, and the expected hits. Plan for misses on micro-businesses.
   - Profiles without a LinkedIn URL go to `search_business_email_by_name` instead.
3. **Execute:** batches of 100 with a pause between them. Misses go to `misses.jsonl`; hits merge into the records by LinkedIn URL.

## "VP Sales at US software companies, 200-1,000 employees"

1. **Probe:** `search_people` with `limit: 1`, exact filters (seniority "VP", department "Sales", country "United States", the company size band), to read `total`.
2. **Plan:** pages of 25 up to the target, against the 5-hour search window. Exclusions go in the query.
3. **Execute:** page with `offset`, write each page before advancing, and stop at the target or the window floor.

## "Owners of multi-location dental groups in Texas"

- Discover the companies first, with DiscoLike or Alexandria.
- Dedupe to domains.
- Then `search_people` per domain for owner-level titles.

This mirrors the Hermes `moltsets-multi-location-owner-discovery` playbook, bounded by a plan.
