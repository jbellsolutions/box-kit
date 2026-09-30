# DiscoLike: charter

**Tier 1 data tool for companies, approved by Justin.** Paid use happens only inside an approved data-box plan (Justin, 2026-09-28 and 2026-09-30).

## What it is for

- **Company discovery:** lookalikes of seed domains, or matches to an ICP.
- **Firmographics:** size, industry, tech stack, growth and subsidiaries.
- **Contacts and work emails:** for the **shortlist** of companies, after discovery and dedupe.

## Rules

1. **Count first.** Counts are free; a plan never pays to learn a market's size.
2. **Checkpoint before scale.** Validation or a DiscoGen run on at most 100 domains comes before any bulk pull.
   - 80% fit or better: proceed.
   - 50-79%: tighten the filters.
   - Under 50%: rework the query.
3. **Contacts on the shortlist only.**
4. **The key is `DISCOLIKE_API_KEY` on the box**, sent as `x-discolike-key`. It never goes in a URL, log, commit or chat.
5. **Contact data stays on the box** for the retention period. Logs carry counts only.

## Not for

- Local businesses with a thin web presence. A digital-footprint score under 50 is excluded by default; use Alexandria's directories instead.
- Consumer or personal data.
