# Consulti: cost map

From Consulti's API reference, mirrored 2026-09-30. What a credit costs in dollars depends on the plan; set `DATABOX_CONSULTI_USD_PER_CREDIT` when the plan is known (the naming rule is D2's, #63; data-box reads it once D6 wires Consulti). Until then data-box will not price or run a Consulti lane.

| What | Credits | Notes |
|---|---|---|
| `/leads/search`, `/local-leads/search`, `/creator-leads/search`, `/instagram/search` | 1 lead credit a row returned | reserved up to `size` (max 100), refunded to the rows returned; 0 rows = 0 |
| `/leads/find-by-name`, `/leads/enrich` | 1 lead credit on a match | a 404 no-match is refunded, not verified |
| `/enrich/linkedin` | 1 lead credit when an email returns | the US mobile is a free add-on |
| `/verify` | 1 verification credit on success | 400/401/402 never billed |
| `/verify/catchall` | 5 verification credits | Pro plan or higher |
| `/credits`, `/meta/{filter}`, `/lists` | free | |

```json
{
  "tool": "consulti",
  "unit": "credit",
  "usd_per_unit": null,
  "checked": "2026-09-30",
  "source": "vendor-docs/pages/llms.txt",
  "prices": [
    {"what": "search a page of leads", "cost": 1, "per": "row returned", "note": "b2b, local, creator, instagram; size max 100"},
    {"what": "find by name or enrich by email", "cost": 1, "per": "match"},
    {"what": "linkedin to work email", "cost": 1, "per": "email returned", "note": "mobile phone free"},
    {"what": "verify an email", "cost": 1, "per": "verification", "note": "verification credits"},
    {"what": "verify a catch-all", "cost": 5, "per": "verification"},
    {"what": "credits balance", "free": true},
    {"what": "filter values", "free": true},
    {"what": "lists", "free": true}
  ]
}
```
