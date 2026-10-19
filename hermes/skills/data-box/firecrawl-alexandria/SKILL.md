---
name: firecrawl-alexandria
description: Use for lists of businesses, people or records from Firecrawl's Alexandria catalog (82 data providers, 564 tools read live in September 2026) - business directories such as BBB, Bing and Google Maps places, trade directories, and research, developer and government indexes. data-box surveys the whole catalog for free, keeps only tools about the request, prices the pull in credits and dollars, and runs it only after approval, with page, query and balance caps. It exists because the 2026-09-28 pull cost six times its quote.
---

# Firecrawl Alexandria

Alexandria is Firecrawl's catalog of structured-data tools. It works in three steps: discover a tool, inspect its inputs and price, then run it through `POST /v2/scrape` with `{"alexandria": {provider, capability, options}}`.
- **Discovery and inspection are free.**
- **Running a tool costs the credits it lists.**

It is tier 1 in data-box and the first choice for a list of businesses.

## When to use it

- **A list of businesses:** `plan` with kind `pull` and entity `business`. BBB (1 credit, 15 a page) is the base layer; Bing and Google Maps (5 credits a call) top it up.
- **Home-trades professionals:** the Houzz directory.
- **Papers, code docs, government data:** the research, developer and government indexes, reached through `search`.
- **Contacts for people:** not here. Apollo and FullEnrich are **excluded by Justin's decision on 2026-09-30**, and they come out of the code in D3. Use **moltsets**, **getleads** or **consulti** on the deduped shortlist.

## How

1. `sources` with the request: a free survey of every tool that could serve it. Each comes with price, page size, pagination, field fit and terms status, and any tool not about the request is dropped with the reason.
2. `plan`: the ranked lanes, with category × place cells, the worst-case credits and dollars against the live balance, and preflight samples (25 credits at most).
3. **Show the whole plan to the user and wait for a yes.**
4. `execute` with `approve: true`. It stops at the approved amount, the page and query caps, the unique-record target, or the balance floor, whichever comes first. Calling it again resumes without paying twice.

## Never

- Accept a provider's terms. A `THIRD_PARTY_DATA_TERMS_REQUIRED` answer has a `requiresAction.url`. Give the URL to Justin; an org admin accepts the terms. data-box marks such lanes "terms required" and never plans them.
- Page "until `has_more` is false". Pages × queries × cells is the multiplier that burned 2026-09-28 ([references/lessons.md](references/lessons.md)).
- Run a tool because it scored well without being about the request (TickPick for roofers).
- Use `["web", "alexandria"]` for discovery. It pays for the web results; `["alexandria"]` alone is free.
- Use BBB as the only lane for a broad vertical. It skews toward accredited firms.

## References

- [references/charter.md](references/charter.md), [references/handoff.md](references/handoff.md), [references/best-practices.md](references/best-practices.md), [references/lessons.md](references/lessons.md), [references/cost-map.md](references/cost-map.md), [references/recipes.md](references/recipes.md)
- [references/vendor-docs/](references/vendor-docs/PROVENANCE.md): Firecrawl's Alexandria, research and developer index, billing, rate-limit and endpoint docs, mirrored 2026-09-30.
- The general Firecrawl skill (**firecrawl**) covers scrape, search, crawl and extract.
