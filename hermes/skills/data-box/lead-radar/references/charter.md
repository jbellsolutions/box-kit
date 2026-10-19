# Lead Radar: charter

**Tier 1 intent lane, called over HTTP, never contained** (Justin, 2026-09-30). The code, the classifier, the golden sets and the operator's runs all live in the lead-radar repo.

## What data-box may do

- Call Lead Radar's HTTP API as the `intent` lane of an approved plan:
  - a `dry_run` estimate before approval;
  - a hunt capped at `max_cost_usd` after it.
- Store the returned leads in the job folder, like any other records.
- Enrich **High-tier buyers only**, through tier-1 contact tools, on the shortlist.

## What data-box may not do

- Import Lead Radar code, or copy its classifier.
- Search Reddit until commercial access is recorded.
- Post, comment or DM anywhere.
- Open issues or change files in the lead-radar repo without Justin's say-so.

## Data

- A lead carries the post's text and its author's public handle.
- Evidence quotes are verbatim, and at most 30 words.
- Leads stay on the box for the retention period. Logs carry counts and tiers only.
