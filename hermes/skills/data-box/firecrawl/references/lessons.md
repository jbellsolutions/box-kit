# Firecrawl: lessons

Each lesson is dated and names the rule, and the guard in code, that it produced.

## 2026-09-28: the credit burn (Hermes firecrawl profile, "5,000 active U.S. realtors")

**What happened**
- The quote was 1,200-1,400 credits: Bing at 100 metros, about 2 pages each.
- The run paged Bing up to 8 pages × 4 queries per metro. That was 2,018 calls, which returned 30,002 raw records and 7,508 unique ones.
- The agent deepened the run halfway through without showing a new budget.
- It spent about 7,360 credits by the agent's own count, or about 8,000 by Justin's. The month's 5,000 were gone, and the balance went negative. It was −330 on 2026-09-30.
- The profile's session log shows a larger figure too (calls × list price). It overcounts, because Bing's truncated pages are billed 0. The agent's count and the balance drop are the numbers to use.

**The rules, and the guards that enforce them in data-box (D1)**

| Rule | Guard |
|---|---|
| Nothing paid runs without an approved plan, and the plan's budget binds | `execute` refuses a missing, expired or unapproved plan, and it reserves before every call |
| Deepening a run means a new plan | the approved amount is a hard cap; there is no "keep going" |
| Pages and queries have caps per cell | `DEFAULT_MAX_PAGES` is 5 |
| Stop paging once a page is mostly repeats | `DATABOX_MIN_NEW_RATIO` (30%) |
| Stop when the target is met | the unique-record target |
| Read the balance while running | every 15 calls (`BALANCE_EVERY`), with a floor of 0 |
| A failing lane does not keep paying | `LANE_ERROR_LIMIT` is 3 |

**Hermes follow-up.** The Hermes skill fixed its SKILL.md, but its `firecrawl-alexandria-provider-playbook.md` still says "follow pages until `has_more:false`", and so does its census playbook. Those are Justin's Hermes files and have not been changed. The rule here overrides them.

## 2026-09-28: the survey picked tee times for a roofers pull

**What happened.** The live survey for "roofing contractors in Austin TX" marked 25 Alexandria tools runnable. Most were GolfNow, SeatGeek, Trader Joe's and the like, and TickPick outranked Bing on records per credit. With credits, preflight would have paid for them.

**Rule** (#61):
- A catalog tool serves only if it is a general directory for the entity, or its description mentions the request's topic.
- The place in the sentence goes to the location input.

## 2026-09-30: a failed page is not free

**What happened.** Firecrawl's billing docs, mirrored here, charge 1 credit whenever the target answered, 403 and 404 included. Only a call that returns no document is free.

**Rule:**
- Plans price every reached page.
- `execute` treats an unknown outcome (a timeout or 5xx) as charged in full.
- A 4xx refusal from Firecrawl itself is free (D2c).

## 2026-09-30: Bing truncates without saying so

**What happened.** The Hermes notes record Bing's business search returning short or empty pages past about page 5 or 6. They put the page size near 30, but it was measured at 14.9 records a call.

**Rule:**
- The repeat-page stop catches truncation.
- Ranking uses the measured page size, not the advertised one.
- D3 adds a test for the silent truncation.
