# Lead Radar: cost map

Lead Radar spends on its own providers and reports the total in dollars as `cost_usd`. data-box reserves the plan's `max_cost_usd` and settles to that figure.

| What | Cost |
|---|---|
| `dry_run` estimate | free |
| A hunt | the reported `cost_usd`, capped by `max_cost_usd` |
| ScrapeCreators, inside Lead Radar | 1 credit a call; Instagram comments with replies, 15 |
| Stage 1 (Jev), inside Lead Radar | $0.042 per million input tokens |
| Stage 2 (reasoning model), inside Lead Radar | per post that Stage 1 did not settle |

In the table below, a `"cost": null` means the price is not known yet.

```json
{
  "tool": "lead-radar",
  "unit": "usd",
  "checked": "2026-09-30",
  "source": "LEAD_RADAR_V2_SPEC.md sections 5, 6 and 11; lead-radar docs/radar/scrapecreators-endpoints.md",
  "prices": [
    {"what": "hunt dry_run estimate", "free": true},
    {"what": "hunt", "cost": null, "unit": "usd", "note": "reported cost_usd, capped by max_cost_usd"},
    {"what": "ScrapeCreators call (inside Lead Radar)", "cost": 1, "unit": "credit"},
    {"what": "ScrapeCreators Instagram comments with replies", "cost": 15, "unit": "credit"},
    {"what": "Jev stage 1 (inside Lead Radar)", "cost": 0.042, "unit": "usd per million input tokens"}
  ]
}
```
