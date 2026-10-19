# Firecrawl Alexandria: cost map

Credits come from the Firecrawl balance, at $0.0038 a credit on Hobby (`DATABOX_FIRECRAWL_USD_PER_CREDIT`).
- **Always free:** discovery and inspection.
- **Everything else:** a tool's live price in find-tools is the authority. The prices below are priors, verified in September 2026.

| What | Credits | Notes |
|---|---|---|
| `search` with `sources: ["alexandria"]` | free | discovery |
| `find-tools` inspect | free | inputs, response contract, price |
| `domainTools` matching | free | the search or scrape it rides on is billed |
| `bbb-business-profiles-ratings-complaint/businesses/search` | 1 a call | 15 a page, up to page 100 |
| `bbb-org` | 5 a call | not the cheap BBB lane |
| `bing-com/businesses/search` | 5 a call | measured 14.9 records a call; truncates near page 5 |
| `maps-google-com/businesses/search` | 5 a call | 20 places, no pagination |
| `houzz-com/professionals/search` | 5 a page | |
| Developer index search | 2 per 10 results | |
| A result with no document | 0 | empty calls are free |
| Apollo and FullEnrich tools | excluded | policy, 2026-09-30 |

```json
{
  "tool": "firecrawl-alexandria",
  "unit": "credit",
  "usd_per_unit": 0.0038,
  "checked": "2026-09-30",
  "source": "references/vendor-docs/pages/features/alexandria.md, billing.md; Hermes firecrawl-alexandria skill (verified 2026-09)",
  "prices": [
    {"what": "search sources=[alexandria]", "free": true},
    {"what": "find-tools inspect", "free": true},
    {"what": "domainTools matching", "free": true},
    {"what": "bbb-business-profiles-ratings-complaint/businesses/search", "cost": 1, "per": "call", "page_size": 15},
    {"what": "bbb-org", "cost": 5, "per": "call"},
    {"what": "bing-com/businesses/search", "cost": 5, "per": "call", "page_size": 14.9},
    {"what": "maps-google-com/businesses/search", "cost": 5, "per": "call", "page_size": 20},
    {"what": "houzz-com/professionals/search", "cost": 5, "per": "page"},
    {"what": "developer index search", "cost": 2, "per": "10 results"},
    {"what": "call returning no document", "free": true}
  ],
  "excluded": ["apollo", "fullenrich"]
}
```
