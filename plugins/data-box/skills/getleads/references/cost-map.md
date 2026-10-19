# GetLeads: cost map

GetLeads has two balances:
- **Plan credits:** 1 per item where `success` is true. Unlimited plans have no credit balance and are capped by fair-use windows instead.
- **Wallet cash:** prepaid, only for the LinkedIn scraping products.

Prices below are from the mirrored docs, checked 2026-09-30.

| What | Cost |
|---|---|
| `POST /contacts/search/count`, `GET /contacts/filter-values`, `GET /usage/fair-use` | free |
| `POST /contacts/search`, `/search/export` | 1 credit a row returned; on unlimited, rows count against the windows |
| `POST /enrich/from-email`, `/from-linkedin`, `/from-person` | 1 credit per item where `success` is true; a miss is free |
| `POST /contacts/lookup/colleagues` | 1 credit per record returned; 0 if none |
| Phone lookup | 1 credit per match |
| Unlimited plan | $497 a month; fair use of 500,000 rows a day and 6,000,000 a month by default |
| Partner plan | $248.50 a month (`ask.txt` says $249) |
| Credit top-up | $97 for 10,000 credits |
| Profile monitoring | $0.012 per engager, from the wallet |
| Website visitor identification | $0.125 per identified lead, from the wallet |
| Company followers | $3.50 per 1,000 followers, $8.75 minimum, from the wallet |
| Free trial | 14 days, 1,000 exports, card required |

**Dollars per row, for ranking.** It is amortized: the monthly fee divided by the rows actually pulled that month. Until data-box has a month of pulls, the rate is Justin's call (planned: `DATABOX_GETLEADS_USD_PER_ROW`, once D6 gives GetLeads the unit `row` under D2's `DATABOX_<NAME>_USD_PER_<UNIT>` rule).

```json
{
  "tool": "getleads",
  "unit": "row",
  "checked": "2026-09-30",
  "source": "references/vendor-docs/pages/api-docs.md, ask.txt, llms.txt",
  "prices": [
    {"what": "contacts/search/count", "free": true},
    {"what": "contacts/filter-values", "free": true},
    {"what": "usage/fair-use", "free": true},
    {"what": "contacts/search row", "cost": 1, "unit": "credit", "note": "unlimited plans: counts against fair-use windows instead"},
    {"what": "contacts/search/export row", "cost": 1, "unit": "credit", "note": "50,000 rows a request"},
    {"what": "enrich item where success is true", "cost": 1, "unit": "credit", "note": "a miss is free"},
    {"what": "lookup/colleagues record", "cost": 1, "unit": "credit"},
    {"what": "unlimited plan", "cost": 497, "unit": "usd/month", "note": "500,000 rows/day, 6,000,000 rows/month by default"},
    {"what": "partner plan", "cost": 248.5, "unit": "usd/month"},
    {"what": "credit top-up", "cost": 97, "unit": "usd per 10,000 credits"},
    {"what": "profile monitoring engager", "cost": 0.012, "unit": "usd", "note": "wallet"},
    {"what": "website visitor lead", "cost": 0.125, "unit": "usd", "note": "wallet"},
    {"what": "company followers", "cost": 3.5, "unit": "usd per 1,000", "note": "wallet, $8.75 minimum"}
  ]
}
```
