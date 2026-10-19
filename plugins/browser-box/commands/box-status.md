---
description: Is the browser box up? Reports what is running, what is down and why, and what recent calls cost.
allowed-tools: [mcp__browser-box__status, Bash]
---

Call the browser-box `status` tool and report it in plain language:

- Is Browser Use Cloud up (and Browserbase, if the box has it)? If not, give the reason verbatim — it is the actionable part.
- Which tools work right now, and which are withheld and why.
- Anything notable in the recent calls (failures, slow calls).

If the MCP server is not attached at all, say so and offer the CLI fallback: `bb status`.
Do not guess at the box's state — an unreachable box and a browser provider that is down are different
problems with different fixes.
