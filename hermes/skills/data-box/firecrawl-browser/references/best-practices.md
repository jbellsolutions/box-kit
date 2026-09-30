# Firecrawl browser: best practices

- **Try rung 1 first.** A scrape with `actions` (wait, click, scroll, press) inside `/v2/scrape` costs 1 credit a page, no minutes. The sandbox is for flows that need a session between steps.
- **Short TTLs.** `ttl` bills to the end unless the session is deleted; `activityTtl` kills an idle session. Set both, and delete explicitly.
- **One session, many steps.** Opening a session is the one-minute minimum; do the whole flow in it rather than one session per step.
- **Snapshot before clicking.** `agent-browser snapshot` returns the page's elements with refs (`@e5`); clicking by ref is stable where coordinates are not.
- **Read-only profiles for reading.** Open a saved profile with `saveChanges: false` unless the flow must update the login; only one session can save at a time.
- **Watch it live when debugging.** `liveViewUrl` shows the session; hand it to a person when a login needs a human.
- **Bot protection is not this rung's job.** A challenge page in the sandbox will be a challenge page every minute: move to Hyperbrowser.
