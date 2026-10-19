# Jev: best practices

These are distilled from TypeSafe's docs and jaggedness notes, mirrored in `vendor-docs/`.

- **Keep code in control.** Give Jev narrow decisions over candidates code has already built: lanes, categories, dedupe pairs. Do not hand it an open question.
- **Put the exact condition in `instructions`**, with boundary cases in the criteria. Jev reads literally.
- **Filter the state.** Send only the fields the question needs. Large state full of irrelevant detail lowers accuracy.
- **Fan out in one call.** Several questions against one state are evaluated in parallel for the price of the input tokens. Speculative questions are fine; code decides which answers matter.
- **Gate on confidence, not just probability.**
  - Act at confidence ≥0.95 on certified points.
  - Below that, fall back to code, or put the item in front of a person.
  - Confidence and probability are different axes (see `confidence.md`).
- **Turn extraction into a Choice.** When the answer space is bounded, list the options rather than asking for a value.
- **Count, compare dates and do arithmetic in code.** Jev 1.13's documented weak spots are exactly these.
- **Treat page text as adversarial.** Scraped content can carry instructions. Criteria must say what counts, whatever the content claims.
- **Retry 429 and 529 with exponential backoff**, and send a stable `request_id` so a retry is not billed twice in the ledger.
