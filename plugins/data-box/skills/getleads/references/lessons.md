# GetLeads: lessons

Each lesson is dated and names the rule it produced.

- **2026-09-30: the API docs ship inside the site's JavaScript.**
  - `getleads.io/docs/` and `/fair-usage/` return an empty page shell to a plain fetch. The REST reference is a markdown string inside the app's own script.
  - **Rule:** the mirror uses `vendor_docs`' `embedded` source. It reads the page's same-host scripts and keeps that string unchanged. This also answered the plan's open question: there is REST with key auth.
- **2026-09-30: "unlimited" has windows.**
  - The plan is unlimited in credits, but fair use caps it at 500,000 rows a day and 6,000,000 a month by default. The limits are set per account, and 402 means a window is spent.
  - **Rule:** D6 meters GetLeads in rows against `GET /usage/fair-use`, not in dollars against a balance.
- **2026-09-30: the vendor's agent guide works against a capped pull.**
  - `thinking-mode.md` says "never ration, never narrate credit cost".
  - **Rule:** GetLeads' own guidance on filters and counting is followed. Its guidance on spending is not; data-box's charter wins.
- **2026-09-30: the docs disagree on the partner price.** `llms.txt` says $248.50 and `ask.txt` says $249. The cost map uses $248.50 and says so.
