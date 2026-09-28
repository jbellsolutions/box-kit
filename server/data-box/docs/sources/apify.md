# Apify

**Status (2026-09-23).** `APIFY_TOKEN` is present on the droplet. data-box does not call Apify yet; the catalog and `run` arrive in M4.

## What it gives data-box

Apify Store actors are purpose-built scrapers for particular platforms: LinkedIn, Google Maps, Amazon, Instagram, TikTok, Upwork and others. For records from a named platform, an actor is usually cheaper and more reliable than scraping the pages directly.

- **Catalog size:** 65,004 Store actors, measured through `GET /v2/store` on 2026-09-23. Apify's marketing says about 73k, and the difference is not explained.
- **In data-box:** every actor becomes a catalog row with its title, description, input schema and pricing model. Input schemas are fetched when first needed, then cached. `sources` searches the rows; `run` runs one of them.

## How data-box calls it (M4)

- **Listing:** `GET https://api.apify.com/v2/store`, paginated. The full list is refreshed weekly, and the newest actors daily.
- **Running:** `POST /v2/acts/{actor}/runs` with `maxTotalChargeUsd` set from the caller's cap. data-box reserves that cap in the ledger before starting the run, then settles to Apify's reported usage when the run finishes.
- **Auth:** `Authorization: Bearer $APIFY_TOKEN`.

## Rules

- A run never starts without a cap.
- Actors that collect personal data follow the contact-data rule: the results stay in the job that asked for them.

## Primary docs

- https://docs.apify.com/api/v2
