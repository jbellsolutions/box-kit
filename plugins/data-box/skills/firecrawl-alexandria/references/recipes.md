# Firecrawl Alexandria: recipes

## "50 roofing contractors in Austin TX, with phone and website" (the D1 bounded pull)

1. `plan` with `request: "roofing contractors in Austin TX"`, `count: 50`, `fields: ["phone", "website"]`.
   - Intake splits the place ("Austin TX") from the topic ("roofing contractors").
   - The survey keeps directories and roofing tools and drops the rest, with reasons.
2. The plan priced 21 credits worst case on 2026-09-28:
   - BBB, a few pages for Austin;
   - Bing, 2 queries, up to 3 pages;
   - Maps, 1 call per query.
3. Show it and wait for a yes. Then `execute` with `approve: true`.
4. It stops at 50 unique records, or at the cap if that comes first.
5. `job action=export format=csv`.

## "5,000 realtors across the US" (the one that burned 2026-09-28, done right)

1. Survey. BBB's real-estate categories partitioned by state (1 credit, 15 a page) come first, because they are cheapest per record.
2. The plan shows the worst case against the balance. On Hobby's 5,000 credits a month, a list this size does not fit alongside anything else, and the plan says so.
3. The top-ups are Bing, capped at 2 queries and 3 pages a metro, over the top 100 metros.
   - The worst case is shown before approval: 100 × 2 × 3 × 5 = 3,000 credits.
   - The expected cost is lower, because the repeat-page and target stops end cells early.
4. Going deeper is a new plan with a new yes. It never happens mid-run.

## "Research papers on CRISPR base editing"

- `search` against the research index. Its endpoints are in the mirrored `features/research.md`.
- Only the scraping of chosen papers is a paid lane.
