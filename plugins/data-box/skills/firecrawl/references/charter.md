# Firecrawl: charter

**Tier 1, the default for anything web-shaped.** Firecrawl is the first paid rung after data-box's free fetch, the engine for search, crawl and extract plans, and (through Alexandria, a separate skill) the first place a lead or data pull looks.

## What it is for

- **Scrape rung 1:** a page the free pinned fetch could not read: blocked, challenged, or rendered by JavaScript. Firecrawl renders it (proxy `auto`, enhanced proxies at no extra cost) and returns markdown, HTML, links or JSON.
- **Search:** web and news results for queries, 2 credits per 10 results.
- **Crawl and map:** every page of a site up to a limit, or just its URLs.
- **Extract:** fields out of known pages, through a JSON schema or a prompt.
- **Alexandria and the browser:** see the `firecrawl-alexandria` and `firecrawl-browser` skills.

## Rules

1. **Money moves only inside an approved data-box plan.** A plan shows the worst case in credits and dollars against the live balance; the user says yes; `execute` spends at most that. Direct calls to Firecrawl are for free reads only (balance, queue status, Alexandria discovery).
2. **Every run has caps:** pages per cell, queries per place, a unique-record target, a balance floor, and a stop when pages start repeating. A plan without caps is not a plan.
3. **Worst case, not average.** A failed page that Firecrawl reached still costs 1 credit. Budgets assume every planned page is bought.
4. **One key, shared.** The Hermes firecrawl profile and data-box use the same key and the same 5,000 credits a month. data-box leaves one of the 5 concurrent browsers free.
5. **The key never leaves the box's environment** (`FIRECRAWL_API_KEY` in the server's environment: `/etc/data-box.env` on a systemd install). Never in a URL, a log, a commit, a skill or a chat.
6. **Firecrawl's data terms are the user's to accept.** data-box never accepts terms; a plan lists terms-gated lanes as unable to run.

## What it is not for

- Contact reveal (emails, phones) at discovery scale: that is MoltSets, GetLeads or Consulti, on a deduped shortlist.
- Company discovery by similarity: DiscoLike.
- Buyer intent: Lead Radar.
- Logged-in, multi-step browsing at volume: browser-box.
