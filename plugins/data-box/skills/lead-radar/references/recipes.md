# Lead Radar: recipes

These run once D9 is wired and Lead Radar ships its API.

## "People asking for a virtual assistant, last 14 days"

1. `plan` with `request: "people asking to hire a virtual assistant"`.
   - Intake marks it as intent: code first, and Jev's `intake.intent` in D8.
   - `platforms: all` except Reddit, and `days: 14`.
2. **Preflight:** `POST /radar/hunt` with `dry_run: true` returns an estimate, for example $1.80. The plan shows it with a cap.
3. **Execute, after the yes:** the hunt runs with `max_cost_usd` set to the cap and a stable `request_id`, and polls `GET /radar/runs/{id}`.
4. **Results:** leads with tiers and evidence quotes. `job action=export` with the High tier only.

## "…and get me their contact details"

- A second stage in the same plan: High-tier leads with a LinkedIn profile go to MoltSets `linkedin_to_business_email`, on the shortlist only.
- The stage is priced separately and needs its own line in the approval.
