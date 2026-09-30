---
description: Turn a public URL into markdown, text, HTML or its links through your data-box server.
argument-hint: <url> [markdown|text|html|links]
allowed-tools: [Read]
---

Use the `data-box` skill. Call the data-box `scrape` tool with the URL from: $ARGUMENTS
(format defaults to markdown; use the second word as `format` if given).

Report the title, final URL and the content (or links). If the result has `blocked`, say what
stopped it. If it also carries a `plan`, show its rungs and worst-case cost and ask whether to run
it; only on a yes, call `execute` with its `plan_id` and `approve: true`. Without a plan, offer to
open the page with browser-box `read`. Mention `cost_usd` when it is not 0.
If `$ARGUMENTS` is empty, ask for the URL.
