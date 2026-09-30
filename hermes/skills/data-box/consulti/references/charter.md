# Consulti: charter

**Tier 1 data tool, approved by Justin on 2026-09-30** as one of data-box's paid lead sources (with DiscoLike, MoltSets and GetLeads). Wired in milestone D6.

## What it is for

- **Discovery with emails already verified:** B2B people (`/leads/search`), local businesses from Google Maps (`/local-leads/search`), creators (`/creator-leads/search`), Instagram accounts (`/instagram/search`).
- **Enrichment on a shortlist:** one person from a name and company, an email, or a LinkedIn URL.
- **Email verification** before a send.

## Rules

1. **Paid calls only inside an approved data-box plan**, priced as page size x pages x 1 credit, settled to `credits_used`.
2. **No blind retries.** Consulti bills a retried search again. A paid call whose outcome is unknown is checked against `GET /credits`, never simply re-sent.
3. **Enrichment endpoints run on a deduped shortlist,** never at discovery scale.
4. **Verified emails first.** data-box's merger prefers a row whose `email_status` is verified over one that is not.
5. **Contact data stays on the box** and is deleted after the retention period; logs carry counts, never emails or phones.
6. **The key is `CONSULTI_API_KEY` on the box**, never in a URL, log, commit, skill or chat.

## Not for

- Company discovery by similarity (DiscoLike) or buyer intent (Lead Radar).
- Scraping pages (Firecrawl).
