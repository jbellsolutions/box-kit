---
description: Read a web page (or answer a question about one) through the self-hosted browser box — fetch first, real browser only when needed.
argument-hint: <url, or what you want to know from the web>
allowed-tools: [mcp__browser-box__fetch, mcp__browser-box__read, mcp__browser-box__status, Bash]
---

The user wants something from the web: $ARGUMENTS

Use the browser-box MCP server. Work in this order, and do not skip a step:

1. **`fetch` first.** It is free and instant and answers most pages. Only if it returns
   almost no text, a shell of scripts, or a bot check, escalate.
2. **`read` second**, and only then. It holds the single browser lane on the host.
3. Add `screenshot: true` only if the picture is the evidence — it costs a second page load
   and that load is not redirect-checked.
4. If anything fails, call **`status`** before concluding the capability is missing. It names
   what is down and why.

A `{"error": "refused: ..."}` result means the target is internal and the SSRF guard stopped
it. Report that plainly; do not attempt another route to the same address.

Answer with the content and the URL it came from. Don't narrate the tool calls.
