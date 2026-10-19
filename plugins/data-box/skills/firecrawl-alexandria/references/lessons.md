# Firecrawl Alexandria: lessons

## 2026-09-28: six times the quote

- **What happened:**
  - The Hermes firecrawl profile quoted 1,200-1,400 credits for 5,000 realtors: Bing at 100 metros × about 2 pages.
  - It then ran Bing to 8 pages × 4 queries a metro: 2,018 calls, 30,002 raw rows, 7,508 unique.
  - It spent about 7,360-8,000 credits and deepened the run without showing a new budget.
- **Rules:**
  - Approve a plan before paying, and the approved amount binds.
  - Bing is capped at 3 pages and 2 queries a metro, and BBB is the base layer.
  - Repeat-page stop, target stop, a balance check every 15 calls with a floor of 0, and at most 3 lane errors.
  - See the **firecrawl** skill's lessons for the full table.

## 2026-09-28: the Hermes script's four defects

- **What happened.** `scripts/alexandria.py`, in the Hermes skill:
  - silently ran `items[0]` when find-tools missed;
  - printed the price and then paid, with no gate;
  - never filled required fields other than the query;
  - exited 0 on an empty result.
- **Rule.** data-box never swaps tools, fills every required input from the contract or drops the lane, gates every call behind an approved plan, and treats an empty result as a failure.

## 2026-09-28: 25 runnable tools, most of them irrelevant

- **What happened.** A roofers survey ranked GolfNow, SeatGeek and TickPick as lanes, and TickPick outranked Bing.
- **Rule** (#61). A tool must be a general directory for the entity, or be about the topic.

## 2026-09-30: free is not the same as ungated

- **What happened.** `apollo/people/search` costs 0 credits but answers `THIRD_PARTY_DATA_TERMS_REQUIRED` until an admin accepts its terms.
- **Rule.** Terms-gated lanes are listed as such and never planned. The same day, Justin excluded Apollo and FullEnrich altogether.

## 2026-09-30: the Hermes numbers disagree with each other

- **What happened:**
  - Bing's page size is "~30" in one Hermes note, but it was measured at 14.9 a call.
  - Truncation is put at "~p5" in one place and "p6+" in another.
  - Hermes' MoltSets figures quote enrichment windows as if they were search windows.
- **Rule.** Plans use measured numbers from data-box's own preflight, and the recipes record where each prior came from.
