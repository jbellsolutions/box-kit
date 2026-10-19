# DiscoLike: recipes

All paid steps run inside an approved data-box plan (milestone D5).

## "US B2B SaaS companies like stripe.com and plaid.com, 50-500 employees"

1. **Free:** `GET /v1/count` with the country, employee range and phrase filters. `count` takes no seed domains. Adjust until the number is workable, for example 2,400.
2. **Plan:**
   - `discover` with `domain=[stripe.com, plaid.com]`, the same filters, and `max_records` at the target;
   - preflight of 10 records;
   - the checkpoint: `validate/icp` with `native-icp` on the first 100 domains.
3. **Execute, stage 1:** discover, then validate 100. At 80% fit or better, the plan's next stage needs `confirm_stages` and runs the rest. At 50-79%, stop and tighten.
4. **Execute, stage 2:** `contacts/discover` for the shortlisted domains, 2 contacts per company by seniority, or MoltSets on the shortlist if that ranks cheaper.

## "Firmographics for these 800 domains"

- `POST /v1/append` in batches of 100 domains, since `append-data` is capped at 100 per call.
- The plan prices 800 domains at the per-domain rate and shows it before anything is spent.

## "Past 10,000 companies"

- Count first; the count is the ceiling.
- Page with an exclusion list per round, as the CLI's `bulk` does: each round adds up to 10,000 new domains.
- Each round is its own stage in the plan.
