# Firecrawl browser: charter

**Scrape rung 4**, after the free fetch (0), Firecrawl scrape (1), Decodo (2) and Bright Data's Unlocker (3), and before Hyperbrowser (5) and browser-box (6). It exists for pages that need **actions**: clicks, scrolls, pagination behind buttons, forms, and logged-in profiles.

## Rules

1. **Code-written steps only.** data-box builds a closed set of actions (wait, click, scroll, press, read) from the plan. No free-form JavaScript from a request, and no `prompt` mode, where Firecrawl's model would choose the steps at 7 credits a minute.
2. **Every session has a TTL** no longer than the plan needs (at most 300 s in data-box) and is deleted in a `finally`. At startup data-box lists sessions (`GET /v2/interact`) and closes strays.
3. **Worst-case minutes are priced up front:** TTL rounded up to minutes x 2 credits, one-minute minimum.
4. **No bot protection work.** The sandbox has no proxy or stealth; a challenge page means rung 5, not more minutes here.
5. **Profiles hold logins and are the user's.** Opening one is a plan step the user approves; only one session saves to a profile at a time.
6. Same money rule as every paid call: only inside an approved plan, within its cap.
