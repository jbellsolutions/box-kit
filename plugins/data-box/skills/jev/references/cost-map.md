# Jev: cost map

Jev bills input tokens only. A typical data-box decision has about 1,000-3,000 tokens of state and questions, which is roughly $0.00004-0.00013 a call. The default monthly cap of $5 covers tens of thousands of decisions.

| What | Cost |
|---|---|
| Input tokens | $0.042 per million ($42 per billion) |
| Output tokens | free |
| Failed request (401, 429) | not billed |

```json
{
  "tool": "jev",
  "unit": "input token",
  "checked": "2026-09-30",
  "source": "references/vendor-docs/pages/models.md",
  "prices": [
    {"what": "input tokens", "cost": 0.042, "unit": "usd per million"},
    {"what": "output tokens", "free": true}
  ],
  "cap": {"env": "DATABOX_JEV_MONTHLY_USD", "default_usd": 5, "status": "planned, D8"}
}
```
