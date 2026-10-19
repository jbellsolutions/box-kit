# MoltSets: charter

**Tier 1 data tool for people and contacts.** It is one of the approved paid sources (Justin, 2026-09-23, reaffirmed 2026-09-30), and it is used only inside an approved data-box plan.

## What it is for

- Searching people and companies by exact filters.
- Revealing work emails, verified best emails and mobile phones, **only for the deduped shortlist**.

## Rules

1. **Contacts on the shortlist only**, never at discovery scale.
2. **Metered in records against the fair-use windows.**
   - The windows are rolling: 5 hours, and a week. Every key on the account shares them.
   - A plan draws no more than the smallest window's headroom minus a floor.
3. **Misses are free, and not repeated.** A `not_found` is recorded in `misses.jsonl`, so a resumed run never asks again.
4. **Not planned without Justin's say-so:** personal email, MAID and SHA256 tools. They are consumer identity and ad-targeting data.
5. **The key is `MOLTSETS_API_KEY` on the box.** It never goes in a URL, log, commit, skill or chat.
6. **Contact data stays on the box** for the retention period. Logs carry counts only.

## Not for

- Company discovery by similarity: use DiscoLike.
- Local businesses without LinkedIn footprints: use Alexandria directories.
