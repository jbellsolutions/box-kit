# Consulti: recipes

Sketches of what a D6 plan runs. Each starts with the free calls, and the plan shows the worst-case credits before anything is spent.

## 100 roofing companies in Texas with an owner email (local)

1. `GET /meta/local-states` for the exact value for Texas. Filters are exact matches, so neither "TX" nor "Texas" is a safe guess.
2. Preflight: `POST /local-leads/search` `{"q": "roofing", "states": ["<that value>"], "hasOwnerEmail": true, "size": 5}`, at most 5 credits.
3. The plan: 1 page of 100, worst case 100 credits, deduped with the other lanes on name + phone + address.

## VPs of Marketing at Shopify stores (B2B)

1. `GET /meta/technologies` and `GET /meta/industries`, both free, for the exact values.
2. `POST /leads/search` `{"titles": ["VP Marketing"], "technologies": ["Shopify"], "size": 25}` as the preflight.
3. The plan pages at 100 a page up to the target. It stops at `has_more: false` or once the deduped count is reached.

## Podcasts about AI with a verified email (creators)

`POST /creator-leads/search` `{"source": "podcast", "q": "artificial intelligence", "size": 50}`. The entity is `creator`. Every row has a verified, non-catch-all email.

## Enrich a shortlist of LinkedIn URLs

This runs only after discovery and dedupe:
- `POST /enrich/linkedin` per URL: 1 credit when an email returns.
- Misses are free and go to `misses.jsonl`, so a resumed run never asks again.
