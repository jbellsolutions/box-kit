# DiscoLike

**Status (2026-09-23).**
- **Key:** an API key was supplied, but DiscoLike rejects it. `GET /usage` returns 403 with "API Key is inactive or expired". Reactivate or regenerate it in the DiscoLike dashboard.
- **Wiring:** tier 1, wired in D2 as a discovery lane inside approved plans ("disco" in a request's `sources` names it). Until D2 every survey lists it with that reason.

DiscoLike is one of two contact-data services approved for data-box as an explicit exception to the "no paid enrichment" rule; MoltSets is the other. Like MoltSets:
- it is tier 1, but runs **only inside a plan the user approved**, within that plan's budget;
- it never runs on Jev's automatic path;
- in lead intent, it runs only after a lead has qualified.

## What it gives data-box

Company discovery and firmographics. DiscoLike says it covers more than 80 million companies; that figure is DiscoLike's own, not measured here. Its endpoints include:

- **Companies:** discover (lookalikes and filters), bizdata, match (single and bulk), score, segment, extract, subsidiaries, vendors.
- **People:** contacts discover and lookup, email find.
- **Account:** usage.

## How data-box calls it

- **Base URL:** `https://api.discolike.com/v1`
- **Auth:** the header `x-discolike-key: $DISCOLIKE_API_KEY`
- **Checking the key:** `GET /usage` is free.
- **OpenAPI spec:** https://api.discolike.com/v1/openapi.json
- **MCP:** DiscoLike's MCP server (`https://api.discolike.com/v1/mcp`) signs in only with OAuth in a browser, so a server can't use it unattended. data-box uses the REST API with the key.

## Primary docs

- https://docs.discolike.com (API authentication, API keys, usage, MCP)
