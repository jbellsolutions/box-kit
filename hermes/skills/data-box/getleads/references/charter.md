# GetLeads: charter

**Tier 1 data tool, approved by Justin on 2026-09-30** as one of data-box's paid lead sources. Wired in milestone D6, once there is a subscription and a key.

## What it is for

- **B2B discovery:** people by company, domain, title, seniority, place, email status, phone presence; decision makers and colleagues at a company.
- **Enrichment on a shortlist:** a person from a work email, a LinkedIn URL, or a name and company.

## Rules

1. **Paid use only inside an approved data-box plan.** The plan is flat, but each row still draws on the daily and monthly fair-use windows; a plan shows the rows it will draw and the window that binds first.
2. **Count before pulling.** `search/count` is free; a query over 50,000 matches is narrowed before any page is pulled.
3. **Enrichment runs on the deduped shortlist only.**
4. **No reselling of raw contact data**, and no bulk pulls that rebuild the database, per GetLeads' fair-use policy.
5. **Contact data stays on the box** and is deleted after the retention period; logs carry counts only.
6. **The key is `GETLEADS_API_KEY` on the box**, never in a URL, log, commit, skill or chat.

## Not for

- The LinkedIn scraping products billed from the prepaid wallet (profile monitoring, website visitors, company followers): outside data-box's plans.
- Local businesses without a B2B footprint: Consulti's local search, or Firecrawl's Alexandria directories.
