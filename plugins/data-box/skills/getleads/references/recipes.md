# GetLeads: recipes

All paid steps run inside an approved data-box plan (milestone D6). Until then, a signed-in caller can follow the same steps through its own GetLeads MCP tools.

## "2,000 VP-and-above marketing leaders at US SaaS companies, 50-500 employees, with verified emails"

1. **Free:** `GET /usage/fair-use`, to learn which window binds and how much is left.
2. **Free:** `GET /contacts/filter-values` for the exact seniority, department and industry values.
3. **Free:** `POST /contacts/search/count` for each industry route:
   - the named industry filter;
   - a `where_sql` keyword route over the company description.

   Union the routes that land, then count the union. If it is over 50,000, split by state.
4. **Plan:** rows = min(target, count), ranked against other providers at the amortized rate. The plan says which window binds.
5. **Execute** (after approval): `POST /contacts/search` with `limit` 1,000 and `max_per_company` 3, paged by `offset` until `has_more` is false or 2,000 rows are in. Dedupe on name + email.

## "Decision makers at these 300 accounts"

1. **Free:** one `count` call with all 300 domains.
2. **Plan:** `POST /contacts/lookup/decision-makers` in batches, at 1 credit per record returned.
3. **Execute:** send the batches, and record domains that returned nothing in `misses.jsonl`.

## "Fill in work emails for this LinkedIn list"

- `POST /enrich/from-linkedin` on the deduped list, `limit_per_item` 1.
- Only items where `success` is true are charged. Misses are recorded, so a resumed run never looks them up again.
