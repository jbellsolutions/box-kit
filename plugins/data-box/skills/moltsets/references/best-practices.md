# MoltSets: best practices

- **Read `get_account` before a run, and store `metadata.fair_use.records_remaining_5h` after every page.** Stop before the window is spent. A 429 may carry `metadata.retry_after`.
- **Probe with `limit: 1`** to read `total`, then pull the smallest segments first. `total` caps at 10,000, and so does paging.
- **Use exact values.**
  - Filters are exact-match with full names: "Texas", "United States", "C Suite".
  - A misspelt value returns nothing, and still counts as a request.
  - NAICS codes and the other value lists are in the mirrored docs.
- **Exclude in the query, not afterwards.** An excluded record is never returned and costs nothing. Dropping 5 of 25 yourself costs all 25.
- **Use one of `department` or `functional_area`.** They are the same data.
- **Batch enrichment by 100.** `linkedin_to_mobile_phone` takes up to 100 profiles a call. Pause between batches; do not fire everything at once.
- **Choose the email tool by what you need.**
  - `linkedin_to_business_email` is for a work address.
  - `linkedin_to_best_email` returns the best verified address, business or personal.
  - Measured on micro-business lists: personal email hit about 24%, business-only close to 0. Plan for misses.
- **Keep the quotas apart.** Search records, enrichment records, the token balance and phone tokens are separate. Phone tokens come from their own monthly add-on.
- **Append before you advance.** Write each page to JSONL before updating the resume state, and run one instance at a time.
