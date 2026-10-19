---
description: Click, type and move through a site in a hosted browser, step by step in plain words — or hand the whole goal over when steering each step is not worth it.
argument-hint: <what to do on which site>
allowed-tools: [mcp__browser-box__act, mcp__browser-box__session, mcp__browser-box__task, mcp__browser-box__read, mcp__browser-box__fetch, mcp__browser-box__status]
---

The user wants something done on a website: $ARGUMENTS

Use the browser-box MCP server.

1. **If it is only reading**, use `fetch` (then `read`) — not this.
2. **If you can plan the steps, use `act`.** One plain-words step per call, or up to 4 joined
   by "then": `open https://…`, `click the Pricing link`, `type 'x' into the search box and
   press enter`, `scroll down`, `go back`. Check each result's `status` and `url` before the
   next step.
   - `needs_clarification`: pick the option that matches what the user meant with
     `act(pick=…)`; if none does, say so rather than guessing.
   - `needs_confirmation`: this step is hard to undo. Only confirm what the user asked for
     explicitly; otherwise `act(confirm=false)` and ask them.
   - `act` returns the url and title, not the text: pass `read_page=true`, or `read(url)`.
   - Every browser is fresh and logged out. For a browser of your own, `session(action="create")`
     and pass its `session_id` to `act`; `release` it when done. Without one, `act` uses a shared
     scratch browser. This box keeps no logins: if the site needs one, say so rather than trying.
3. **If the goal is long or you would rather not steer**, use
   `task(goal, surface="browser")`: an agent plans the steps. It reports every step and what
   it cost. If you stop waiting it keeps running, so call `task(cancel=true)` to stop it.
4. A `refused` result means the target is internal; report it and do not route around it.
   If anything fails, call `status` before concluding a capability is missing.

Report what was done and what the page showed, with the URL. Never submit, buy, send or
delete anything the user did not explicitly ask for.
