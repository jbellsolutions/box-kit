# MoltSets

**Status (2026-09-23).**
- **Key:** verified through the free account and billing calls, and set on the droplet.
- **Plan:** a subscription with fair-use limits. Enrichment, for example, is limited to 75k a week.
- **Wiring:** nothing calls MoltSets yet. It arrives in M4, as a `run` source.

MoltSets is one of two contact-data services approved for data-box as an explicit exception to the "no paid enrichment" rule; DiscoLike is the other. The exception comes with conditions:
- MoltSets runs **only when a caller names it**, with a cap. It is never on Jev's automatic path.
- In lead intent, it runs only after a lead has qualified.

## What it gives data-box

People and company contact data. Its tools are all `POST https://api.moltsets.com/api/v1/tools/<tool>`:

| Kind | Tools |
|---|---|
| Free: account | `get_account`, `get_billing`, `get_usage` |
| Search | `search_people`, `search_companies`, `search_linkedin_profile` |
| From a LinkedIn profile | `linkedin_to_best_email`, `linkedin_to_business_email`, `linkedin_to_personal_email_usa`, `linkedin_to_mobile_phone`, `linkedin_to_sha256` |
| Reverse lookups | `reverse_email_lookup`, `reverse_linkedin_lookup`, `email_to_linkedin`, `email_to_maid`, `ip_to_company` |

Every tool except the account tools uses credits.

## How data-box calls it

- **Auth:** `Authorization: Bearer $MOLTSETS_API_KEY`.
- **MCP:** MoltSets also runs an MCP server (`mcp.moltsets.com/mcp`). data-box uses the REST tools, so each call goes through the cap and the ledger.
- **Contact data:**
  - It stays in the job that asked for it and is deleted after the retention period.
  - It never goes into logs, learnings or the repo.
  - Justin sets the retention period and the per-call cap.

## Primary docs

- https://developer.moltsets.com (MoltSets MCP guide: `/integrations/moltsets-mcp`)
