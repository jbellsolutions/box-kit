# DiscoLike: cost map

DiscoLike bills per record returned and per domain processed. Its public docs do not list per-record prices; those are on its pricing page, by plan. The figures below are the disco-plugin's estimates and are **not calibrated**. D5 replaces them with rates measured from `GET /v1/usage`.

| What | Cost | Source |
|---|---|---|
| `count`, `contacts/count` | free of record charges | vendor docs |
| `usage`, `discogen/models`, email job polling, saved-query reads | free | vendor docs |
| `discover`, `contacts`, `contacts/discover`, `bulk-match`, `append` | about $3 per 1,000 records | disco-plugin estimate |
| `bizdata` and single-domain reads | under $0.01 each | disco-plugin estimate |
| `email/find` | billed only when it proves an address | vendor docs |
| DiscoGen (`discogen/process`) | per record plus model fees; cached 90 days, new domains only | vendor docs |
| `validate/icp` with `native-icp` | no LLM fee | vendor docs |
| Pro plan | $199 a month, needed for pulls over 10,000 records | disco-plugin |

In the table below, a `"cost": null` means the price is not known yet.

```json
{
  "tool": "discolike",
  "unit": "record",
  "checked": "2026-09-30",
  "calibrated": false,
  "source": "references/vendor-docs/pages/llms-full.txt; the DiscoLike disco-plugin's references/tool-cost-map.md (estimates)",
  "prices": [
    {"what": "count", "free": true},
    {"what": "contacts/count", "free": true},
    {"what": "usage", "free": true},
    {"what": "email job polling", "free": true},
    {"what": "discover record", "cost": 0.003, "unit": "usd", "estimate": true},
    {"what": "contacts record", "cost": 0.003, "unit": "usd", "estimate": true},
    {"what": "bizdata domain", "cost": 0.01, "unit": "usd", "estimate": true, "note": "upper bound"},
    {"what": "email/find proven address", "cost": null, "unit": "usd", "note": "billed only on success; rate unknown"},
    {"what": "pro plan", "cost": 199, "unit": "usd/month", "note": "pulls over 10,000 records"}
  ]
}
```
