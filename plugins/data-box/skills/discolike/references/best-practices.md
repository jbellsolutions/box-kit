# DiscoLike: best practices

- **Iterate on `count`.** It takes the same filters as `discover` (not lookalike, paging or AI fields) and bills no records. Stop when the number is a segment someone would actually work.
- **Seed with real domains.** Three to ten good customers make better lookalikes than a long ICP paragraph. `icp_prompt` (up to 4,000 characters) extracts filters and suggests seeds in one call. Check what it chose before paying.
- **Filters.** `phrase_match` and `negate_phrase_match` take up to 20 fragments each, at least 3 characters. `state` needs a single `country`. The `digital_footprint` score runs 0-800 and defaults to a minimum of 50.
- **Page past 10,000 with exclusion lists.** One `discover` returns at most 10,000. The CLI's `bulk` saves each page as an exclusion list for the next; D5 does the same.
- **Validate small.** Start `validate/icp` or DiscoGen with a handful of domains, never the whole list. `integration_id="native-icp"` scores fit with no LLM fee. DiscoGen caches for 90 days and bills only new domains.
- **Pace requests.** A 429 carries `Retry-After`. Rate limits go by plan tier, from Starter at 1× to Enterprise at 20×. Do not fan out hundreds of calls at once.
- **Poll email jobs for free.** Only the original `find` bills, and only when it proves an address.
- **Watch spend.** `GET /v1/usage` gives month-to-date requests, records, spend and recent billing events, and it is free.
