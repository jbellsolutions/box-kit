# Consulti: best practices

- **Read the canonical values first.** `GET /meta/{filter}` (free) lists the exact strings for industries (145), states (942), technologies (7,538), creator niches and more. Filters are exact matches; a near miss returns nothing.
- **Size pages deliberately.** A search reserves up to `size` (max 100) and refunds down to the rows returned; set `size` to what you still need, not the maximum.
- **Page with `page` and stop on `has_more: false`.** `total` can be capped; it is not a promise of that many rows.
- **Check `GET /credits` before a batch and after anything ambiguous.** It is free.
- **Local leads:** `email_type` says how the address was derived. `owner` means a pattern from the owner's name that passed verification; `role` means info@ or contact@. Ask for `hasOwnerEmail` when a person must receive it.
- **Deduplicate on your side.** Responses carry no stable id for a search today (`artifact_id` is not enabled), so data-box's merger keys on name + phone + address and on email.
- **Verification:** `status: unknown` is transient, so retry later. `is_role_account: true` usually replies less. `/verify/catchall` costs 5 and needs Pro.
