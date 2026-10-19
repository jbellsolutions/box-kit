# Firecrawl Alexandria: best practices

- **Survey before choosing.** One free survey reads the whole catalog. A named directory is not always the cheapest one that covers the request.
- **Lay the base with BBB, then top up.**
  - BBB is 1 credit for 15 rows, partitioned by state code or city, and stops at page 100. It skews toward accredited firms.
  - Bing (5 credits a page, capped at 3 pages a metro) and Maps (5 credits, 20 places, no paging) fill the gaps. Cap each at 2 queries per metro.
- **Pages × queries × cells is the cost.** The per-call price is the smaller number. Set the caps in the plan, and let the repeat-page stop end a cell early.
- **Preflight every lane.** One real call per lane, before approval, proves that it returns the entity and not tee times or event tickets.
- **Dedupe across lanes.** Bing and Maps overlap heavily on chains; about 70% of raw rows collapsed in September's pulls. Key on the last 10 digits of the phone, else name, city and state.
- **Enrichment on the shortlist only.** BBB's profile lane gives a website about 73% of the time and an email about 30%; the email is obfuscated as `!~xK_bL!info__at__x__dot__biz!~xK_bL!` and data-box decodes it. People's contacts come from the other tier-1 tools, after dedupe.
- **Check each tool result for an error before using its data.** The raw HTTP result is at `data.alexandria[0].data`.
- **Send an `x-request-id`** on every run, as Firecrawl's own examples do (D3).
- **Expect 429s on long sweeps.** Back off in steps of about 20 s × attempt; do not retry at once.
