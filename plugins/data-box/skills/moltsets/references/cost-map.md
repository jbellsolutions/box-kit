# MoltSets: cost map

MoltSets sells flat monthly plans, metered by fair-use windows in records. Tokens are charged only when data comes back; a miss costs nothing but still counts as a request. Prices and windows below are from the mirrored docs, checked 2026-09-30.

| Plan | Search records (5 h / week) | Enrichment records (5 h / week) |
|---|---|---|
| Free | 100 lifetime (5 a call) | 1,000 lifetime |
| $27 a month | 500 / 2,500 | 1,000 / 5,000 |
| $97 a month | 7,500 / 37,500 | 15,000 / 75,000 |
| $397 a month | 75,000 / 375,000 | 150,000 / 750,000 |
| $997 a month | 112,500 / 562,500 | 225,000 / 1,125,000 |

**Phone tokens** are a separate monthly add-on, one token per mobile found:
- $27 for 180;
- $97 for 646;
- $197 for 1,313.

That is about $0.15 a token.

**Dollars per record, for ranking.** Amortized from the plan fee and the records actually used. It is Justin's call until measured (planned: `DATABOX_MOLTSETS_USD_PER_RECORD`, once D5 gives MoltSets the unit `record` under D2's `DATABOX_<NAME>_USD_PER_<UNIT>` rule).

```json
{
  "tool": "moltsets",
  "unit": "record",
  "checked": "2026-09-30",
  "source": "references/vendor-docs/pages/developer-llms-full.txt (Rate Limits), pricing.md",
  "prices": [
    {"what": "get_account, get_billing, get_usage", "free": true, "note": "count as requests"},
    {"what": "not_found lookup or search", "free": true, "note": "counts as a request"},
    {"what": "search record returned", "cost": 1, "unit": "search record (window)"},
    {"what": "enrichment hit", "cost": 1, "unit": "enrichment record (window)"},
    {"what": "mobile phone found", "cost": 1, "unit": "phone token", "usd_approx": 0.15},
    {"what": "plan $27", "cost": 27, "unit": "usd/month", "windows": {"search_5h": 500, "search_week": 2500, "enrich_5h": 1000, "enrich_week": 5000}},
    {"what": "plan $97", "cost": 97, "unit": "usd/month", "windows": {"search_5h": 7500, "search_week": 37500, "enrich_5h": 15000, "enrich_week": 75000}},
    {"what": "plan $397", "cost": 397, "unit": "usd/month", "windows": {"search_5h": 75000, "search_week": 375000, "enrich_5h": 150000, "enrich_week": 750000}},
    {"what": "plan $997", "cost": 997, "unit": "usd/month", "windows": {"search_5h": 112500, "search_week": 562500, "enrich_5h": 225000, "enrich_week": 1125000}}
  ]
}
```
