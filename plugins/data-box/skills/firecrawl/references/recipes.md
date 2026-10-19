# Firecrawl: recipes

Every recipe goes through data-box: `plan`, show the plan, get a yes, then `execute`. Prices are worst case at 1 credit a page (see [cost-map.md](cost-map.md)).

## Read one page that the free fetch could not

1. `scrape` with the URL. Rung 0 runs free. If it is blocked, the answer is a plan whose first paid rung is Firecrawl `/v2/scrape`.
2. Show the plan. On a yes, `execute` with `approve: true`.

Cost: 1 credit, or 5 if a JSON schema was asked for.

## "News from the last week about <company>"

1. `plan` with kind `search` and `request: "<company> news"`. Limit 10.
2. The plan prices 2 credits per 10 results. Scraping the results is a separate lane, at 1 credit a page, and only for the ones worth reading.
3. `execute`, then `job action=results`.

## "Every docs page on <site>"

1. `plan` with kind `crawl`, the URL, and `max_pages` at the number you would pay for.
2. The plan reserves `max_pages` credits and shows the include and exclude paths. In D3, map runs first for 1 credit and sets the limit from the site's real size.
3. `execute`. A stopped crawl is cancelled so it stops billing (D3).

## "The price and SKU from these 20 product pages"

- `plan` with kind `extract`, the 20 URLs and a JSON schema for `{price, sku}`.
- That is 5 credits a page, 100 credits in all. It shows up in the plan before anything is spent.

## "500 plumbers in Phoenix with phone numbers"

This is a `pull`, and it goes to the Alexandria directory lanes. See the **firecrawl-alexandria** skill, whose recipes page walks through it.
